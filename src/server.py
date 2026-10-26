"""Lightweight local web server and API for browsing collected Pinterest references.

Run via:
    python -m src.server
    python -m src.server --port 8000 --open
"""
from __future__ import annotations

import argparse
import html
import io
import json
import mimetypes
import os
import socket
import subprocess
import sys
import threading
import urllib.parse
import uuid
import webbrowser
import zipfile
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from . import config
from .classifier import load_categories
from .design_analyzer import (
    analyze_pin,
    build_ad_creative_template,
    delete_template_record,
    list_saved_templates,
    save_template_record,
)

WEB_DIR = Path(__file__).resolve().parent / "web"


class CollectorJob:
    """Represents a background collection or download task triggered from the UI."""

    def __init__(
        self,
        query: str = "",
        limit: int = 30,
        industry: str | None = None,
        headless: bool = True,
        mode: str = "collect",  # "collect" or "download"
        targets: list[str] | None = None,
        destination: str = "dataset",  # "dataset", "folder", "both"
        output_dir: str | None = None,
    ):
        self.id = str(uuid.uuid4())[:8]
        self.mode = mode
        self.query = query.strip()
        self.targets = [t.strip() for t in (targets or []) if t and t.strip()]
        if not self.targets and self.query:
            self.targets = [self.query]
        self.destination = destination
        self.output_dir = output_dir or "downloads"
        self.limit = max(1, min(limit, 200))
        self.industry = industry
        self.headless = headless
        self.status = "running"  # running, done, error, cancelled
        self.progress_log: list[str] = []
        action = "Download" if mode == "download" else "Collection"
        descr = f"{len(self.targets)} target(s)" if mode == "download" else f"'{self.query}'"
        self.last_line = f"Starting {action} for {descr}..."
        self.saved_count = 0
        self.error: str | None = None
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.finished_at: str | None = None
        self.process: subprocess.Popen | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "mode": self.mode,
            "query": self.query,
            "targets": self.targets,
            "destination": self.destination,
            "output_dir": self.output_dir,
            "limit": self.limit,
            "industry": self.industry,
            "status": self.status,
            "last_line": self.last_line,
            "saved_count": self.saved_count,
            "error": self.error,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "recent_logs": self.progress_log[-20:],
        }


class CollectorManager:
    """Coordinates active scraping processes and reports live progress."""

    def __init__(self, store: ReferenceStore):
        self.store = store
        self.current_job: CollectorJob | None = None
        self._lock = threading.Lock()

    def start_job(
        self,
        query: str = "",
        limit: int = 30,
        industry: str | None = None,
        headless: bool = True,
        mode: str = "collect",
        targets: list[str] | None = None,
        destination: str = "dataset",
        output_dir: str | None = None,
    ) -> CollectorJob:
        with self._lock:
            if self.current_job and self.current_job.status == "running":
                cur_desc = self.current_job.query or (", ".join(self.current_job.targets[:2]) if self.current_job.targets else "task")
                raise ValueError(f"Task already in progress for '{cur_desc}'")
            job = CollectorJob(
                query=query,
                limit=limit,
                industry=industry,
                headless=headless,
                mode=mode,
                targets=targets,
                destination=destination,
                output_dir=output_dir,
            )
            self.current_job = job

        t = threading.Thread(target=self._run_job, args=(job,), daemon=True)
        t.start()
        return job

    def cancel_job(self) -> bool:
        with self._lock:
            if self.current_job and self.current_job.status == "running":
                job = self.current_job
                job.status = "cancelled"
                job.last_line = "Cancelled by user"
                if job.process:
                    try:
                        job.process.terminate()
                    except Exception:
                        pass
                return True
        return False

    def get_status(self) -> dict[str, Any]:
        with self._lock:
            job = self.current_job
            active = bool(job and job.status == "running")
            return {
                "active": active,
                "job": job.to_dict() if job else None,
            }

    def _run_job(self, job: CollectorJob) -> None:
        if job.mode == "download":
            cmd = [
                sys.executable,
                "-m",
                "src.download",
                *job.targets,
                "--limit",
                str(job.limit),
            ]
            if job.headless:
                cmd.append("--headless")
            if job.industry and job.industry != "all":
                cmd.extend(["--industry", job.industry])
            if job.destination in ("folder", "both"):
                cmd.extend(["-o", str(job.output_dir)])
            if job.destination == "both":
                cmd.append("--also-dataset")
        else:
            cmd = [
                sys.executable,
                "-m",
                "src.collect",
                job.query,
                "--limit",
                str(job.limit),
            ]
            if job.headless:
                cmd.append("--headless")
            if job.industry and job.industry != "all":
                cmd.extend(["--industry", job.industry])

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(config.ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
            )
            job.process = proc

            for line in iter(proc.stdout.readline, ""):
                if job.status == "cancelled":
                    break
                line_str = line.strip()
                if line_str:
                    job.progress_log.append(line_str)
                    job.last_line = line_str
                    if "✓" in line_str:
                        job.saved_count += 1
                    elif "Saved " in line_str and " new pins" in line_str:
                        try:
                            parts = line_str.split("Saved ")[1].split(" new pins")[0]
                            job.saved_count = int(parts.strip())
                        except Exception:
                            pass
                    elif "Saved to " in line_str and " pins" in line_str:
                        try:
                            parts = line_str.split("Saved to ")[1].split(" pins")[0].split(":")[-1]
                            job.saved_count = int(parts.strip())
                        except Exception:
                            pass

            proc.wait()
            if job.status != "cancelled":
                if proc.returncode == 0:
                    job.status = "done"
                    job.finished_at = datetime.now(timezone.utc).isoformat()
                    self.store.reload_if_needed()
                else:
                    job.status = "error"
                    job.finished_at = datetime.now(timezone.utc).isoformat()
                    candidates = [
                        l for l in job.progress_log
                        if any(w in l.lower() for w in ["not logged in", "error", "failed", "exit"])
                    ]
                    job.error = candidates[-1] if candidates else (job.last_line or f"Process exited with code {proc.returncode}")
        except Exception as e:
            job.status = "error"
            job.error = str(e)
            job.finished_at = datetime.now(timezone.utc).isoformat()


class ReferenceStore:
    """Manages cached pins with automatic reload when pins.jsonl is updated."""

    def __init__(self, repo_dir: Path):
        self.repo_dir = repo_dir
        self.pins_file = repo_dir / "index" / "pins.jsonl"
        self.stats_file = repo_dir / "index" / "stats.json"
        self._mtime: float = -1.0
        self._pins: list[dict[str, Any]] = []
        self._categories = load_categories()
        self._lock = threading.Lock()
        self.reload_if_needed()

    def reload_if_needed(self) -> None:
        if not self.pins_file.exists():
            with self._lock:
                self._pins = []
                self._mtime = -1.0
            return

        try:
            current_mtime = self.pins_file.stat().st_mtime
        except OSError:
            return

        if current_mtime != self._mtime:
            with self._lock:
                if current_mtime == self._mtime:
                    return
                pins: list[dict[str, Any]] = []
                try:
                    with open(self.pins_file, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                try:
                                    pins.append(json.loads(line))
                                except json.JSONDecodeError:
                                    continue
                    self._pins = pins
                    self._mtime = current_mtime
                except Exception as e:
                    print(f"[server] Error loading pins.jsonl: {e}", file=sys.stderr)

    @property
    def pins(self) -> list[dict[str, Any]]:
        self.reload_if_needed()
        with self._lock:
            return list(self._pins)

    def get_pin(self, pin_id: str) -> dict[str, Any] | None:
        self.reload_if_needed()
        with self._lock:
            for p in self._pins:
                if str(p.get("pin_id")) == str(pin_id):
                    return dict(p)
        return None

    def get_stats(self) -> dict[str, Any]:
        self.reload_if_needed()
        all_pins = self.pins

        labels = {k: v.get("label", k) for k, v in self._categories.get("industries", {}).items()}
        by_ind: dict[str, int] = {}
        by_fmt: dict[str, int] = {}
        queries: dict[str, int] = {}

        for p in all_pins:
            ind = p.get("industry") or "uncategorized"
            fmt = p.get("format") or "unknown"
            q = p.get("query") or ""

            by_ind[ind] = by_ind.get(ind, 0) + 1
            by_fmt[fmt] = by_fmt.get(fmt, 0) + 1
            if q:
                queries[q] = queries.get(q, 0) + 1

        by_ind = dict(sorted(by_ind.items(), key=lambda item: item[1], reverse=True))
        by_fmt = dict(sorted(by_fmt.items(), key=lambda item: item[1], reverse=True))
        queries = dict(sorted(queries.items(), key=lambda item: item[1], reverse=True))

        latest_time = all_pins[-1].get("collected_at") if all_pins else None

        return {
            "total_pins": len(all_pins),
            "updated_at": latest_time,
            "by_industry": by_ind,
            "industry_labels": labels,
            "by_format": by_fmt,
            "queries": queries,
        }

    def filter_pins(
        self,
        *,
        industry: str | None = None,
        format_tag: str | None = None,
        query: str | None = None,
        sort: str = "latest",
        page: int = 1,
        limit: int = 40,
    ) -> dict[str, Any]:
        self.reload_if_needed()
        pins = self.pins

        if industry and industry != "all":
            pins = [p for p in pins if p.get("industry") == industry]

        if format_tag and format_tag != "all":
            pins = [p for p in pins if p.get("format") == format_tag]

        if query:
            q_clean = query.strip().lower()
            if q_clean:
                tokens = q_clean.split()
                filtered = []
                for p in pins:
                    searchable = " ".join([
                        str(p.get("title") or ""),
                        str(p.get("caption") or ""),
                        str(p.get("description") or ""),
                        str(p.get("alt_text") or ""),
                        str(p.get("query") or ""),
                        str(p.get("pinner") or ""),
                        str(p.get("board") or ""),
                        str(p.get("industry") or ""),
                        str(p.get("format") or ""),
                        " ".join(p.get("style_tags") or []),
                    ]).lower()
                    if all(t in searchable for t in tokens):
                        filtered.append(p)
                pins = filtered

        def get_created_timestamp(p: dict[str, Any]) -> float:
            c = p.get("created_at")
            if not c:
                return 0.0
            try:
                from email.utils import parsedate_to_datetime
                return parsedate_to_datetime(c).timestamp()
            except Exception:
                return 0.0

        def get_collected_timestamp(p: dict[str, Any]) -> str:
            return str(p.get("collected_at") or "")

        def get_display_title(p: dict[str, Any]) -> str:
            t = (p.get("title") or "").strip()
            if not t:
                t = (p.get("query") or "").strip()
            if not t:
                t = (p.get("alt_text") or "").strip()
            return t.lower()

        if sort == "latest":
            pins = sorted(pins, key=get_collected_timestamp, reverse=True)
        elif sort == "oldest":
            pins = sorted(pins, key=get_collected_timestamp)
        elif sort in ("created_at_desc", "created_at"):
            pins = sorted(pins, key=get_created_timestamp, reverse=True)
        elif sort == "created_at_asc":
            pins = sorted(pins, key=get_created_timestamp)
        elif sort in ("title_asc", "title"):
            pins = sorted(pins, key=get_display_title)
        elif sort == "title_desc":
            pins = sorted(pins, key=get_display_title, reverse=True)
        else:
            pins = sorted(pins, key=get_collected_timestamp, reverse=True)

        total = len(pins)
        limit = max(1, min(limit, 100))
        page = max(1, page)
        start = (page - 1) * limit
        end = start + limit
        paged_pins = pins[start:end]
        total_pages = (total + limit - 1) // limit if total > 0 else 1

        return {
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
            "has_more": end < total,
            "pins": paged_pins,
        }


class GalleryRequestHandler(SimpleHTTPRequestHandler):
    """Handles API requests, dataset asset streaming, and SPA serving."""

    store: ReferenceStore
    collector_manager: CollectorManager

    def log_message(self, format: str, *args: Any) -> None:
        if len(args) > 1 and str(args[1]).startswith(("4", "5")):
            sys.stderr.write(f"[server] {args[0]} - {args[1]}\n")

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def do_GET(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query_params = urllib.parse.parse_qs(parsed_url.query)

        # 1. API: /api/stats
        if path == "/api/stats":
            self.send_json(self.store.get_stats())
            return

        # 2. API: /api/pins
        if path == "/api/pins":
            industry = query_params.get("industry", [None])[0]
            format_tag = query_params.get("format", [None])[0]
            search_query = query_params.get("q", [None])[0]
            sort = query_params.get("sort", ["latest"])[0]

            try:
                page = int(query_params.get("page", ["1"])[0])
            except ValueError:
                page = 1

            try:
                limit = int(query_params.get("limit", ["40"])[0])
            except ValueError:
                limit = 40

            data = self.store.filter_pins(
                industry=industry,
                format_tag=format_tag,
                query=search_query,
                sort=sort,
                page=page,
                limit=limit,
            )
            self.send_json(data)
            return

        # 3. API: /api/collect/status
        if path == "/api/collect/status":
            self.send_json(self.collector_manager.get_status())
            return

        # 4. API: /api/templates
        if path == "/api/templates":
            self.send_json({"templates": list_saved_templates(self.store.repo_dir)})
            return

        # 5. API: /api/config
        if path == "/api/config":
            self.send_json({
                "gemini_configured": bool(config.GEMINI_API_KEY),
                "gemini_model": config.GEMINI_MODEL,
                "classifier": config.CLASSIFIER,
            })
            return

        # 6. API: /api/analyze-pin (GET query param support)
        if path == "/api/analyze-pin":
            pin_id = query_params.get("pin_id", [None])[0]
            if not pin_id:
                self.send_json({"error": "pin_id query parameter is required"}, status=HTTPStatus.BAD_REQUEST)
                return
            pin = self.store.get_pin(pin_id)
            if not pin:
                self.send_json({"error": f"Pin {pin_id} not found"}, status=HTTPStatus.NOT_FOUND)
                return
            img_rel = pin.get("image_path", "")
            img_path = (self.store.repo_dir / img_rel) if img_rel else None
            try:
                analysis = analyze_pin(pin, img_path)
                self.send_json({"status": "ok", "analysis": analysis})
            except Exception as e:
                self.send_json({"error": str(e)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        # 7. API: /api/export-pin (Download image or ZIP package)
        if path == "/api/export-pin":
            pin_id = query_params.get("pin_id", [None])[0]
            fmt = query_params.get("format", ["zip"])[0].lower()
            if not pin_id:
                self.send_json({"error": "pin_id query parameter is required"}, status=HTTPStatus.BAD_REQUEST)
                return
            pin = self.store.get_pin(pin_id)
            if not pin:
                self.send_json({"error": f"Pin {pin_id} not found"}, status=HTTPStatus.NOT_FOUND)
                return

            img_rel = pin.get("image_path", "")
            img_path = (self.store.repo_dir / img_rel) if img_rel else None

            if fmt == "image":
                if img_path and img_path.exists():
                    self.serve_static_file(img_path, content_type="image/jpeg", cache_seconds=86400)
                else:
                    self.send_json({"error": "Image file not found"}, status=HTTPStatus.NOT_FOUND)
                return

            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                if img_path and img_path.exists():
                    zf.writestr(f"{pin_id}.jpg", img_path.read_bytes())

                caption_rel = pin.get("caption_path", "")
                caption_path = (self.store.repo_dir / caption_rel) if caption_rel else None
                caption_text = ""
                if caption_path and caption_path.exists():
                    caption_text = caption_path.read_text(encoding="utf-8")
                else:
                    caption_text = pin.get("caption") or pin.get("description") or pin.get("title") or ""
                zf.writestr(f"{pin_id}.txt", caption_text.encode("utf-8"))
                zf.writestr(f"{pin_id}.json", json.dumps(pin, indent=2, ensure_ascii=False).encode("utf-8"))

                try:
                    analysis = analyze_pin(pin, img_path)
                    spec_md = f"# Reference Pin {pin_id} — Design Spec\n\n"
                    spec_md += f"**Title**: {pin.get('title') or 'Untitled'}\n"
                    spec_md += f"**Industry**: {pin.get('industry')}\n"
                    spec_md += f"**Format**: {pin.get('format')}\n"
                    spec_md += f"**Pinterest URL**: {pin.get('pin_url')}\n\n"
                    spec_md += f"## Caption\n{caption_text}\n\n"
                    spec_md += f"## Palette\n{', '.join(analysis.get('palette', []))}\n\n"
                    presets = analysis.get('prompt_presets', {})
                    spec_md += f"## Midjourney v6.1 Prompt\n```\n{presets.get('midjourney', '')}\n```\n\n"
                    spec_md += f"## Ad Creative Template\n```\n{presets.get('ad_creative', '')}\n```\n"
                    zf.writestr(f"design_prompt_{pin_id}.md", spec_md.encode("utf-8"))
                except Exception:
                    pass

            zip_data = buf.getvalue()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", f'attachment; filename="pin_{pin_id}_package.zip"')
            self.send_header("Content-Length", str(len(zip_data)))
            self.end_headers()
            self.wfile.write(zip_data)
            return

        # 4. Serve dataset files: /dataset/...
        if path.startswith("/dataset/"):
            rel_path = urllib.parse.unquote(path.removeprefix("/dataset/")).lstrip("/\\")
            file_path = (self.store.repo_dir / "dataset" / rel_path).resolve()

            dataset_root = (self.store.repo_dir / "dataset").resolve()
            if not str(file_path).startswith(str(dataset_root)):
                self.send_error(HTTPStatus.FORBIDDEN, "Forbidden")
                return

            if not file_path.exists() or not file_path.is_file():
                self.send_error(HTTPStatus.NOT_FOUND, "File not found")
                return

            self.serve_static_file(file_path, cache_seconds=86400)
            return

        # 5. Web root: / or index.html
        if path in ("/", "/index.html"):
            index_path = WEB_DIR / "index.html"
            if index_path.exists():
                self.serve_static_file(index_path, content_type="text/html; charset=utf-8", cache_seconds=0)
            else:
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"<h1>Pinterest Reference Collector UI</h1><p>index.html not found.</p>")
            return

        # 6. Static web assets in src/web/
        safe_rel = urllib.parse.unquote(path.lstrip("/\\"))
        candidate = (WEB_DIR / safe_rel).resolve()
        if candidate.exists() and candidate.is_file() and str(candidate).startswith(str(WEB_DIR.resolve())):
            self.serve_static_file(candidate, cache_seconds=3600)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        if path == "/api/collect":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len) if content_len > 0 else b"{}"
            try:
                data = json.loads(body.decode("utf-8")) if body else {}
            except Exception:
                self.send_json({"error": "Invalid JSON body"}, status=HTTPStatus.BAD_REQUEST)
                return

            query = (data.get("query") or "").strip()
            if not query:
                self.send_json({"error": "Query cannot be empty"}, status=HTTPStatus.BAD_REQUEST)
                return

            try:
                limit = int(data.get("limit", 30))
            except ValueError:
                limit = 30

            industry = data.get("industry")
            headless = bool(data.get("headless", True))

            try:
                job = self.collector_manager.start_job(
                    query=query,
                    limit=limit,
                    industry=industry,
                    headless=headless,
                )
                self.send_json({"status": "started", "job": job.to_dict()}, status=HTTPStatus.ACCEPTED)
            except ValueError as e:
                self.send_json(
                    {"error": str(e), "current_job": self.collector_manager.get_status().get("job")},
                    status=HTTPStatus.CONFLICT,
                )
            return

        if path == "/api/download":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len) if content_len > 0 else b"{}"
            try:
                data = json.loads(body.decode("utf-8")) if body else {}
            except Exception:
                self.send_json({"error": "Invalid JSON body"}, status=HTTPStatus.BAD_REQUEST)
                return

            raw_targets = data.get("targets")
            if isinstance(raw_targets, str):
                targets = [line.strip() for line in raw_targets.splitlines() if line.strip()]
            elif isinstance(raw_targets, list):
                targets = [str(t).strip() for t in raw_targets if str(t).strip()]
            elif data.get("url"):
                targets = [str(data["url"]).strip()]
            elif data.get("query"):
                targets = [str(data["query"]).strip()]
            else:
                targets = []

            if not targets:
                self.send_json({"error": "At least one target (URL, Pin ID, or Board link) is required"}, status=HTTPStatus.BAD_REQUEST)
                return

            destination = data.get("destination", "dataset")
            output_dir = data.get("output_dir", "downloads")
            industry = data.get("industry")
            try:
                limit = int(data.get("limit", 30))
            except ValueError:
                limit = 30
            headless = bool(data.get("headless", True))

            try:
                job = self.collector_manager.start_job(
                    mode="download",
                    targets=targets,
                    destination=destination,
                    output_dir=output_dir,
                    industry=industry,
                    limit=limit,
                    headless=headless,
                )
                self.send_json({"status": "started", "job": job.to_dict()}, status=HTTPStatus.ACCEPTED)
            except ValueError as e:
                self.send_json(
                    {"error": str(e), "current_job": self.collector_manager.get_status().get("job")},
                    status=HTTPStatus.CONFLICT,
                )
            return

        if path == "/api/export-batch":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len) if content_len > 0 else b"{}"
            try:
                data = json.loads(body.decode("utf-8")) if body else {}
            except Exception:
                data = {}

            requested_ids = data.get("pin_ids")
            all_pins = self.store.pins
            if requested_ids and isinstance(requested_ids, list):
                target_ids = set(str(pid) for pid in requested_ids)
                export_pins = [p for p in all_pins if str(p.get("pin_id")) in target_ids]
            else:
                export_pins = all_pins

            if not export_pins:
                self.send_json({"error": "No pins available to export"}, status=HTTPStatus.NOT_FOUND)
                return

            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                manifest = []
                for p in export_pins[:500]:
                    pid = str(p.get("pin_id"))
                    ind = str(p.get("industry") or "uncategorized")
                    img_rel = p.get("image_path", "")
                    img_path = (self.store.repo_dir / img_rel) if img_rel else None
                    if img_path and img_path.exists():
                        zf.writestr(f"{ind}/{pid}.jpg", img_path.read_bytes())

                    caption_rel = p.get("caption_path", "")
                    caption_path = (self.store.repo_dir / caption_rel) if caption_rel else None
                    caption_text = ""
                    if caption_path and caption_path.exists():
                        caption_text = caption_path.read_text(encoding="utf-8")
                    else:
                        caption_text = p.get("caption") or p.get("description") or p.get("title") or ""
                    zf.writestr(f"{ind}/{pid}.txt", caption_text.encode("utf-8"))
                    manifest.append(p)

                zf.writestr("index.json", json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8"))

            zip_data = buf.getvalue()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", 'attachment; filename="pinterest_references_batch.zip"')
            self.send_header("Content-Length", str(len(zip_data)))
            self.end_headers()
            self.wfile.write(zip_data)
            return

        if path == "/api/collect/cancel":
            cancelled = self.collector_manager.cancel_job()
            self.send_json({"status": "cancelled" if cancelled else "no_active_job"})
            return

        if path == "/api/analyze-pin":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len) if content_len > 0 else b"{}"
            try:
                data = json.loads(body.decode("utf-8")) if body else {}
            except Exception:
                self.send_json({"error": "Invalid JSON body"}, status=HTTPStatus.BAD_REQUEST)
                return

            pin_id = str(data.get("pin_id") or "").strip()
            if not pin_id:
                self.send_json({"error": "pin_id is required"}, status=HTTPStatus.BAD_REQUEST)
                return

            pin = self.store.get_pin(pin_id)
            if not pin:
                self.send_json({"error": f"Pin {pin_id} not found"}, status=HTTPStatus.NOT_FOUND)
                return

            img_rel = pin.get("image_path", "")
            img_path = (self.store.repo_dir / img_rel) if img_rel else None
            force_gemini = bool(data.get("force_gemini", False))
            api_key = (data.get("api_key") or "").strip() or None

            try:
                analysis = analyze_pin(
                    pin=pin,
                    image_bytes_or_path=img_path,
                    force_gemini=force_gemini,
                    api_key=api_key,
                )
                self.send_json({"status": "ok", "analysis": analysis})
            except Exception as e:
                self.send_json({"error": str(e)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        if path == "/api/generate-prompt":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len) if content_len > 0 else b"{}"
            try:
                data = json.loads(body.decode("utf-8")) if body else {}
            except Exception:
                self.send_json({"error": "Invalid JSON body"}, status=HTTPStatus.BAD_REQUEST)
                return

            analysis = data.get("analysis")
            if not analysis:
                self.send_json({"error": "analysis payload is required"}, status=HTTPStatus.BAD_REQUEST)
                return

            custom = data.get("customizations", {})
            updated_creative = build_ad_creative_template(analysis, custom)
            templates = dict(analysis.get("prompt_templates", {}))
            templates["creative_ad"] = updated_creative

            self.send_json({"status": "ok", "prompt_templates": templates})
            return

        if path == "/api/templates":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len) if content_len > 0 else b"{}"
            try:
                data = json.loads(body.decode("utf-8")) if body else {}
            except Exception:
                self.send_json({"error": "Invalid JSON body"}, status=HTTPStatus.BAD_REQUEST)
                return

            if not data:
                self.send_json({"error": "Empty template data"}, status=HTTPStatus.BAD_REQUEST)
                return

            saved = save_template_record(self.store.repo_dir, data)
            self.send_json({"status": "saved", "template": saved}, status=HTTPStatus.CREATED)
            return

        if path == "/api/templates/delete":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len) if content_len > 0 else b"{}"
            try:
                data = json.loads(body.decode("utf-8")) if body else {}
            except Exception:
                self.send_json({"error": "Invalid JSON body"}, status=HTTPStatus.BAD_REQUEST)
                return

            template_id = data.get("id")
            if not template_id:
                self.send_json({"error": "Template id required"}, status=HTTPStatus.BAD_REQUEST)
                return

            ok = delete_template_record(self.store.repo_dir, template_id)
            self.send_json({"status": "deleted" if ok else "not_found"})
            return

        if path == "/api/config":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len) if content_len > 0 else b"{}"
            try:
                data = json.loads(body.decode("utf-8")) if body else {}
            except Exception:
                self.send_json({"error": "Invalid JSON body"}, status=HTTPStatus.BAD_REQUEST)
                return

            gemini_key = data.get("gemini_api_key")
            if gemini_key is not None:
                config.GEMINI_API_KEY = gemini_key.strip()
                if data.get("save_to_env"):
                    env_path = config.ROOT / ".env"
                    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
                    found = False
                    new_lines = []
                    for l in lines:
                        if l.startswith("GEMINI_API_KEY="):
                            new_lines.append(f"GEMINI_API_KEY={config.GEMINI_API_KEY}")
                            found = True
                        else:
                            new_lines.append(l)
                    if not found:
                        new_lines.append(f"GEMINI_API_KEY={config.GEMINI_API_KEY}")
                    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

            self.send_json({
                "status": "updated",
                "gemini_configured": bool(config.GEMINI_API_KEY),
                "gemini_model": config.GEMINI_MODEL,
            })
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_DELETE(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        if path.startswith("/api/templates/"):
            template_id = path.removeprefix("/api/templates/").strip()
            ok = delete_template_record(self.store.repo_dir, template_id)
            self.send_json({"status": "deleted" if ok else "not_found"})
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def send_json(self, data: Any, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(body)

    def serve_static_file(
        self,
        file_path: Path,
        content_type: str | None = None,
        cache_seconds: int = 86400,
    ) -> None:
        try:
            file_size = file_path.stat().st_size
            if not content_type:
                content_type, _ = mimetypes.guess_type(str(file_path))
                if not content_type:
                    content_type = "application/octet-stream"

            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(file_size))
            if cache_seconds > 0:
                self.send_header("Cache-Control", f"public, max-age={cache_seconds}")
            else:
                self.send_header("Cache-Control", "no-cache, must-revalidate")
            self.end_headers()

            with open(file_path, "rb") as f:
                while chunk := f.read(64 * 1024):
                    self.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, f"Error reading file: {e}")


def find_free_port(start_port: int = 8000, max_tries: int = 50) -> int:
    """Finds an available local port starting from start_port."""
    if start_port == 0:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    for port in range(start_port, start_port + max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return start_port


def create_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    repo_dir: Path | None = None,
) -> tuple[ThreadingHTTPServer, int]:
    repo = repo_dir or config.REPO_DIR
    store = ReferenceStore(repo)
    manager = CollectorManager(store)

    class CustomHandler(GalleryRequestHandler):
        pass

    CustomHandler.store = store
    CustomHandler.collector_manager = manager

    chosen_port = find_free_port(port)
    server = ThreadingHTTPServer((host, chosen_port), CustomHandler)
    actual_port = server.server_address[1]
    return server, actual_port


def main() -> None:
    parser = argparse.ArgumentParser(description="Pinterest Reference Collector Web UI")
    parser.add_argument("--host", default="127.0.0.1", help="Host address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Preferred port (default: 8000)")
    parser.add_argument("--open", action="store_true", help="Automatically open browser window")
    args = parser.parse_args()

    server, port = create_server(args.host, args.port)
    url = f"http://{args.host}:{port}"
    print("=" * 60)
    print(f"  Pinterest Reference Collector - UI Server")
    print(f"  URL: {url}")
    print(f"  Dataset: {config.REPO_DIR}")
    print("  Press Ctrl+C to stop the server.")
    print("=" * 60)

    if args.open:
        try:
            threading.Timer(0.6, lambda: webbrowser.open(url)).start()
        except Exception:
            pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[server] Shutting down.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
