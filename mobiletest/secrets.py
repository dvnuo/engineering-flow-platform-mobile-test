"""The test accounts: one JSON file of profiles the team keeps in Jenkins.

The file is a map of profiles, ``default`` and any others, each a map of the
fields the app asks for::

    {"default": {"username": "uat-fx-01", "password": "...", "pin": "1234"},
     "vip": {"username": "uat-fx-vip", "password": "..."}}

The Jenkins job hands it to the tests as MOBILE_TEST_USERS_FILE (the Secret
file credential its TEST_PROFILE_CREDENTIALS_ID parameter names); a build signs
in with the ``default`` profile. On a laptop, export MOBILE_TEST_USERS_FILE
before running behave, and MOBILE_TEST_USER to sign in with another profile.

``secret("MOBILE_SECRET_PASSWORD")`` is what recorded password fields turn
into: the chosen profile's ``password`` (the name without ``MOBILE_SECRET_``,
in lower case); an environment variable of that exact name still wins, so a
single value can be passed without a file. ``user_value("username")`` reads
any other field of the profile.
"""
import json
import os

DEFAULT_PROFILE = "default"
SECRET_PREFIX = "MOBILE_SECRET_"


class MissingSecret(RuntimeError):
    pass


def users_file_path():
    return os.environ.get("MOBILE_TEST_USERS_FILE", "")


def _load_users():
    path = users_file_path()
    if not path:
        raise MissingSecret(
            "no test users file: the Jenkins job passes its Secret file credential as MOBILE_TEST_USERS_FILE; "
            "on a laptop, export MOBILE_TEST_USERS_FILE=<path to the JSON file>"
        )
    try:
        with open(path, encoding="utf-8") as f:
            users = json.load(f)
    except OSError as exc:
        raise MissingSecret(f"the test users file could not be read: {exc}") from None
    except ValueError as exc:
        raise MissingSecret(f"the test users file is not valid JSON: {exc}") from None
    if not isinstance(users, dict) or not all(isinstance(v, dict) for v in users.values()):
        raise MissingSecret("the test users file must be a JSON object of profiles, each an object of fields")
    return users


def profile_name():
    return (os.environ.get("MOBILE_TEST_USER") or DEFAULT_PROFILE).strip() or DEFAULT_PROFILE


def profile(name=None):
    """The fields of one profile (the build's TEST_USER unless named)."""
    users = _load_users()
    wanted = (name or profile_name()).strip()
    if wanted not in users:
        known = ", ".join(sorted(users)) or "none"
        raise MissingSecret(f"the test users file has no profile {wanted!r}; it has: {known}")
    return dict(users[wanted])


def user_value(field, name=None):
    """One field of the profile, such as username; empty values count as missing."""
    values = profile(name)
    value = values.get(field)
    if value is None or str(value) == "":
        raise MissingSecret(f"profile {(name or profile_name())!r} of the test users file has no {field!r}; it has: {', '.join(sorted(values)) or 'nothing'}")
    return str(value)


def secret_field(name):
    """The profile field a text_env name stands for: MOBILE_SECRET_PASSWORD is password."""
    field = name[len(SECRET_PREFIX):] if name.startswith(SECRET_PREFIX) else name
    return field.lower()


def secret(name):
    """The value a recorded secret field types: the environment variable NAME
    when set, else the matching field of the chosen test user profile."""
    value = os.environ.get(name, "")
    if value:
        return value
    try:
        return user_value(secret_field(name))
    except MissingSecret as exc:
        raise MissingSecret(f"the test secret {name} is not set and the test users file does not supply it: {exc}") from None
