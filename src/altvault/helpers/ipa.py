import plistlib
import zipfile

from pydantic import BaseModel, ConfigDict


class ExtractedIpaMetadata(BaseModel):
    bundle_identifier: str
    version: str

    model_config = ConfigDict(extra="forbid", frozen=True)


def extract_ipa_metadata(ipa_path: str) -> ExtractedIpaMetadata:
    with zipfile.ZipFile(ipa_path, "r") as zf:
        plist_paths = [
            name
            for name in zf.namelist()
            if name.startswith("Payload/")
            and name.endswith(".app/Info.plist")
            and name.count("/") == 2
        ]
        plist_data = zf.read(plist_paths[0])
    info = plistlib.loads(plist_data)
    return ExtractedIpaMetadata(
        bundle_identifier=info["CFBundleIdentifier"],
        version=info["CFBundleShortVersionString"],
    )
