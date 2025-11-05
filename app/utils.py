from __future__ import annotations

import mimetypes
import os
import sys
import platform
import uuid
from datetime import datetime
from pathlib import Path
from typing import Iterable, List


def _app_base_dir() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(getattr(sys, '_MEIPASS', Path.cwd()))
    return Path(__file__).resolve().parent.parent


def _user_data_dir() -> Path:
    if platform.system() == 'Windows':
        base = os.environ.get('LOCALAPPDATA') or (Path.home() / 'AppData' / 'Local')
        return Path(base) / 'KomodoHub'
    base = os.environ.get('XDG_DATA_HOME') or (Path.home() / '.local' / 'share')
    return Path(base) / 'komodohub'


BASE_DIR = _app_base_dir()
# For frozen app, write media to user data directory; else use repo media folder
if getattr(sys, 'frozen', False):
    MEDIA_ROOT = _user_data_dir() / 'media'
else:
    MEDIA_ROOT = BASE_DIR / 'media'

UPLOADS_DIR = MEDIA_ROOT / "uploads"

ALLOWED_MIME = {"image/jpeg", "image/png"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


def ensure_media_dirs() -> None:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def save_upload(file_obj, subdir: str = "") -> str:
    ensure_media_dirs()
    # Validate content type and size
    content_type = file_obj.content_type or mimetypes.guess_type(file_obj.filename)[0]
    if content_type not in ALLOWED_MIME:
        raise ValueError("Unsupported file type")

    contents = file_obj.file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise ValueError("File too large")

    dt = datetime.utcnow()
    folder = UPLOADS_DIR / dt.strftime("%Y/%m")
    if subdir:
        folder = folder / subdir
    folder.mkdir(parents=True, exist_ok=True)

    ext = os.path.splitext(file_obj.filename)[1].lower()
    name = f"{uuid.uuid4().hex}{ext}"
    path = folder / name
    with open(path, "wb") as f:
        f.write(contents)

    rel_path = path.relative_to(MEDIA_ROOT).as_posix()
    return rel_path


def join_paths(paths: Iterable[str]) -> str:
    return ",".join(p for p in paths if p)


def split_paths(path_str: str | None) -> List[str]:
    if not path_str:
        return []
    return [p for p in path_str.split(",") if p]


def delete_media(rel_path: str) -> None:
    try:
        target = (MEDIA_ROOT / rel_path).resolve()
        root = MEDIA_ROOT.resolve()
        # safety: ensure target under media root
        if str(target).startswith(str(root)) and target.is_file():
            target.unlink(missing_ok=True)
    except Exception:
        # best-effort deletion; ignore failures
        pass


def delete_media_list(paths: Iterable[str]) -> None:
    for p in paths:
        delete_media(p)
