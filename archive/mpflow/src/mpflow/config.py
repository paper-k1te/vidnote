"""Credential handling for mpflow.

Everything comes from the environment so that the CLI is easy to use in CI:

    MP_APPID   WeChat Official Account AppID
    MP_SECRET  WeChat Official Account AppSecret

The IP allowlist of the Official Account must contain the machine that calls
the API; WeChat rejects token requests from unknown IPs with errcode 40164.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigError(RuntimeError):
    """Raised when credentials are missing or incomplete."""


@dataclass(frozen=True)
class Credentials:
    appid: str
    secret: str

    @classmethod
    def from_env(cls) -> Credentials:
        appid = os.environ.get("MP_APPID", "").strip()
        secret = os.environ.get("MP_SECRET", "").strip()
        if not appid or not secret:
            raise ConfigError(
                "MP_APPID / MP_SECRET are not set.\n"
                "Export them first:\n"
                "  export MP_APPID=wx...\n"
                "  export MP_SECRET=..."
            )
        return cls(appid=appid, secret=secret)

    @staticmethod
    def is_configured() -> bool:
        return bool(os.environ.get("MP_APPID")) and bool(os.environ.get("MP_SECRET"))
