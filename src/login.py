"""One-time login. Run:  python -m src.login

A Chrome window opens on Pinterest. Sign in however you normally do
(email + password, or "Continue with Google"). The session is stored in
.auth/browser-profile, so every later run is already logged in.
"""
import time

from . import config
from .browser import get_page, is_logged_in, open_context

TIMEOUT_S = 300


def main() -> None:
    print("🚀 Launching browser...", flush=True)
    with open_context(headless=False) as ctx:
        page = get_page(ctx)
        print("🌐 Opening Pinterest...", flush=True)
        page.goto(config.PINTEREST_HOME, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        if is_logged_in(ctx):
            print("✅ Already logged in to Pinterest — nothing to do.", flush=True)
            return
        print("🔐 Opening login page...", flush=True)
        page.goto(f"{config.PINTEREST_HOME}/login/", wait_until="domcontentloaded")
        try:
            page.bring_to_front()
        except Exception:
            pass
        print(f"👉 Log in to Pinterest in the browser window (waiting up to {TIMEOUT_S // 60} min)…", flush=True)
        deadline = time.time() + TIMEOUT_S
        while time.time() < deadline:
            if is_logged_in(ctx):
                page.wait_for_timeout(2000)  # let cookies flush to disk
                print("✅ Logged in. Session saved — future runs will reuse it.", flush=True)
                return
            time.sleep(2)
        print("⏱️  Timed out. Run `python -m src.login` again.", flush=True)


if __name__ == "__main__":
    main()
