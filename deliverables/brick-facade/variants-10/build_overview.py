"""Compose the requested 2-column, 5-row overview from existing final PNGs."""
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
VARIANTS = json.loads((ROOT / 'generation-prompts.json').read_text())['variants']
REGULAR = '/System/Library/Fonts/Supplemental/Arial.ttf'
BOLD = '/System/Library/Fonts/Supplemental/Arial Bold.ttf'
FONT_TITLE = ImageFont.truetype(BOLD, 48)
FONT_NAME = ImageFont.truetype(BOLD, 30)
FONT_BODY = ImageFont.truetype(REGULAR, 23)
PAD, TILE_W, IMAGE_H, CAPTION_H, GAP = 32, 960, 720, 94, 24
HEADER, FOOTER = 142, 112
WIDTH = 2 * TILE_W + 2 * PAD + GAP
HEIGHT = HEADER + 5 * (IMAGE_H + CAPTION_H) + 4 * GAP + FOOTER
canvas = Image.new('RGB', (WIDTH, HEIGHT), '#f2eee8')
draw = ImageDraw.Draw(canvas)
draw.text((PAD, 28), '10 вариантов кирпичного фасада', font=FONT_TITLE, fill='#2f2924')
draw.text((PAD, 90), 'Один дом · один ракурс · тёмная кладка первого этажа сохраняется', font=FONT_BODY, fill='#65584b')

for index, variant in enumerate(VARIANTS):
    path = ROOT / f"{variant['id']}-{variant['slug']}.png"
    with Image.open(path) as opened:
        photo = opened.convert('RGB')
        if abs(photo.width / photo.height - 4 / 3) > 0.025:
            raise ValueError(f'Unexpected aspect ratio: {path}')
        photo.thumbnail((TILE_W, IMAGE_H), Image.Resampling.LANCZOS)
        x = PAD + (index % 2) * (TILE_W + GAP)
        y = HEADER + (index // 2) * (IMAGE_H + CAPTION_H + GAP)
        draw.rectangle((x, y, x + TILE_W - 1, y + IMAGE_H + CAPTION_H - 1), fill='white')
        canvas.paste(photo, (x + (TILE_W - photo.width) // 2, y + (IMAGE_H - photo.height) // 2))
        draw.text((x + 18, y + IMAGE_H + 13), f"{variant['id']}  {variant['name']}", font=FONT_NAME, fill='#2f2924')
        draw.text((x + 18, y + IMAGE_H + 53), variant['description'], font=FONT_BODY, fill='#65584b')

draw.text((PAD, HEIGHT - 82), 'Концепции: цвета и доли кирпичей приблизительные.', font=FONT_BODY, fill='#65584b')
draw.text((PAD, HEIGHT - 46), 'Тёмный первый этаж по всему периметру — предложенное завершение кладки по фото.', font=FONT_BODY, fill='#65584b')
canvas.save(ROOT / 'overview.png', optimize=True)
print(f'Saved overview.png: {WIDTH} × {HEIGHT}, {len(VARIANTS)} variants')
