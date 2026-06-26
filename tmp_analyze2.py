import re

with open(r'C:\Users\Administrator\AppData\Local\Temp\gaokao_henan.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Find all script src
for m in re.finditer(r'src=["\']([^"\']+\.js[^"\']*)["\']', content):
    src = m.group(1)
    if 'config' not in src and 'parser' not in src and 'captcha' not in src:
        print(src)
