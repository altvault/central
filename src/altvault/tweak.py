import argparse
import datetime as dt
import hashlib
import os
import subprocess
import tempfile
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import httpx

from altvault.helpers.config import config
from altvault.helpers.cydia import get_cydia_package
from altvault.helpers.github import create_github_client, get_github_release_asset
from altvault.helpers.models import (
    App,
    Tweak,
    TweakedReleaseBodyJson,
    TweakedReleaseBodyJson_deb,
    TweakedReleaseBodyJson_ipa,
)
from altvault.helpers.recipes import get_tweak_config

github_client = create_github_client()


class DownloadIpaResult(NamedTuple):
    path: Path
    file_name: str
    version: str
    sha256: str


def download_ipa(
    app_config: App, app_version: str | None, tmpdir: Path
) -> DownloadIpaResult:
    if app_version:
        decrypted_app_release = github_client.rest.repos.get_release_by_tag(
            owner=config.owner, repo=app_config.ipa_repo, tag=app_version
        )
    else:
        decrypted_app_release = github_client.rest.repos.get_latest_release(
            owner=config.owner, repo=app_config.ipa_repo
        )
    if not decrypted_app_release:
        raise Exception("decrypted_app_release not found")
    if len(decrypted_app_release.parsed_data.assets) != 1:
        raise Exception("decrypted_app_release assets != 1")
    decrypted_app_release_first_asset = decrypted_app_release.parsed_data.assets[0]
    decrypted_app_asset = github_client.rest.repos.get_release_asset(
        owner=config.owner,
        repo=app_config.ipa_repo,
        asset_id=decrypted_app_release_first_asset.id,
        headers={"Accept": "application/octet-stream"},
    )
    ipa_path = tmpdir / decrypted_app_release_first_asset.name
    sha256 = hashlib.sha256()
    with open(ipa_path, "wb") as f:
        for chunk in decrypted_app_asset.iter_bytes():
            f.write(chunk)
            sha256.update(chunk)
    return DownloadIpaResult(
        path=ipa_path,
        file_name=decrypted_app_release_first_asset.name,
        version=decrypted_app_release.parsed_data.tag_name,
        sha256=sha256.hexdigest(),
    )


class DownloadDebsResultDebInfo(NamedTuple):
    path: Path
    url: str
    sha256: str


class DownloadDebsResult(NamedTuple):
    debs: list[DownloadDebsResultDebInfo]
    version_label: str | None = None


def download_debs(tweak_config: Tweak, tmpdir: Path) -> DownloadDebsResult:
    deb_list: list[DownloadDebsResultDebInfo] = []
    version_label: str | None = None
    if tweak_config.deb_files:
        for deb in tweak_config.deb_files:
            if deb.source == "cydia_repo":
                _deb_info = get_cydia_package(info=deb)
                deb_url = _deb_info.url
                if deb.use_version:
                    version_label = _deb_info.version
            elif deb.source == "github_releases":
                _deb_info = get_github_release_asset(info=deb)
                deb_url = _deb_info.url
                if deb.use_version:
                    version_label = _deb_info.tag
            with httpx.stream("GET", deb_url, follow_redirects=True) as r:
                current_tweak_filepath = tmpdir / os.path.basename(
                    urlparse(deb_url).path
                )
                sha256 = hashlib.sha256()
                with open(current_tweak_filepath, "wb") as f:
                    for chunk in r.iter_bytes():
                        f.write(chunk)
                        sha256.update(chunk)
                deb_list.append(
                    DownloadDebsResultDebInfo(
                        path=current_tweak_filepath,
                        url=deb_url,
                        sha256=sha256.hexdigest(),
                    )
                )
    return DownloadDebsResult(debs=deb_list, version_label=version_label)


def custom_apollo_reborn(tmpdir: Path, injected_path: Path):
    apollo_reborn_repo_dir = tmpdir / "apollo-reborn"
    patched_ipa_path = apollo_reborn_repo_dir / "apollo_patched.ipa"
    subprocess.run(
        [
            "git",
            "clone",
            "--depth=1",
            f"https://github.com/{config.owner}/Apollo-Reborn.git",
            apollo_reborn_repo_dir,
        ],
        check=True,
    )
    subprocess.run(
        [
            "bash",
            apollo_reborn_repo_dir / "patch.sh",
            injected_path,
            "--output",
            patched_ipa_path,
            "--liquid-glass",
            "--url-schemes",
            "dystopia",
        ],
        check=True,
        cwd=tmpdir,
    )
    return patched_ipa_path.replace(injected_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("tweak_name")
    parser.add_argument("--app-version")
    parser.add_argument("--note")
    args = parser.parse_args()

    app_config, tweak_config = get_tweak_config(name=args.tweak_name, strict=True)
    note = args.note

    if not app_config or not tweak_config:
        raise ValueError("app_config or tweak_config not found")

    with tempfile.TemporaryDirectory() as tmpdirname:
        tmpdir: Path = Path(tmpdirname)

        print("download ipa")
        ipa_download_result = download_ipa(
            app_config=app_config,
            app_version=None if args.app_version == "latest" else args.app_version,
            tmpdir=tmpdir,
        )

        print("download debs")
        deb_download_results = download_debs(tweak_config=tweak_config, tmpdir=tmpdir)

        print("inject")
        injected_path: Path = tmpdir / "injected.ipa"
        subprocess.run(
            [
                "cyan",
                "--input",
                ipa_download_result.path,
                "--output",
                injected_path,
                # "--remove-supported-devices",
                "--no-watch",
                "--remove-encrypted",
                "-f",
                *[deb.path for deb in deb_download_results.debs],
            ],
            check=True,
            cwd=tmpdir,
        )

        # custom
        if tweak_config.name == "ApolloReborn":
            print("custom: apollo reborn patch")
            custom_apollo_reborn(tmpdir=tmpdir, injected_path=injected_path)
            note = "LiquidGlass"

        print("upload")
        tweak_version_label = deb_download_results.version_label
        if not tweak_version_label:
            tweak_version_label = dt.datetime.now(ZoneInfo("Asia/Bangkok")).strftime(
                "%Y%m%d%H%M"
            )
        if note:
            injected_filename = f"{app_config.name}_{ipa_download_result.version}_{tweak_config.name}_{tweak_version_label}_{note}.ipa"
            tag_name = f"{ipa_download_result.version}_{tweak_version_label}_{note}"
        else:
            injected_filename = f"{app_config.name}_{ipa_download_result.version}_{tweak_config.name}_{tweak_version_label}.ipa"
            tag_name = f"{ipa_download_result.version}_{tweak_version_label}"

        # custom (ApolloReborn puts app_version in their tag_name so prevent duplication)
        if tweak_version_label.startswith(f"{ipa_download_result.version}_"):
            tag_name = tag_name.removeprefix(f"{ipa_download_result.version}_")

        # release body
        release_body_json = TweakedReleaseBodyJson(
            ipa=TweakedReleaseBodyJson_ipa(
                file_name=ipa_download_result.file_name,
                version=ipa_download_result.version,
                sha256=ipa_download_result.sha256,
            ),
            debs=[
                TweakedReleaseBodyJson_deb(url=deb.url, sha256=deb.sha256)
                for deb in deb_download_results.debs
            ],
        )
        release_body = f"```json\n{release_body_json.model_dump_json(indent=2)}\n```"

        release = github_client.rest.repos.create_release(
            owner=config.owner,
            repo=tweak_config.ipa_repo,
            tag_name=tag_name,
            body=release_body,
        )
        with open(injected_path, "rb") as f:
            github_client.request(
                "POST",
                release.parsed_data.upload_url.split("{?")[0],
                params={"name": injected_filename},
                content=f.read(),
                headers={"Content-Type": "application/octet-stream"},
            )


if __name__ == "__main__":
    main()
