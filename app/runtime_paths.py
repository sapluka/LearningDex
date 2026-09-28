"""Locate bundled assets and writable user data."""

import os
import sys
from pathlib import Path


RESOURCE_ROOT = Path(__file__).resolve().parent.parent


def data_root():
    if getattr(sys, "frozen", False):
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "LearningDex"
    return RESOURCE_ROOT
