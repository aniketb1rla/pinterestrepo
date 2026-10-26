"""Central settings, loaded from .env (copy .env.example -> .env)."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


# Browser / login ---------------------------------------------------------
# Persistent profile = your Pinterest login is kept between runs.
PROFILE_DIR = ROOT / ".auth" / "browser-profile"
BROWSER_CHANNEL = os.getenv("BROWSER_CHANNEL", "chrome")  # chrome | msedge | chromium
HEADLESS = _bool("HEADLESS", "false")
PINTEREST_HOME = os.getenv("PINTEREST_HOME", "https://www.pinterest.com")

# Dataset repo ------------------------------------------------------------
REPO_URL = os.getenv("DATASET_REPO_URL", "https://github.com/aniketb1rla/pinterestrepo.git")
DEFAULT_REPO = ROOT if (ROOT / "dataset").exists() else (ROOT / "pinterestrepo")
REPO_DIR = Path(os.getenv("DATASET_REPO_DIR", str(DEFAULT_REPO))).expanduser().resolve()
GIT_BRANCH = os.getenv("GIT_BRANCH", "main")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()  # optional; otherwise your normal git login is used
USE_GIT_LFS = _bool("USE_GIT_LFS", "false")
AUTO_PUSH = _bool("AUTO_PUSH", "true")

# Classification ----------------------------------------------------------
CLASSIFIER = os.getenv("CLASSIFIER", "keywords").strip().lower()  # keywords | gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
DROP_NON_DESIGN = _bool("DROP_NON_DESIGN", "false")  # gemini only: skip plain photos
CATEGORIES_FILE = ROOT / "config" / "categories.yaml"

# Images ------------------------------------------------------------------
MAX_IMAGE_SIDE = int(os.getenv("MAX_IMAGE_SIDE", "1440"))
JPEG_QUALITY = int(os.getenv("JPEG_QUALITY", "90"))
DUPLICATE_HAMMING = int(os.getenv("DUPLICATE_HAMMING", "4"))  # 0 = exact only

# Politeness --------------------------------------------------------------
MAX_SCROLLS = int(os.getenv("MAX_SCROLLS", "40"))
