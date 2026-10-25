#!/usr/bin/env python3
"""Verify the distributable tree, wallpapers and portable references."""
import hashlib,json,re,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'apps/wysun'))
backgrounds=root/'assets/backgrounds'
assert set(p.name for p in backgrounds.iterdir())=={'purple-abstract-3840x3840-27445.jpg'}
assert hashlib.sha256((backgrounds/'purple-abstract-3840x3840-27445.jpg').read_bytes()).hexdigest()=='aeb9c5a195534fb47c7de1704a277a77f7a598ba0cee8d26b140e9f8991fc214'
themes=json.loads((root/'manifests/themes.json').read_text())
assert set(themes)=={'material-you'}
for theme in themes.values():
 assert (backgrounds/theme['wallpaper']).is_file()
 if theme.get('archive'):assert hashlib.sha256((root/theme['archive']).read_bytes()).hexdigest()==theme['sha256']
assert json.loads((root/'manifests/mason.json').read_text())==json.loads((root/'config/.config/nvim/mason-lock.json').read_text())
plugins=json.loads((root/'manifests/plugins.json').read_text())
lock=json.loads((root/'config/.config/nvim/lazy-lock.json').read_text())
assert {n:p['commit'] for n,p in plugins.items()}=={n:p['commit'] for n,p in lock.items()}
assert not (root/'config/.config/sxhkd').exists(),'the X11 shortcut configuration must not return'
assert not (root/'config/.config/bspwm').exists(),'the X11 desktop configuration must not return'
assert not (root/'apps/wysun').joinpath('polybar.ini').exists()
for name,artifact in json.loads((root/'manifests/artifacts.json').read_text()).items():
 assert artifact['url'].startswith('https://'),name
 assert re.fullmatch('[a-f0-9]{64}',artifact['sha256']),name
for base in ('config','apps','bin','assets'):
 for p in (root/base).rglob('*'):
  if '__pycache__' in p.parts:continue
  if p.is_symlink():
   assert not p.readlink().is_absolute(),str(p)
   assert p.exists(),str(p)
  if p.is_file() and p.suffix in ('.py','.sh','.lua','.ini','.toml'):
   text=p.read_text()
   assert not re.search(r'/home/nicolas|~/proyects/|\.local/opt/',text),str(p)
   assert not re.search(r'\brofi(?:\s|/|-)',text,re.I),str(p)
  assert p.suffix not in ('.sqlite3','.db'),str(p)
runtime=json.loads((root/'manifests/runtime.json').read_text())
for name,source in runtime['sources'].items():
 assert source['url'].startswith('https://'),name
 assert re.fullmatch('[a-f0-9]{40}',source.get('commit','0'*40)) and re.fullmatch('[a-f0-9]{64}',source.get('sha256','0'*64)),name
assert re.fullmatch(r'\d+\.\d+\.\d+',runtime['qt']['version'])
assert not any('caelestia' in str(p).lower() for p in (root/'apps/shell').rglob('*') if p.name not in ('UPSTREAM.json','LICENSE','THIRD_PARTY.md')),'shell paths must not use the former project name'
print('MANIFEST_OK: one Material You profile with its default wallpaper, matching tool locks, no conflicting shortcuts or personal paths')

assert (root/'bin/orbit-tools').is_file()
assert not (root/'scripts').exists()
for p in (root/'apps/tools').rglob('*'):
 assert p.name not in ('accounts.json','.rezets','uploads'),str(p)
print('TOOLS_OK: one launcher, shared backend, no private accounts or uploads')
