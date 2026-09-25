import asyncio
import base64
import json
import logging
import mimetypes
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

try:
    from site_config import (
        GITHUB_BRANCH,
        GITHUB_OWNER,
        GITHUB_REPO,
        GITHUB_TOKEN,
        SHOW_FULL_STUDENT_NAMES,
    )
except Exception:
    GITHUB_BRANCH = "main"
    GITHUB_OWNER = ""
    GITHUB_REPO = ""
    GITHUB_TOKEN = ""
    SHOW_FULL_STUDENT_NAMES = False

LOGGER = logging.getLogger(__name__)
_API = "https://api.github.com"
_LOCK = asyncio.Lock()


def _headers():
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "X-GitHub-Api-Version": "2026-03-10",
        "User-Agent": "sofi-ollohyor-site-sync",
        "Content-Type": "application/json",
    }


def _request(method, url, payload=None):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=_headers(), method=method)
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(body)
        except Exception:
            detail = {"message": body}
        return exc.code, detail


def _repo_file_info(path):
    url = f"{_API}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{urllib.parse.quote(path, safe='/')}?ref={urllib.parse.quote(GITHUB_BRANCH)}"
    status, body = _request("GET", url)
    if status == 200 and isinstance(body, dict):
        return body
    if status == 404:
        return None
    raise RuntimeError(f"GitHub GET {path}: {status} {body}")


def _put_file(path, content_bytes, message, *, binary=False):
    encoded = base64.b64encode(content_bytes).decode("ascii")
    url = f"{_API}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{urllib.parse.quote(path, safe='/')}"

    for attempt in range(3):
        info = _repo_file_info(path)
        payload = {
            "message": message,
            "content": encoded,
            "branch": GITHUB_BRANCH,
        }
        if info and info.get("sha"):
            payload["sha"] = info["sha"]
        status, body = _request("PUT", url, payload)
        if status in (200, 201):
            return body
        if status == 409 and attempt < 2:
            continue
        raise RuntimeError(f"GitHub PUT {path}: {status} {body}")
    raise RuntimeError(f"GitHub PUT {path}: conflict")


def _public_name(full_name):
    full_name = (full_name or "").strip()
    if SHOW_FULL_STUDENT_NAMES:
        return full_name
    parts = full_name.split()
    if not parts:
        return "O‘quvchi"
    if len(parts) == 1:
        return parts[0]
    return parts[0] + " " + " ".join((p[0].upper() + ".") for p in parts[1:] if p)


def _local_media_path(base_dir: Path, value):
    prefix = "LOCALFILE::"
    if not isinstance(value, str) or not value.startswith(prefix):
        return None
    rel = value[len(prefix):]
    path = base_dir / Path(rel)
    return path if path.exists() and path.is_file() else None


def _build_data(db_path: Path, base_dir: Path):
    import sqlite3

    con = sqlite3.connect(str(db_path), timeout=30)
    con.row_factory = sqlite3.Row
    try:
        teachers = []
        teacher_media = []
        for r in con.execute("SELECT * FROM teachers ORDER BY id ASC").fetchall():
            item = {
                "id": r["id"],
                "name": r["full_name"] or "",
                "subject": r["subject"] or "",
                "experience": r["experience"] or "",
                "education": r["education"] or "",
                "certificates": r["certificates"] or "",
                "achievements": r["achievements"] or "",
                "results": r["results"] or "",
                "description": r["description"] or "",
                "photo": "",
            }
            p = _local_media_path(base_dir, r["photo_file_id"])
            if p:
                site_path = f"site_media/teachers/{p.name}"
                item["photo"] = site_path
                teacher_media.append((site_path, p))
            teachers.append(item)

        ranking = []
        # Keep only public ranking fields. Telegram IDs, phone numbers and addresses are never exported.
        for r in con.execute("""
            SELECT full_name, class_name, score
            FROM users
            ORDER BY score DESC, full_name ASC
            LIMIT 50
        """).fetchall():
            ranking.append({
                "name": _public_name(r["full_name"]),
                "class_name": r["class_name"] or "",
                "score": int(r["score"] or 0),
            })

        stats = {
            "students": int(con.execute("SELECT COUNT(*) FROM students").fetchone()[0]),
            "teachers": int(con.execute("SELECT COUNT(*) FROM teachers").fetchone()[0]),
            "subjects": int(con.execute("SELECT COUNT(*) FROM subjects").fetchone()[0]),
            "books": int(con.execute("SELECT COUNT(*) FROM books").fetchone()[0]),
        }

        data = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "stats": stats,
            "teachers": teachers,
            "ranking": ranking,
        }
        return data, teacher_media
    finally:
        con.close()


async def sync_site_data(db_path, base_dir):
    """SQLite'dagi public ma'lumotlarni GitHub Pages repo'siga joylaydi."""
    if not (GITHUB_TOKEN and GITHUB_OWNER and GITHUB_REPO):
        return False

    async with _LOCK:
        try:
            data, media = await asyncio.to_thread(_build_data, Path(db_path), Path(base_dir))
            for site_path, local_path in media:
                raw = await asyncio.to_thread(local_path.read_bytes)
                await asyncio.to_thread(
                    _put_file,
                    site_path,
                    raw,
                    f"Sync teacher photo: {local_path.name}",
                    binary=True,
                )

            raw_json = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
            await asyncio.to_thread(
                _put_file,
                "data.json",
                raw_json,
                "Sync live school data",
            )
            LOGGER.info("Sayt ma'lumotlari GitHub Pages'ga yangilandi.")
            return True
        except Exception:
            LOGGER.exception("Sayt ma'lumotlarini GitHub'ga yuborishda xato")
            return False
