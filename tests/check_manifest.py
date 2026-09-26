#!/usr/bin/env python3
"""Verify the distributable tree, hotkeys, wallpaper and portable references."""
import hashlib,json,re,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'apps/orbit'))
from settings_data import ShortcutFile
assert set(p.name for p in (root/'backgrounds').iterdir())=={'tokyo.png'}
assert hashlib.sha256((root/'backgrounds/tokyo.png').read_bytes()).hexdigest()=='a017bb425a0c09dc598a3ce8b3f551cd9e64b91de61e1ecbd8b20a29db54cac2'
assert json.loads((root/'manifests/mason.json').read_text())==json.loads((root/'home/.config/nvim/mason-lock.json').read_text())
plugins=json.loads((root/'manifests/plugins.json').read_text())
lock=json.loads((root/'home/.config/nvim/lazy-lock.json').read_text())
assert {n:p['commit'] for n,p in plugins.items()}=={n:p['commit'] for n,p in lock.items()}
assert not ShortcutFile(root/'home/.config/sxhkd/sxhkdrc').conflicts()
for name,artifact in json.loads((root/'manifests/artifacts.json').read_text()).items():
 assert artifact['url'].startswith('https://'),name
 assert re.fullmatch('[a-f0-9]{64}',artifact['sha256']),name
for base in ('home','apps','assets','backgrounds'):
 for p in (root/base).rglob('*'):
  if '__pycache__' in p.parts:continue
  if p.is_symlink():
   assert not p.readlink().is_absolute(),str(p)
   assert p.exists(),str(p)
  if p.is_file() and p.suffix in ('.py','.sh','.lua','.ini','.toml'):
   text=p.read_text()
   assert not re.search(r'/home/nicolas|~/proyects/|\.local/opt/',text),str(p)
   # A read-only import of the old color history is not a runtime dependency.
   if p == root/'apps/orbit/color_window.py':
    text=text.replace("Path.home()/'.config/bspwm/rofi/data/colors.txt'",'LEGACY_COLOR_DATA')
   assert not re.search(r'\brofi(?:\s|/|-)',text,re.I),str(p)
  assert p.suffix not in ('.sqlite3','.db'),str(p)
print('MANIFEST_OK: one wallpaper, matching tool locks, no conflicting shortcuts or personal paths')
