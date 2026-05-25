import argparse
import sys
from pathlib import Path

from githubkit.exception import RequestFailed

from altvault.helpers.config import config
from altvault.helpers.confirm import confirm
from altvault.helpers.github import create_github_client
from altvault.helpers.ipa import extract_ipa_metadata
from altvault.helpers.recipes import get_app_config
from altvault.helpers.version import a_newer_than_b

github_client = create_github_client()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ipa_path")
    parser.add_argument("--note")
    args = parser.parse_args()

    ipa_path = Path(args.ipa_path)
    if not ipa_path.is_file():
        print(f"Error: IPA file not found: {ipa_path}", file=sys.stderr)
        sys.exit(1)
    ipa_filename = ipa_path.name
    ipa_filesize = ipa_path.stat().st_size

    metadata = extract_ipa_metadata(str(ipa_path))
    app_config = get_app_config(
        bundle_identifier=metadata.bundle_identifier, strict=True
    )

    notes = ""
    if "-eeveedecrypter" in ipa_filename:
        notes += "eeveedecrypter"
    elif "-Decrypted" in ipa_filename:
        notes += "armconverter"
    elif "_decrypt_" in ipa_filename:
        notes += "anyipa"
    elif "-AppAssassin" in ipa_filename:
        notes += "appassassin"
    if args.note:
        notes += args.note if notes == "" else f"\n{args.note}"

    # check latest
    try:
        latest = github_client.rest.repos.get_latest_release(
            owner=config.owner,
            repo=app_config.ipa_repo,
        )
        newer = a_newer_than_b(metadata.version, latest.parsed_data.tag_name)
    except RequestFailed as e:
        if e.response.status_code == 404:
            newer = True
        else:
            raise

    print("=======================")
    print(f"File Name: {ipa_filename}")
    print(f"Notes: {notes}")
    print(f"Newer: {newer}")
    print()

    if confirm(default=True):
        # create release
        release = github_client.rest.repos.create_release(
            owner=config.owner,
            repo=app_config.ipa_repo,
            tag_name=metadata.version,
            body=notes,
            make_latest="true" if newer else "false",
        )

        # upload
        with open(ipa_path, "rb") as f:
            github_client.request(
                "POST",
                release.parsed_data.upload_url.split("{?")[0],
                params={"name": ipa_filename},
                content=f.read(),
                headers={
                    "Content-Type": "application/octet-stream",
                    "Content-Length": str(ipa_filesize),
                },
            )


if __name__ == "__main__":
    main()
