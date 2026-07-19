"""kiroku アプリのアイコン（温かい地色＋白の太字「記」）を生成する。

使い方:
    ../.venv/bin/python make_icon.py         # icon_1024.png を生成
その後 .icns 化してアプリへ適用（README「アイコン」節参照）:
    for sz in 16 32 128 256 512; do
      sips -z $sz $sz icon_1024.png --out kiroku.iconset/icon_${sz}x${sz}.png
      sips -z $((sz*2)) $((sz*2)) icon_1024.png --out kiroku.iconset/icon_${sz}x${sz}@2x.png
    done
    cp icon_1024.png kiroku.iconset/icon_512x512@2x.png
    iconutil -c icns kiroku.iconset -o kiroku.icns
    cp kiroku.icns /Applications/kiroku.app/Contents/Resources/applet.icns
"""
from PIL import Image, ImageDraw, ImageFont

S = 1024
TOP = (176, 140, 82)   # #b08c52
BOT = (105, 82, 42)    # #69522a
FONT = "/System/Library/Fonts/ヒラギノ角ゴシック W8.ttc"
CHAR = "記"


def build() -> Image.Image:
    grad = Image.new("RGB", (S, S), TOP)
    px = grad.load()
    for y in range(S):
        t = y / (S - 1)
        px_row = tuple(int(TOP[i] + (BOT[i] - TOP[i]) * t) for i in range(3))
        for x in range(S):
            px[x, y] = px_row

    margin, radius = 84, 224
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [margin, margin, S - margin, S - margin], radius=radius, fill=255)

    icon = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    icon.paste(grad, (0, 0), mask)

    hl = Image.new("L", (S, S), 0)
    ImageDraw.Draw(hl).rounded_rectangle(
        [margin, margin, S - margin, margin + (S - 2 * margin) // 2],
        radius=radius, fill=40)
    white = Image.new("RGBA", (S, S), (255, 255, 255, 0))
    white.putalpha(Image.composite(hl, Image.new("L", (S, S), 0), mask))
    icon = Image.alpha_composite(icon, white)

    draw = ImageDraw.Draw(icon)
    font = ImageFont.truetype(FONT, 620)
    bbox = draw.textbbox((0, 0), CHAR, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx, ty = (S - tw) // 2 - bbox[0], (S - th) // 2 - bbox[1] - 8
    draw.text((tx + 8, ty + 10), CHAR, font=font, fill=(60, 45, 20, 120))
    draw.text((tx, ty), CHAR, font=font, fill=(255, 252, 245, 255))
    return icon


if __name__ == "__main__":
    build().save("icon_1024.png")
    print("saved icon_1024.png")
