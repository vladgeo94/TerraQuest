import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"


def _default_data_dir():
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "TerraQuest"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "terraquest"


DATA_DIR = Path(os.environ.get("TERRAQUEST_DATA") or _default_data_dir())
LABS_DIR = DATA_DIR / "labs"
PLUGIN_CACHE = DATA_DIR / "plugin-cache"
BACKEND_DIR = DATA_DIR / "http-backend"
