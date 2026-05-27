from githubkit.exception import RequestFailed

from altvault.helpers.config import config
from altvault.helpers.github import create_github_client
from altvault.helpers.models import AltSourceApp, AltSourceRepo
from altvault.recipes import recipes

github_client = create_github_client()


def upload_json(file_name: str, data: str):
    # get index release
    release = github_client.rest.repos.get_release_by_tag(
        owner=config.owner, repo=config.index_repo, tag=config.index_tag
    )
    # delete if exists to replace
    for asset in release.parsed_data.assets:
        if asset.name == file_name:
            github_client.rest.repos.delete_release_asset(
                owner=config.owner, repo=config.index_repo, asset_id=asset.id
            )
            break
    # upload file
    github_client.request(
        "POST",
        release.parsed_data.upload_url.split("{?")[0],
        params={"name": file_name},
        content=data,
        headers={"Content-Type": "application/octet-stream"},
    )


def generate_latest_tweaked_apps_repo():
    tweaked_apps = []

    for app in recipes:
        for tweak in app.tweaks:
            print(f"getting latest release from {tweak.ipa_repo}")
            try:
                _release = github_client.rest.repos.get_latest_release(
                    owner=config.owner, repo=tweak.ipa_repo
                )
            except RequestFailed as e:
                if e.response.status_code == 404:
                    print("::warning", "latest release not found for", tweak.ipa_repo)
                    continue
                else:
                    raise
            release = _release.parsed_data
            if len(release.assets) != 1:
                print(
                    "::warning",
                    tweak.ipa_repo,
                    release.tag_name,
                    "has",
                    len(release.assets),
                    "assets",
                )
            for asset in release.assets:
                if asset.name.endswith(".ipa"):
                    description = asset.name
                    if release.body_text:
                        description += "\n" + release.body_text
                    tweaked_apps.append(
                        AltSourceApp(
                            name=tweak.name,
                            bundleIdentifier=app.bundle_identifier,
                            version=release.tag_name,
                            localizedDescription=description,
                            downloadURL=f"/download/{tweak.ipa_repo}/{asset.id}/{asset.name}",
                            iconURL=f"/icon/{app.name}.jpg",
                            versionDate=asset.created_at.isoformat(),
                            size=asset.size,
                        )
                    )
                    break

    tweaked_apps_repo = AltSourceRepo(
        name="AltVault Latest Tweaked Apps",
        identifier="altvault.tweaked.latest",
        iconURL="/icon.png",
        apps=sorted(tweaked_apps, key=lambda x: x.versionDate, reverse=True),
    )

    print("uploading latest.json")
    upload_json(file_name="latest.json", data=tweaked_apps_repo.model_dump_json())
    print("finished")


def main():
    generate_latest_tweaked_apps_repo()


if __name__ == "__main__":
    main()
