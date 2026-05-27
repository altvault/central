import asyncio
import subprocess
from time import time
from typing import NamedTuple

import httpx
from githubkit.exception import RequestFailed

from altvault.helpers.config import config
from altvault.helpers.confirm import confirm
from altvault.helpers.github import create_github_client
from altvault.helpers.models import App
from altvault.helpers.version import a_newer_than_b
from altvault.recipes import recipes

LINE_SEPARATOR = "------------------------------------------------------------------------------------------"

github_client = create_github_client()


async def lookup_appstore(client: httpx.AsyncClient, bundle_identifier: str):
    response = await client.get(
        f"https://itunes.apple.com/lookup?bundleId={bundle_identifier}&cacheBusting={time()}"
    )
    data = response.json()
    return (data["results"][0]["version"], data["results"][0]["trackViewUrl"])


async def our_latest_version(repo: str):
    try:
        release = await github_client.rest.repos.async_get_latest_release(
            owner=config.owner,
            repo=repo,
        )
        return release.parsed_data.tag_name
    except RequestFailed as e:
        if e.response.status_code == 404:
            return None
        else:
            raise


class CheckAppVersionResult(NamedTuple):
    name: str
    appstore_url: str
    appstore_version: str
    decrypted_version: str
    decrypted_outdated: bool | None
    tweaked_version: str | None
    tweaked_outdated: bool | None


async def check_app_version(client: httpx.AsyncClient, app: App):
    tasks = [
        lookup_appstore(client=client, bundle_identifier=app.bundle_identifier),
        our_latest_version(repo=app.ipa_repo),
    ]
    if len(app.tweaks) > 0:
        tasks.append(our_latest_version(repo=app.tweaks[0].ipa_repo))

    results = await asyncio.gather(*tasks)
    (appstore_version, appstore_url) = results[0]
    our_decrypted_version = results[1]
    our_tweaked_version = results[2] if len(results) == 3 else None

    decrypted_is_outdated = (
        a_newer_than_b(appstore_version, our_decrypted_version)
        if our_decrypted_version and app.name != "Apollo"
        else None
    )

    tweaked_is_outdated = (
        a_newer_than_b(appstore_version, our_tweaked_version)
        if our_tweaked_version
        else None
    )

    return CheckAppVersionResult(
        name=app.name,
        appstore_url=appstore_url,
        appstore_version=appstore_version,
        decrypted_version=our_decrypted_version,
        decrypted_outdated=decrypted_is_outdated,
        tweaked_version=our_tweaked_version,
        tweaked_outdated=tweaked_is_outdated,
    )


async def amain():
    print(LINE_SEPARATOR)
    print(
        f"{'name':<14}",
        f"{'appstore':<9}",
        f"{'decrypted':<9}",
        f"{'': <2}",
        f"{'tweaked':<9}",
        f"{'': <2}",
        f"{'link'}",
    )
    print(LINE_SEPARATOR)

    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            *[check_app_version(client=client, app=app) for app in recipes]
        )

    outdated_apps: list[CheckAppVersionResult] = []

    for result in results:
        print(
            f"{result.name:<14}",
            f"{result.appstore_version:<9}",
            f"{result.decrypted_version or '':<9}",
            f"{'✓' if result.decrypted_outdated else '': <2}",
            f"{result.tweaked_version or '':<9}",
            f"{'✓' if result.tweaked_outdated else '': <2}",
            f"{result.appstore_url}",
        )
        if result.decrypted_outdated:
            outdated_apps.append(result)
    print(LINE_SEPARATOR)

    if len(outdated_apps) > 0:
        for outdated_app in outdated_apps:
            if confirm(
                prompt=f"Update {outdated_app.name} {outdated_app.appstore_version}",
                default=True,
            ):
                telegram_bot = (
                    "FastDecryptBot"
                    if outdated_app in ["Instagram", "TikTok"]
                    else "eeveedecrypterbot"
                )
                telegram_link = (
                    f"tg://resolve?domain={telegram_bot}&text={result.appstore_url}"
                )
                subprocess.run(["open", telegram_link], check=True)
        print(LINE_SEPARATOR)


def main():
    asyncio.run(amain())


if __name__ == "__main__":
    main()
