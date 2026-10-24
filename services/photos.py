"""Recipe photos: check and resize an upload with Pillow, save and delete the files.

Errors are translation keys, like in services/forms.py.
"""

import io
import uuid

from PIL import Image, ImageOps, UnidentifiedImageError

import config

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


class PhotoError(Exception):
    def __init__(self, key):
        super().__init__(key)
        self.key = key


def process_photo(data, max_side=config.PHOTO_MAX_SIDE, max_bytes=config.MAX_PHOTO_BYTES):
    """Uploaded file bytes -> JPEG bytes, turned upright (phone EXIF) and fitted in max_side px.

    Raises PhotoError for a file that is too big, not an image, or not jpg/png/webp.
    """
    if len(data) > max_bytes:
        raise PhotoError("recipes.error_photo_too_large")
    try:
        with Image.open(io.BytesIO(data)) as img:
            if img.format not in ALLOWED_FORMATS:
                raise PhotoError("recipes.error_photo_type")
            img = ImageOps.exif_transpose(img)
            img.thumbnail((max_side, max_side))
            if img.mode != "RGB":
                # Transparent parts become white rather than black
                img = img.convert("RGBA")
                background = Image.new("RGB", img.size, "white")
                background.paste(img, mask=img.getchannel("A"))
                img = background
            out = io.BytesIO()
            img.save(out, "JPEG", quality=85)
            return out.getvalue()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as e:
        raise PhotoError("recipes.error_photo_type") from e


def save_photo(images_dir, jpeg):
    """Write JPEG bytes under a random file name and return that name."""
    filename = f"{uuid.uuid4().hex}.jpg"
    (images_dir / filename).write_bytes(jpeg)
    return filename


def delete_photo(images_dir, filename):
    """Delete a saved photo; a file that is already gone is fine."""
    if filename:
        (images_dir / filename).unlink(missing_ok=True)
