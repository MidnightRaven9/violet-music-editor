"""Generate launcher icons for Violet Music Editor (violet rounded square + music note)."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RES = Path(__file__).resolve().parent.parent / "res"

# Violet gradient endpoints
TOP = (167, 139, 250)     # #a78bfa
BOTTOM = (109, 40, 217)   # #6d28d9
NOTE = (255, 255, 255, 255)

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def make_icon(size: int, rounded: bool = True) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Vertical gradient background
    for y in range(size):
        t = y / max(1, size - 1)
        r = int(TOP[0] + (BOTTOM[0] - TOP[0]) * t)
        g = int(TOP[1] + (BOTTOM[1] - TOP[1]) * t)
        b = int(TOP[2] + (BOTTOM[2] - TOP[2]) * t)
        draw.line([(0, y), (size, y)], fill=(r, g, b, 255))

    # Mask to rounded rect / circle
    mask = Image.new("L", (size, size), 0)
    mdraw = ImageDraw.Draw(mask)
    if rounded:
        radius = int(size * 0.22)
        mdraw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    else:
        mdraw.ellipse([0, 0, size - 1, size - 1], fill=255)

    img.putalpha(mask)

    # Music note glyph
    note = "\u266a"  # ♪
    font_size = int(size * 0.62)
    font = load_font(font_size)
    bbox = draw.textbbox((0, 0), note, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    x = (size - w) / 2 - bbox[0]
    y = (size - h) / 2 - bbox[1]
    draw = ImageDraw.Draw(img)
    draw.text((x, y), note, font=font, fill=NOTE)

    return img


DENSITIES = {
    "mdpi": 48,
    "hdpi": 72,
    "xhdpi": 96,
    "xxhdpi": 144,
    "xxxhdpi": 192,
}


def main() -> None:
    for density, size in DENSITIES.items():
        out_dir = RES / f"mipmap-{density}"
        out_dir.mkdir(parents=True, exist_ok=True)
        make_icon(size, rounded=True).save(out_dir / "ic_launcher.png")
        make_icon(size, rounded=False).save(out_dir / "ic_launcher_round.png")
        print(f"generated {density} {size}x{size}")


if __name__ == "__main__":
    main()
