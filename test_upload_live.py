import requests
from PIL import Image
import io

img = Image.new("RGB", (32, 32), color=(255, 0, 0))
buf = io.BytesIO()
img.save(buf, format="PNG")
buf.seek(0)
files = {'file': ('test.png', buf, 'image/png')}
try:
    r = requests.post('http://127.0.0.1:5000/', files=files, timeout=20)
    print('STATUS', r.status_code)
    print(r.text[:4000])
except Exception as e:
    print('ERROR', e)
