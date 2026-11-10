from __future__ import annotations

import base64
from io import BytesIO
from typing import Any

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_IMAGES_PER_GROQ_REQUEST = 2
MAX_IMAGE_DIMENSION = 768
JPEG_QUALITY = 65
SUPPORTED_IMAGE_TYPES = {"image/png", "image/jpeg"}


def prepare_images_for_analysis(
    attachments: list[dict[str, Any]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    prepared: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []

    for attachment in attachments:
        content_type = attachment.get("content_type")
        name = attachment.get("name")
        attachment_id = attachment.get("id")
        data = attachment.get("_data")
        if content_type not in SUPPORTED_IMAGE_TYPES or not isinstance(data, bytes):
            continue
        if len(prepared) >= MAX_IMAGES_PER_GROQ_REQUEST:
            skipped.append(
                {
                    "id": str(attachment_id or ""),
                    "name": str(name or "image attachment"),
                    "status": "not_analyzed",
                    "message": "Image analysis is limited to two images per request.",
                }
            )
            continue

        try:
            with Image.open(BytesIO(data)) as original:
                image = ImageOps.exif_transpose(original)
                if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
                    rgba = image.convert("RGBA")
                    background = Image.new("RGB", rgba.size, "white")
                    background.paste(rgba, mask=rgba.getchannel("A"))
                    image = background
                else:
                    image = image.convert("RGB")
                image.thumbnail(
                    (MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION),
                    Image.Resampling.LANCZOS,
                )
                output = BytesIO()
                image.save(output, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        except (
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
            OSError,
            UnidentifiedImageError,
            ValueError,
        ):
            skipped.append(
                {
                    "id": str(attachment_id or ""),
                    "name": str(name or "image attachment"),
                    "status": "not_analyzed",
                    "message": "Image decoding failed; image not analyzed.",
                }
            )
            continue
        prepared.append(
            {
                "id": str(attachment_id or ""),
                "name": str(name or "image attachment"),
                "content_type": "image/jpeg",
                "data_url": "data:image/jpeg;base64,"
                + base64.b64encode(output.getvalue()).decode("ascii"),
            }
        )

    return prepared, skipped
