import os
import subprocess
from functools import cache
from typing import NamedTuple

from githubkit import GitHub
from githubkit.auth import ActionAuthStrategy, TokenAuthStrategy

from altvault.helpers.config import config
from altvault.helpers.models import GitHubReleasesDebFile


@cache
def create_github_client() -> GitHub:
    if os.environ.get("GITHUB_ACTIONS") == "true":
        return GitHub(ActionAuthStrategy())

    token = _get_local_github_token()
    return GitHub(TokenAuthStrategy(token))


def _get_local_github_token() -> str:
    result = subprocess.run(
        ["gh", "auth", "token", "--user", config.local_username],
        check=True,
        capture_output=True,
        text=True,
    )
    token = result.stdout.strip()
    if not token:
        raise RuntimeError(
            f"gh auth token returned an empty token for {config.local_username!r}"
        )
    return token


class GitHubReleaseAssetResult(NamedTuple):
    url: str
    tag: str


def get_github_release_asset(
    info: GitHubReleasesDebFile,
) -> GitHubReleaseAssetResult:
    github_client = create_github_client()

    if info.tag == "latest":
        release = github_client.rest.repos.get_latest_release(
            owner=info.owner, repo=info.repo
        )
    else:
        release = github_client.rest.repos.get_release_by_tag(
            owner=info.owner, repo=info.repo, tag=info.tag
        )
    if not release:
        raise ValueError("Release not found")
    assets = release.parsed_data.assets
    tag_name = release.parsed_data.tag_name.removeprefix("v")

    for asset in assets:
        if (info.startswith is None or asset.name.startswith(info.startswith)) and (
            info.endswith is None or asset.name.endswith(info.endswith)
        ):
            return GitHubReleaseAssetResult(
                url=asset.browser_download_url, tag=tag_name
            )

    return GitHubReleaseAssetResult(url=assets[0].browser_download_url, tag=tag_name)
