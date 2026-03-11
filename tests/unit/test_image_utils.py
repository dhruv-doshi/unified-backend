import pytest
import io
from PIL import Image
from src.domain.analysis.image_utils import compute_histogram, create_thumbnail, validate_image
from src.core.exceptions import AppError


def _make_test_image(width: int = 100, height: int = 100) -> bytes:
    img = Image.new("RGB", (width, height), color=(128, 64, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_compute_histogram():
    data = _make_test_image()
    histogram = compute_histogram(data)
    assert "red" in histogram
    assert "green" in histogram
    assert "blue" in histogram
    assert "luminance" in histogram
    assert len(histogram["red"]) == 256


def test_create_thumbnail():
    data = _make_test_image(1000, 800)
    thumb = create_thumbnail(data)
    img = Image.open(io.BytesIO(thumb))
    assert img.width <= 400
    assert img.height <= 400


def test_validate_image_ok():
    data = _make_test_image()
    validate_image(data, "image/jpeg")  # Should not raise


def test_validate_image_too_large():
    large_data = b"x" * (21 * 1024 * 1024)
    with pytest.raises(AppError) as exc:
        validate_image(large_data, "image/jpeg")
    assert exc.value.code == "FILE_TOO_LARGE"


def test_validate_image_unsupported_format():
    data = _make_test_image()
    with pytest.raises(AppError) as exc:
        validate_image(data, "image/gif")
    assert exc.value.code == "UNSUPPORTED_FORMAT"
