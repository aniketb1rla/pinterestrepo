"""Opens a real, persistent browser window so your Pinterest login is remembered."""
from contextlib import contextmanager

from playwright.sync_api import BrowserContext, Page, sync_playwright

from . import config


@contextmanager
def open_context(headless: bool | None = None):
    config.PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    headless = config.HEADLESS if headless is None else headless
    with sync_playwright() as p:
        kwargs = dict(
            user_data_dir=str(config.PROFILE_DIR),
            headless=headless,
            viewport={"width": 1440, "height": 900},
            locale="en-US",
            args=["--disable-blink-features=AutomationControlled"],
            ignore_default_args=["--enable-automation"],
        )
        if config.BROWSER_CHANNEL != "chromium":
            kwargs["channel"] = config.BROWSER_CHANNEL
        try:
            ctx = p.chromium.launch_persistent_context(**kwargs)
        except Exception as exc:  # channel not installed -> bundled Chromium
            if "channel" not in kwargs:
                raise
            print(f"[browser] '{config.BROWSER_CHANNEL}' not available ({exc.__class__.__name__}); "
                  "falling back to Playwright Chromium.")
            kwargs.pop("channel")
            ctx = p.chromium.launch_persistent_context(**kwargs)
        try:
            yield ctx
        finally:
            ctx.close()


def get_page(ctx: BrowserContext) -> Page:
    return ctx.pages[0] if ctx.pages else ctx.new_page()


def is_logged_in(ctx: BrowserContext) -> bool:
    """Pinterest sets the cookie _auth=1 for signed-in sessions."""
    for c in ctx.cookies("https://www.pinterest.com"):
        if c["name"] == "_auth" and c["value"] == "1":
            return True
    return False
