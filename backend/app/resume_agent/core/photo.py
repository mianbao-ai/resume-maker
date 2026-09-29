"""Bounded, embedded raster photos shared by resume exports (no remote fetching)."""
import base64
import binascii
from io import BytesIO

from PIL import Image, ImageOps


def photo_bytes(value):
    if not isinstance(value, str) or len(value) > 2_000_000:
        return None
    if not value.startswith(('data:image/jpeg;base64,', 'data:image/png;base64,', 'data:image/webp;base64,')):
        return None
    try:
        raw = base64.b64decode(value.split(',', 1)[1], validate=True)
        with Image.open(BytesIO(raw)) as source:
            if source.width * source.height > 4_000_000:
                return None
            photo = ImageOps.fit(ImageOps.exif_transpose(source).convert('RGB'), (600, 600))
            output = BytesIO()
            photo.save(output, format='JPEG', quality=88)
            return output.getvalue()
    except (ValueError, OSError, binascii.Error, Image.DecompressionBombError):
        return None
