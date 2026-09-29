"""Test account passwords come from the environment, never from a file."""
import os


class MissingSecret(RuntimeError):
    pass


def secret(name):
    """The value of the environment variable NAME (a Jenkins credential)."""
    value = os.environ.get(name, "")
    if not value:
        raise MissingSecret(
            f"the test secret {name} is not set: pass it through the job's TEST_SECRETS parameter "
            f"(a Jenkins Secret text credential), or export it before running behave"
        )
    return value
