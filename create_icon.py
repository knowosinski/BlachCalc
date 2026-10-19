from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parent
ICON_SOURCE = ROOT / "applogo.png"
ICON_OUTPUT = ROOT / "BlachCalc.ico"


def main() -> None:
    with Image.open(ICON_SOURCE) as source:
        logo = source.convert("RGBA")

    icon = Image.new("RGBA", (256, 256), "#173B63")
    draw = ImageDraw.Draw(icon)
    draw.rounded_rectangle((12, 36, 244, 220), radius=28, fill="white")
    logo.thumbnail((210, 132), Image.Resampling.LANCZOS)
    icon.alpha_composite(
        logo,
        ((icon.width - logo.width) // 2, 112 - logo.height // 2),
    )
    draw.rounded_rectangle((38, 225, 218, 240), radius=7, fill="#ED1B24")
    icon.save(
        ICON_OUTPUT,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )


if __name__ == "__main__":
    main()
