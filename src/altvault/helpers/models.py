from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, RootModel


class MyBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Config(MyBaseModel):
    local_username: str
    owner: str
    index_repo: str
    index_tag: str


class Recipes(RootModel):
    root: list[App]

    def __iter__(self):
        return iter(self.root)

    def __getitem__(self, item):
        return self.root[item]


class App(MyBaseModel):
    name: str
    bundle_identifier: str
    tweaks: list[Tweak] = Field(default_factory=list)


class Tweak(MyBaseModel):
    name: str
    note: str | None = None
    deb_files: list[
        Annotated[
            CydiaRepoDebFile | GitHubReleasesDebFile, Field(discriminator="source")
        ]
    ] = Field(default_factory=list)


class DebFileBase(MyBaseModel):
    endswith: str | None = None
    use_version: bool = False


class CydiaRepoDebFile(DebFileBase):
    source: Literal["cydia_repo"] = "cydia_repo"
    repo: str
    package: str
    architecture: str
    version: str = "latest"


class GitHubReleasesDebFile(DebFileBase):
    source: Literal["github_releases"] = "github_releases"
    owner: str
    repo: str
    tag: str = "latest"
