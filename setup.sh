#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
command -v python3 >/dev/null || { echo "Install Python 3.10+ first"; exit 1; }
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium
[ -f .env ] || cp .env.example .env
echo
echo "Setup done. Next:  .venv/bin/python -m src.login"
