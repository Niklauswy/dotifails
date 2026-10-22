import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps/wysun'))
from theme_runtime import apply_theme
import theme_core
from theme_tokens import theme_id,invalidate
def external(key):return theme_core.resolve(*theme_core.parse(key))['external']
def wallpaper(key):return theme_core.resolve(*theme_core.parse(key))['wallpaper']
class CompleteThemeTests(unittest.TestCase):
 def setUp(self):
  self.folder=tempfile.TemporaryDirectory();self.home=Path(self.folder.name)
  def file(path,text):
   dest=self.home/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(text)
  file('.config/ghostty/config','font-size = 23\nkeybind = ctrl+i=csi:105;5u\nbackground-opacity = 0.61\nbackground = 101010\nforeground = aaaaaa\npalette = 0=#000000\n')
  file('.config/starship.toml',"format = '$directory$character'\n[character]\nsuccess_symbol = '[➜](green)'\n")
  file('.config/nvim/lua/chadrc.lua','local M = {}\nM.base46 = { theme = "rosepine", transparency = true, hl_override = { Comment = {fg = "#908caa"} } }\nM.ui = {statusline = {theme = "minimal"}}\nreturn M\n')
  file('.config/orbit/environment.json',json.dumps({'wallpaper':{'folders':['/my/library']},'workspaces':{'names':['keep']}}))
  for name in ('tokyo.png','azul.jpg','space-black.png'):file('.local/share/backgrounds/'+name,'fixture')
 def tearDown(self):self.folder.cleanup();invalidate()
 def runner(self,args):
  if args[:3]==['hyprctl','-j','getoption']:return json.dumps({'str':'rgb(123456)'})
  if args[:2]==['hyprctl','eval']:self.evaluated.append(args[2]);return 'ok'
  if args[:2]==['hyprctl','-j']:return '[]'
  return ''
 def apply(self,key,runner=None):
  self.evaluated=[]
  with patch('theme_runtime.render_wallpaper'),patch('theme_runtime.display_inventory',return_value=[]):
   return apply_theme(self.home,key,runner or self.runner)
 def test_switches_every_variant_without_losing_settings_or_palette_accumulation(self):
  for key in ('tokyo','severance','space-black','fluent:light','fluent:dark','tokyo'):
   result=self.apply(key);self.assertTrue(Path(result['backup']).exists());ext=external(key)
   terminal=(self.home/'.config/ghostty/config').read_text();self.assertIn('font-size = 23',terminal);self.assertIn('keybind = ctrl+i=csi:105;5u',terminal);self.assertIn('background-opacity = 0.61',terminal)
   self.assertEqual(terminal.count('palette = '),16);self.assertIn(ext['background'][1:],terminal)
   environment=json.loads((self.home/'.config/orbit/environment.json').read_text());self.assertEqual(environment['workspaces']['names'],['keep']);self.assertEqual(environment['wallpaper']['folders'],['/my/library']);self.assertTrue(environment['wallpaper']['default'].endswith(wallpaper(key)))
   saved=json.loads((self.home/'.config/orbit/theme.json').read_text());self.assertEqual(theme_core.key(saved['style'],saved['variant']),theme_core.key(*theme_core.parse(key)))
   scheme=json.loads(theme_core.scheme_path(self.home).read_text());self.assertEqual(scheme['name'],theme_core.parse(key)[1]);self.assertEqual(scheme['mode'],'light' if key=='fluent:light' else 'dark');self.assertTrue(all(not value.startswith('#') for value in scheme['colours'].values()))
   self.assertEqual((self.home/'.config/orbit/theme.json').stat().st_mode&0o777,0o600)
   invalidate();self.assertEqual(theme_id(self.home),theme_core.key(*theme_core.parse(key)))
   self.assertEqual((self.home/'.config/starship.toml').read_text().count('[palettes.orbit]'),1)
   editor=(self.home/'.config/nvim/lua/chadrc.lua').read_text();self.assertIn('transparency = true',editor);self.assertIn('theme = "minimal"',editor)
   self.assertIn('theme = "'+ext['nvim']+'"',editor)
   self.assertFalse((self.home/'.config/wysun/dunstrc').exists())      # notifications follow the shell theme; no separate daemon config
   self.assertTrue(any(ext['accent'][1:] in command for command in self.evaluated))
 def test_theme_generated_bar_colours_are_dropped_but_custom_ones_kept(self):
  bar=self.home/'.config/orbit/hypr-bar.json'
  bar.write_text(json.dumps({'height':40,'background':external('tokyo')['background'],'foreground':'#123456'}))
  self.apply('fluent:dark');saved=json.loads(bar.read_text())
  self.assertEqual(saved,{'height':40,'foreground':'#123456'})
 def test_failed_validation_restores_every_original_file(self):
  originals={p.relative_to(self.home):p.read_bytes() for p in self.home.rglob('*') if p.is_file()}
  def runner(args):
   if args==['ghostty','+validate-config']:raise RuntimeError('validation failed')
   return self.runner(args)
  with self.assertRaises(RuntimeError):self.apply('tokyo',runner)
  for relative,content in originals.items():self.assertEqual((self.home/relative).read_bytes(),content)
  self.assertFalse((self.home/'.config/orbit/theme.json').exists())
 def test_rejects_unknown_profile(self):
  with self.assertRaises(ValueError):self.apply('other')
if __name__=='__main__':unittest.main()
