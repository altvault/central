from ..recipes import recipes

recipes = recipes


def get_app_config(
    name: str | None = None, bundle_identifier: str | None = None, strict: bool = False
):
    if not name and not bundle_identifier:
        raise ValueError("Missing name or bundle_identifier")

    for app in recipes:
        if app.name == name or app.bundle_identifier == bundle_identifier:
            return app

    if strict:
        raise LookupError(
            f"App config not found: name={name!r}, bundle_identifier={bundle_identifier!r}"
        )


def get_tweak_config(name: str | None, strict: bool = False):
    if not name:
        raise ValueError("Missing name")

    for app in recipes:
        for tweak in app.tweaks:
            if tweak.name == name:
                return app, tweak

    if strict:
        raise LookupError(f"Tweak config not found: name={name!r}")
