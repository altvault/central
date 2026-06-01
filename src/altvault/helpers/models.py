from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, RootModel, computed_field


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

    @computed_field
    @property
    def ipa_repo(self) -> str:
        return f"{self.name}-ipas"


class Tweak(MyBaseModel):
    name: str
    note: str | None = None
    deb_files: list[
        Annotated[
            CydiaRepoDebFile | GitHubReleasesDebFile, Field(discriminator="source")
        ]
    ] = Field(default_factory=list)

    @computed_field
    @property
    def ipa_repo(self) -> str:
        return f"{self.name}-ipas"


class DebFileBase(MyBaseModel):
    use_version: bool = False
    extract: list[str] = Field(default_factory=list)


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
    startswith: str | None = None
    endswith: str | None = None


class AltSourceApp(MyBaseModel):
    name: str
    bundleIdentifier: str
    version: str
    localizedDescription: str
    downloadURL: str
    iconURL: str
    versionDate: str
    size: int


class AltSourceRepo(MyBaseModel):
    name: str
    identifier: str
    iconURL: str
    apps: list[AltSourceApp]


class TweakedReleaseBodyJson_ipa(MyBaseModel):
    file_name: str
    version: str
    sha256: str


class TweakedReleaseBodyJson_deb(MyBaseModel):
    url: str
    sha256: str


class TweakedReleaseBodyJson(MyBaseModel):
    ipa: TweakedReleaseBodyJson_ipa
    debs: list[TweakedReleaseBodyJson_deb]
