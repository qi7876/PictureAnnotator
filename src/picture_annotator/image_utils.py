from __future__ import annotations

import struct
from pathlib import Path


def get_image_size(path: Path) -> tuple[int, int]:
    """
    Returns (width, height) for PNG/JPEG.

    Prefers Pillow if available. Falls back to minimal header parsing for PNG/JPEG.
    """
    try:
        from PIL import Image  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        return _get_image_size_without_pillow(path)

    with Image.open(path) as im:
        w, h = im.size
    return int(w), int(h)


def _get_image_size_without_pillow(path: Path) -> tuple[int, int]:
    with path.open("rb") as f:
        header = f.read(32)

    # PNG signature + IHDR width/height
    if header.startswith(b"\x89PNG\r\n\x1a\n") and b"IHDR" in header[:24]:
        # PNG: signature(8) length(4) type(4) data(13...)
        with path.open("rb") as f:
            f.read(8)
            length = struct.unpack(">I", f.read(4))[0]
            ctype = f.read(4)
            if ctype != b"IHDR":
                raise ValueError(f"Unsupported PNG layout: {path}")
            data = f.read(length)
        w, h = struct.unpack(">II", data[:8])
        return int(w), int(h)

    # JPEG: parse markers until SOFn
    if header[:2] == b"\xff\xd8":
        return _get_jpeg_size(path)

    raise ValueError(f"Unsupported image format (install Pillow to support more): {path}")


def _get_jpeg_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as f:
        if f.read(2) != b"\xff\xd8":
            raise ValueError(f"Not a JPEG: {path}")
        while True:
            marker_prefix = f.read(1)
            if marker_prefix != b"\xff":
                raise ValueError(f"Invalid JPEG marker: {path}")
            marker = f.read(1)
            # Skip fill bytes
            while marker == b"\xff":
                marker = f.read(1)
            if marker in {b"\xd8", b"\xd9"}:
                continue
            length_bytes = f.read(2)
            if len(length_bytes) != 2:
                raise ValueError(f"Truncated JPEG: {path}")
            (segment_length,) = struct.unpack(">H", length_bytes)
            if segment_length < 2:
                raise ValueError(f"Invalid JPEG segment length: {path}")
            if b"\xc0" <= marker <= b"\xcf" and marker not in {b"\xc4", b"\xc8", b"\xcc"}:
                # SOF segment: [precision(1), height(2), width(2), ...]
                data = f.read(5)
                if len(data) != 5:
                    raise ValueError(f"Truncated JPEG SOF: {path}")
                _, h, w = struct.unpack(">BHH", data)
                return int(w), int(h)
            # Skip rest of the segment
            f.seek(segment_length - 2, 1)

