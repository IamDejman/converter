"""Image resize/compress and Base64 conversion logic."""
import base64
import io

from PIL import Image


def resize_image(
    image_bytes: bytes,
    width: int | None = None,
    height: int | None = None,
    quality: int = 85,
    fmt: str = "JPEG",
) -> bytes:
    """Resize and/or compress an image. Returns raw bytes."""
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode in ("RGBA", "P") and fmt.upper() == "JPEG":
        img = img.convert("RGB")

    if width and height:
        img = img.resize((width, height), Image.LANCZOS)
    elif width:
        ratio = width / img.width
        img = img.resize((width, int(img.height * ratio)), Image.LANCZOS)
    elif height:
        ratio = height / img.height
        img = img.resize((int(img.width * ratio), height), Image.LANCZOS)

    buf = io.BytesIO()
    save_kwargs: dict = {"format": fmt, "optimize": True}
    if fmt.upper() in ("JPEG", "WEBP"):
        save_kwargs["quality"] = quality
    img.save(buf, **save_kwargs)
    return buf.getvalue()


def image_info(image_bytes: bytes) -> dict:
    """Return basic info about an image."""
    img = Image.open(io.BytesIO(image_bytes))
    return {"width": img.width, "height": img.height, "format": img.format, "mode": img.mode}


def image_to_base64(image_bytes: bytes, mime_type: str = "image/png") -> str:
    """Encode image bytes as a data-URI base64 string."""
    b64 = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime_type};base64,{b64}"


def base64_to_image(data: str) -> tuple[bytes, str]:
    """Decode a data-URI or raw base64 string. Returns (bytes, mime_type)."""
    if data.startswith("data:"):
        header, b64 = data.split(",", 1)
        mime = header.split(";")[0].replace("data:", "")
    else:
        b64 = data
        mime = "image/png"
    return base64.b64decode(b64), mime
