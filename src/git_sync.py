"""Clone / commit / push the dataset repo (github.com/aniketb1rla/pinterestrepo)."""
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from . import config


def _git(*args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, check=check, text=True, capture_output=True)


def _auth_url(url: str) -> str:
    if not config.GITHUB_TOKEN or not url.startswith("https://"):
        return url
    u = urlparse(url)
    return f"https://x-access-token:{config.GITHUB_TOKEN}@{u.netloc}{u.path}"


def ensure_repo() -> Path:
    repo = config.REPO_DIR
    if (repo / ".git").exists():
        r = _git("pull", "--rebase", "--autostash", "origin", config.GIT_BRANCH, cwd=repo, check=False)
        if r.returncode != 0 and "couldn't find remote ref" not in r.stderr:
            print(f"[git] pull skipped: {r.stderr.strip()[:200]}")
        return repo
    print(f"[git] cloning {config.REPO_URL} → {repo}")
    r = _git("clone", _auth_url(config.REPO_URL), str(repo), check=False)
    if r.returncode != 0:
        raise RuntimeError(f"git clone failed:\n{r.stderr}\nCheck the repo URL and that you're logged in to GitHub "
                           "(or set GITHUB_TOKEN in .env).")
    _git("remote", "set-url", "origin", config.REPO_URL, cwd=repo)  # don't leave the token in .git/config
    if _git("rev-parse", "--verify", "HEAD", cwd=repo, check=False).returncode != 0:
        _git("checkout", "-B", config.GIT_BRANCH, cwd=repo)  # brand-new empty repo
    if config.USE_GIT_LFS:
        _git("lfs", "install", "--local", cwd=repo, check=False)
        _git("lfs", "track", "*.jpg", cwd=repo, check=False)
    return repo


def commit_and_push(message: str) -> None:
    repo = config.REPO_DIR
    _git("add", "-A", cwd=repo)
    if _git("diff", "--cached", "--quiet", cwd=repo, check=False).returncode == 0:
        print("[git] nothing new to commit.")
        return
    r = _git("commit", "-m", message, cwd=repo, check=False)
    if r.returncode != 0:
        raise RuntimeError(f"git commit failed (set user.name/user.email?):\n{r.stderr or r.stdout}")
    if not config.AUTO_PUSH:
        print("[git] committed locally (AUTO_PUSH=false).")
        return
    r = _git("push", _auth_url(config.REPO_URL), f"HEAD:{config.GIT_BRANCH}", cwd=repo, check=False)
    if r.returncode != 0:
        msg = r.stderr.replace(config.GITHUB_TOKEN, "***") if config.GITHUB_TOKEN else r.stderr
        raise RuntimeError(f"git push failed:\n{msg}")
    print(f"[git] pushed to {config.REPO_URL} ({config.GIT_BRANCH}).")
