---
description: Collect Pinterest design references for a keyword and push them to the dataset repo
---

1. Make sure the virtual environment exists. If `.venv` is missing, run `setup.bat` on Windows or `./setup.sh` on macOS/Linux.
2. Ask the user for the search keyword(s), how many pins per keyword (default 50), and whether to force an industry (optional, must be a slug from `config/categories.yaml`).
3. Run `python -m src.collect "<keyword>" --limit <n>` (add `--industry <slug>` if given). Use `.venv\Scripts\python` on Windows or `.venv/bin/python` on macOS/Linux.
4. If the output says "Not logged in", run `python -m src.login`, tell the user to sign in to Pinterest in the browser window that opened, wait for "Logged in", then repeat step 3.
5. Report how many pins were saved per industry (read `pinterestrepo/index/stats.json`) and confirm the push succeeded.
