import os
import configparser
import logging
import errno
from pydantic import BaseModel
from typing import Optional, Dict, Any, List


logger = logging.getLogger(__name__)


_DIRNAME = ".gwenlake"
_FILENAME = "credentials"


class Profile(BaseModel):
    token: Optional[str] = None
    token_uri: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    scopes: Optional[List] = None
    tenant: Optional[str] = None


def _get_default_user_profile_path() -> str:
    config_path = None

    if os.name == "nt":
        config_path = os.getenv("APPDATA")
    if not config_path:
        config_path = os.path.expanduser("~")

    config_path = os.path.join(config_path, _DIRNAME)
    return os.path.join(config_path, _FILENAME)


def _load_user_profile_from_dict(content: Dict[str, Any]):
    _profile = Profile(
        token=content.get("token"),
        client_id=content.get("client_id"),
        client_secret=content.get("client_secret"),
        tenant=content.get("tenant"),
    )

    if content.get("scopes"):
        _profile.scopes = [scope.strip() for scope in content.get("scopes", "").split(",")],

    return _profile


def load_user_profile(profile: str = "default") -> Profile:
    try:
        if profile is None:
            profile = "default"
            
        config_path = _get_default_user_profile_path()

        _config = configparser.ConfigParser()
        _config.read(config_path)

    except (IOError, ValueError) as exc:
        logger.debug(
            "Error loading credentials from {}: {}".format(config_path, str(exc))
        )
        return None

    return _load_user_profile_from_dict(_config[profile])


def save_user_profile(name: str, profile: Profile):
    config_path = _get_default_user_profile_path()

    config_dir = os.path.dirname(config_path)
    if not os.path.exists(config_dir):
        try:
            os.makedirs(config_dir)
        except OSError as exc:
            if exc.errno != errno.EEXIST:
                logger.warning(f"Unable to create {_DIRNAME} directory.")
                return

    config = configparser.ConfigParser()

    if os.path.exists(config_path):
        try:
            config.read(config_path)
        except (IOError, ValueError) as exc:
            logger.debug(
                "Error loading credentials from {}: {}".format(
                    config_path, str(exc)
                )
            )

    if name != "default" and not config.has_section(name):
        config.add_section(name)

    config[name]["token"] = profile.token
    config[name]["client_id"] = profile.client_id
    config[name]["client_secret"] = profile.client_secret
    if profile.scopes is not None:
        config[name]["scopes"] = ",".join(profile.scopes)
    config[name]["tenant"] = profile.tenant

    try:
        with open(config_path, "w") as f:
            config.write(f)
    except IOError:
        logger.warning("Unable to save profile.")