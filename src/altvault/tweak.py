import argparse
import datetime as dt
import os
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import httpx

from altvault.generate import generate_latest_tweaked_apps_repo
from altvault.helpers.config import config
from altvault.helpers.cydia import get_cydia_package
from altvault.helpers.github import create_github_client, get_github_release_asset
from altvault.helpers.models import App, Tweak
from altvault.helpers.recipes import get_tweak_config

github_client = create_github_client()


def download_ipa(app_config: App, app_version: str | None, tmpdir: Path):
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
    decrypted_app_asset = github_client.rest.repos.get_release_asset(
        owner=config.owner,
        repo=app_config.ipa_repo,
        asset_id=decrypted_app_release.parsed_data.assets[0].id,
        headers={"Content-Type": "application/octet-stream"},
    )
    ipa_path = tmpdir / decrypted_app_asset.parsed_data.name
    with open(ipa_path, "wb") as f:
        for chunk in decrypted_app_asset.iter_bytes():
            f.write(chunk)
    return ipa_path, decrypted_app_release.parsed_data.tag_name


def download_debs(tweak_config: Tweak, tmpdir: Path):
    deb_paths: list[Path] = []
    if tweak_config.deb_files:
        for deb in tweak_config.deb_files:
            if deb.source == "cydia_repo":
                _deb_info = get_cydia_package(info=deb)
                deb_url = _deb_info.url
                if deb.use_version:
                    tweak_version_label = _deb_info.version
            elif deb.source == "github_releases":
                _deb_info = get_github_release_asset(info=deb)
                deb_url = _deb_info.url
                if deb.use_version:
                    tweak_version_label = _deb_info.tag
            with httpx.stream("GET", deb_url) as r:
                current_tweak_filepath = tmpdir / os.path.basename(
                    urlparse(deb_url).path
                )
                with open(current_tweak_filepath, "wb") as f:
                    for chunk in r.iter_bytes():
                        f.write(chunk)
                deb_paths.append(current_tweak_filepath)
    return deb_paths, tweak_version_label


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
        ipa_path: Path
        ipa_version: str
        ipa_path, ipa_version = download_ipa(
            app_config=app_config, app_version=args.app_version, tmpdir=tmpdir
        )

        print("download debs")
        deb_paths: list[Path]
        tweak_version_label: str | None
        deb_paths, tweak_version_label = download_debs(
            tweak_config=tweak_config, tmpdir=tmpdir
        )

        print("inject")
        injected_path: Path = tmpdir / "injected.ipa"
        subprocess.run(
            [
                "cyan",
                "--input",
                ipa_path,
                "--output",
                injected_path,
                "--remove-supported-devices",
                "--no-watch",
                "--remove-extensions",
                "-f",
                *deb_paths,
            ],
            check=True,
            cwd=tmpdirname,
        )

        # custom
        if tweak_config.name == "ApolloReborn":
            print("custom: apollo reborn patch")
            custom_apollo_reborn(tmpdir=tmpdir, injected_path=injected_path)
            note = "LiquidGlass"

        print("upload")
        if not tweak_version_label:
            tweak_version_label = dt.datetime.now(ZoneInfo("Asia/Bangkok")).strftime(
                "%Y%m%d%H%M"
            )
        if note:
            injected_filename = f"{app_config.name}_{ipa_version}_{tweak_config}_{tweak_version_label}_{note}.ipa"
            tag_name = f"{ipa_version}_{tweak_version_label}_{note}"
        else:
            injected_filename = f"{app_config.name}_{ipa_version}_{tweak_config}_{tweak_version_label}.ipa"
            tag_name = f"{ipa_version}_{tweak_version_label}"
        release = github_client.rest.repos.create_release(
            owner=config.owner,
            repo=tweak_config.ipa_repo,
            tag_name=tag_name,
        )
        with open(injected_path, "rb") as f:
            github_client.request(
                "POST",
                release.parsed_data.upload_url.split("{?")[0],
                params={"name": injected_filename},
                content=f.read(),
                headers={"Content-Type": "application/octet-stream"},
            )

        print("generate")
        generate_latest_tweaked_apps_repo()


if __name__ == "__main__":
    main()
