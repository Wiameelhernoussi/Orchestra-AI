from __future__ import annotations

import re
import shutil
import warnings
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError

MAX_EVIDENCE_FILE_BYTES = 10 * 1024 * 1024
MAX_EVIDENCE_TOTAL_BYTES = 20 * 1024 * 1024
MAX_EVIDENCE_FILES = 5

_SUPPORTED_FILES = {
    ".pdf": ("application/pdf", lambda data: data.startswith(b"%PDF-")),
    ".png": ("image/png", lambda data: data.startswith(b"\x89PNG\r\n\x1a\n")),
    ".jpg": ("image/jpeg", lambda data: data.startswith(b"\xff\xd8\xff")),
    ".jpeg": ("image/jpeg", lambda data: data.startswith(b"\xff\xd8\xff")),
    ".webp": (
        "image/webp",
        lambda data: len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP",
    ),
}
_ATTACHMENT_ID_RE = re.compile(r"^[0-9a-f]{32}$")
_MAX_IMAGE_PIXELS = 40_000_000


def safe_display_filename(filename: str) -> str:
    name = filename.replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(character for character in name if character.isprintable())
    return name[:160] or "evidence-file"


def validate_evidence_file(
    filename: str,
    declared_content_type: str | None,
    data: bytes,
) -> dict[str, Any]:
    display_name = safe_display_filename(filename)
    extension = Path(display_name).suffix.casefold()
    supported = _SUPPORTED_FILES.get(extension)
    if supported is None:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Attach a PNG, JPEG, WebP, or PDF.",
        )
    expected_content_type, signature_check = supported
    if (
        declared_content_type
        and declared_content_type not in {expected_content_type, "application/octet-stream"}
    ):
        raise HTTPException(status_code=415, detail="File type does not match its filename.")
    if not signature_check(data):
        raise HTTPException(status_code=415, detail="File content does not match its type.")
    if not data:
        raise HTTPException(status_code=422, detail="Attached files cannot be empty.")
    if len(data) > MAX_EVIDENCE_FILE_BYTES:
        raise HTTPException(status_code=413, detail="Each attachment must be 10 MB or smaller.")
    if expected_content_type in {"image/png", "image/jpeg", "image/webp"}:
        expected_format = {
            "image/png": "PNG",
            "image/jpeg": "JPEG",
            "image/webp": "WEBP",
        }[expected_content_type]
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(data)) as image:
                    if (
                        image.format != expected_format
                        or image.width * image.height > _MAX_IMAGE_PIXELS
                    ):
                        raise ValueError("Image format or dimensions are invalid.")
                    image.verify()
        except (
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
            UnidentifiedImageError,
            OSError,
            ValueError,
        ) as exc:
            raise HTTPException(
                status_code=415,
                detail="File content does not match its type.",
            ) from exc
    return {
        "id": uuid4().hex,
        "name": display_name,
        "content_type": expected_content_type,
        "size_bytes": len(data),
        "inspection_status": "not_inspected_by_ai",
        "_data": data,
    }


def store_evidence_files(
    media_dir: str,
    evidence_id: str,
    attachments: list[dict[str, Any]],
) -> str | None:
    if not attachments:
        return None

    evidence_root = (Path(media_dir).expanduser().resolve() / "evidence").resolve()
    evidence_dir = (evidence_root / evidence_id).resolve()
    if not evidence_dir.is_relative_to(evidence_root):
        raise ValueError("Invalid evidence storage location.")
    evidence_dir.mkdir(parents=True, exist_ok=False)
    stored_paths: list[Path] = []
    try:
        for attachment in attachments:
            attachment_id = attachment.get("id")
            data = attachment.get("_data")
            if (
                not isinstance(attachment_id, str)
                or not _ATTACHMENT_ID_RE.fullmatch(attachment_id)
                or not isinstance(data, bytes)
            ):
                raise ValueError("Invalid attachment metadata.")
            path = evidence_dir / f"{attachment_id}.blob"
            with path.open("xb") as file:
                file.write(data)
            stored_paths.append(path)
    except (OSError, ValueError):
        try:
            shutil.rmtree(evidence_dir)
        except OSError as cleanup_error:
            raise OSError("Attachment storage failed and partial files could not be removed.") from cleanup_error
        raise
    return str(stored_paths[0])


def remove_evidence_files(media_dir: str, evidence_id: str) -> None:
    if not isinstance(evidence_id, str) or not re.fullmatch(
        r"[0-9a-fA-F-]{1,64}", evidence_id
    ):
        return
    evidence_root = (Path(media_dir).expanduser().resolve() / "evidence").resolve()
    evidence_dir = (evidence_root / evidence_id).resolve()
    if evidence_dir.is_relative_to(evidence_root) and evidence_dir.is_dir():
        shutil.rmtree(evidence_dir)


def resolve_evidence_file(
    media_dir: str,
    evidence_id: str,
    attachment_id: str,
) -> Path | None:
    if not _ATTACHMENT_ID_RE.fullmatch(attachment_id):
        return None
    evidence_root = (Path(media_dir).expanduser().resolve() / "evidence").resolve()
    evidence_dir = (evidence_root / evidence_id).resolve()
    if not evidence_dir.is_relative_to(evidence_root):
        return None
    file_path = (evidence_dir / f"{attachment_id}.blob").resolve()
    if file_path.parent != evidence_dir or not file_path.is_file():
        return None
    return file_path
