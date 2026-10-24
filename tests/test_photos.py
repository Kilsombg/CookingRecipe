import io

import pytest
from PIL import Image

from services.photos import PhotoError, delete_photo, process_photo, save_photo


def image_bytes(size=(100, 50), fmt="PNG", mode="RGB", color="red", exif=None):
    out = io.BytesIO()
    img = Image.new(mode, size, color)
    img.save(out, fmt, **({"exif": exif} if exif else {}))
    return out.getvalue()


def open_jpeg(data):
    img = Image.open(io.BytesIO(data))
    assert img.format == "JPEG"
    return img


@pytest.mark.parametrize("fmt", ["PNG", "JPEG", "WEBP"])
def test_accepted_formats_become_jpeg(fmt):
    assert open_jpeg(process_photo(image_bytes(fmt=fmt))).size == (100, 50)


def test_large_photo_is_resized_keeping_its_shape():
    img = open_jpeg(process_photo(image_bytes(size=(4000, 3000)), max_side=1600))
    assert img.size == (1600, 1200)


def test_small_photo_is_not_enlarged():
    assert open_jpeg(process_photo(image_bytes(size=(300, 200)))).size == (300, 200)


def test_phone_rotation_is_applied():
    exif = Image.Exif()
    exif[0x0112] = 6  # orientation: rotate 90° clockwise to show
    img = open_jpeg(process_photo(image_bytes(size=(200, 100), fmt="JPEG", exif=exif)))
    assert img.size == (100, 200)


def test_transparency_becomes_white():
    img = open_jpeg(process_photo(image_bytes(mode="RGBA", color=(0, 0, 0, 0))))
    assert all(channel > 240 for channel in img.getpixel((50, 25)))


@pytest.mark.parametrize("data", [b"not an image", b"", image_bytes(fmt="GIF"), image_bytes(fmt="BMP")],
                         ids=["text", "empty", "gif", "bmp"])
def test_other_files_are_rejected(data):
    with pytest.raises(PhotoError) as e:
        process_photo(data)
    assert e.value.key == "recipes.error_photo_type"


def test_too_large_file_is_rejected():
    with pytest.raises(PhotoError) as e:
        process_photo(image_bytes(), max_bytes=10)
    assert e.value.key == "recipes.error_photo_too_large"


def test_save_and_delete(tmp_path):
    filename = save_photo(tmp_path, b"jpeg")
    assert filename.endswith(".jpg") and len(filename) == 36
    assert (tmp_path / filename).read_bytes() == b"jpeg"
    assert save_photo(tmp_path, b"jpeg") != filename

    delete_photo(tmp_path, filename)
    assert not (tmp_path / filename).exists()
    delete_photo(tmp_path, filename)  # already gone: no error
    delete_photo(tmp_path, None)
