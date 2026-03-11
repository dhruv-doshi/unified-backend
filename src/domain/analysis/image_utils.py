import io
from typing import Any
import exifread
from PIL import Image
import numpy as np
from src.core.logging import get_logger
from src.core.exceptions import AppError

logger = get_logger(__name__)

SUPPORTED_FORMATS = {"image/jpeg", "image/png", "image/webp", "image/heic"}
MAX_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB


def validate_image(data: bytes, content_type: str) -> None:
    if len(data) > MAX_SIZE_BYTES:
        raise AppError("Image exceeds 20MB limit", "FILE_TOO_LARGE", 413)
    if content_type not in SUPPORTED_FORMATS:
        raise AppError(
            "Unsupported format. Allowed: JPEG, PNG, WebP, HEIC",
            "UNSUPPORTED_FORMAT",
            415,
        )


def extract_exif(data: bytes) -> dict[str, Any]:
    try:
        tags = exifread.process_file(io.BytesIO(data), details=False)
        meta: dict[str, Any] = {}

        def tag_str(key: str) -> str | None:
            v = tags.get(key)
            return str(v) if v else None

        meta["make"] = tag_str("Image Make")
        meta["model"] = tag_str("Image Model")
        meta["lens"] = tag_str("EXIF LensModel")
        meta["focalLength"] = tag_str("EXIF FocalLength")
        meta["aperture"] = tag_str("EXIF FNumber")
        meta["shutterSpeed"] = tag_str("EXIF ExposureTime")
        meta["iso"] = tag_str("EXIF ISOSpeedRatings")
        meta["exposureMode"] = tag_str("EXIF ExposureMode")
        meta["whiteBalance"] = tag_str("EXIF WhiteBalance")
        meta["flash"] = tag_str("EXIF Flash")
        meta["dateTaken"] = tag_str("EXIF DateTimeOriginal")

        # GPS
        gps_lat = tags.get("GPS GPSLatitude")
        gps_lon = tags.get("GPS GPSLongitude")
        if gps_lat and gps_lon:

            def to_decimal(values) -> float:
                d, m, s = [float(str(v)) for v in values.values]
                return d + m / 60 + s / 3600

            meta["gps"] = {
                "lat": to_decimal(gps_lat),
                "lng": to_decimal(gps_lon),
            }

        # Image dimensions from PIL
        try:
            img = Image.open(io.BytesIO(data))
            meta["width"] = img.width
            meta["height"] = img.height
            meta["format"] = img.format
        except Exception:
            pass

        meta["fileSize"] = len(data)

        # Remove None values
        return {k: v for k, v in meta.items() if v is not None}
    except Exception as e:
        logger.warning("exif_extraction_failed", error=str(e))
        return {"fileSize": len(data)}


def compute_histogram(data: bytes) -> dict[str, list[int]]:
    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
        arr = np.array(img)

        red = np.histogram(arr[:, :, 0], bins=256, range=(0, 256))[0].tolist()
        green = np.histogram(arr[:, :, 1], bins=256, range=(0, 256))[0].tolist()
        blue = np.histogram(arr[:, :, 2], bins=256, range=(0, 256))[0].tolist()

        lum = (0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]).astype(np.uint8)
        luminance = np.histogram(lum, bins=256, range=(0, 256))[0].tolist()

        return {"red": red, "green": green, "blue": blue, "luminance": luminance}
    except Exception as e:
        logger.error("histogram_computation_failed", error=str(e))
        return {"red": [], "green": [], "blue": [], "luminance": []}


def create_thumbnail(data: bytes) -> bytes:
    img = Image.open(io.BytesIO(data))
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    img.thumbnail((400, 400), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()
