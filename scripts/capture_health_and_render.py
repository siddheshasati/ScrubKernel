import requests
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

out = Path('docs')
out.mkdir(exist_ok=True)

url = 'http://127.0.0.1:8001/health'
try:
    r = requests.get(url, timeout=5)
    text = r.text
except Exception as e:
    text = f'Error contacting {url}: {e}'

# render text to image
img = Image.new('RGB', (900, 200), color=(255,255,255))
draw = ImageDraw.Draw(img)
try:
    font = ImageFont.load_default()
except Exception:
    font = None
draw.multiline_text((10,10), text, fill=(0,0,0), font=font)
img.save(out / 'screenshot.png')
print('Saved', out / 'screenshot.png')
