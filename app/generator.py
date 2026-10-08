import os
from PIL import Image, ImageDraw, ImageFont

ASSETS_DIR = "assets"
MEDIA_DIR = "media"
TEMPLATE_PATH = os.path.join(ASSETS_DIR, "template.png")


def _font(size):
    """Built-in scalable font (needs Pillow >= 10.1), so no font file is required."""
    return ImageFont.load_default(size=size)


def _fit_font(draw, text, size, max_width):
    """Shrink the font until the text fits on the page."""
    while size > 16 and draw.textlength(text, font=_font(size)) > max_width:
        size -= 4
    return _font(size)


def ensure_template_exists():
    """Generates the blank template image if none is present."""
    os.makedirs(ASSETS_DIR, exist_ok=True)
    if not os.path.exists(TEMPLATE_PATH):
        img = Image.new("RGB", (800, 600), color=(250, 248, 240))
        draw = ImageDraw.Draw(img)
        # Gold decorative border
        draw.rectangle([(20, 20), (780, 580)], outline=(190, 150, 70), width=6)
        draw.text((400, 120), "CERTIFICATE OF COMPLETION", font=_font(44), fill=(30, 40, 60), anchor="mm")
        draw.text((400, 200), "This is proudly presented to:", font=_font(24), fill=(90, 90, 90), anchor="mm")
        img.save(TEMPLATE_PATH)


def generate_certificate(job_id: str, recipient_id: int, recipient_name: str) -> str:
    """Stamps recipient name onto template and writes file to media directory."""
    ensure_template_exists()

    job_dir = os.path.join(MEDIA_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)
    output_path = os.path.join(job_dir, f"{recipient_id}.png")

    img = Image.open(TEMPLATE_PATH).convert("RGB")
    draw = ImageDraw.Draw(img)

    # Stamp recipient name centered (font shrinks if the name is long)
    name = recipient_name.upper()
    draw.text((400, 300), name, font=_fit_font(draw, name, 56, 680), fill=(20, 20, 20), anchor="mm")
    draw.line([(150, 340), (650, 340)], fill=(190, 150, 70), width=3)
    draw.text((400, 400), "For completing the training program successfully.",
              font=_font(24), fill=(80, 80, 80), anchor="mm")

    img.save(output_path)
    return output_path
