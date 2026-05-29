import gzip
from typing import NamedTuple
from urllib.parse import urljoin

import httpx
from debian import deb822

from altvault.helpers.models import CydiaRepoDebFile
from altvault.helpers.version import parse_version


def _fetch_cydia_repo(url: str) -> list[deb822.Packages]:
    packages_gz_url = f"{url}/Packages.gz"
    response = httpx.get(packages_gz_url)
    content = gzip.decompress(response.content).decode("utf-8")
    packages = list(deb822.Packages.iter_paragraphs(content))
    return packages


class CydiaPackageResult(NamedTuple):
    url: str
    version: str


def get_cydia_package(info: CydiaRepoDebFile) -> CydiaPackageResult:
    all_packages = _fetch_cydia_repo(info.repo)
    filtered_packages = [pkg for pkg in all_packages if pkg["Package"] == info.package]
    if info.version == "latest":
        sorted_packages = sorted(
            filtered_packages, key=lambda x: parse_version(x["Version"])
        )
        latest_package = sorted_packages[-1]
        wanted_package = latest_package
    else:
        for pkg in filtered_packages:
            if pkg["Version"] == info.version:
                wanted_package = pkg
                break
    if not wanted_package:
        raise ValueError("Not found")
    return CydiaPackageResult(
        url=urljoin(f"{info.repo}/", wanted_package["Filename"]),
        version=wanted_package["Version"],
    )
