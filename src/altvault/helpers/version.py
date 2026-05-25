from debian.debian_support import Version


def parse_version(a: str) -> Version:
    return Version(a.replace("_", ""))


def a_newer_than_b(a: str, b: str) -> bool:
    return parse_version(a) > parse_version(b)
