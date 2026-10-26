# Pinterest Reference Collector — agent guide

This workspace is a Python + Playwright tool that searches Pinterest with the
user's own logged-in session, downloads design references, sorts them by
industry, and pushes them to the dataset repo
https://github.com/aniketb1rla/pinterestrepo (cloned into `./pinterestrepo`).

## How to run things (always from the project root, inside .venv)
- First-time setup: `setup.bat` (Windows) or `./setup.sh` (macOS/Linux)
- Log in once (opens Chrome, user signs in manually): `python -m src.login`
- Collect: `python -m src.collect "<keyword>" --limit 50`
- Download pin by URL/ID: `python -m src.download "<pin_url_or_id>" [--output ./downloads]`
- Download Pinterest board: `python -m src.download "<board_url>" --limit 40`
- Many keywords or pins: `python -m src.collect --file keywords.txt --limit 40`
- Re-sort existing pins: `python -m src.reclassify --classifier gemini`
- Analyze pins & prompt templates: `python -m src.prompt_template <pin_id>`
- View Front-End UI: `python -m src.server --open` (or double-click `ui.bat`)
- Tests: `python -m unittest discover tests`

## Rules for the agent
- Never type, store, or ask for the user's Pinterest password. Login only
  happens by the user in the visible browser via `src.login`.
- Never commit `.env`, `.auth/`, or tokens. `.auth/browser-profile` holds the
  saved session.
- If a run prints "Not logged in", run `python -m src.login` and wait for
  the user to sign in, then retry.
- Keep scraping polite: don't lower the scroll delays in `src/scraper.py`
  or raise `--limit` above ~200 per keyword in a single run.
- Industries live in `config/categories.yaml`. To add one, add a slug with
  `label` and `keywords`; then optionally run `src.reclassify`.
- The dataset format (see `src/storage.py`) is a contract: images
  `dataset/<industry>/<pin_id>.jpg`, captions `<pin_id>.txt`, records in
  `index/pins.jsonl`. Don't rename fields without migrating existing data.
- If Pinterest changes its page and the scraper finds 0 pins, inspect
  network responses containing `SearchResource` and the `a[href*="/pin/"]`
  cards; update `parse_pin` / `_DOM_JS` in `src/scraper.py`.
