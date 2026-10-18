import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps/orbit'))
from theme_runtime import apply_theme
from theme_tokens import THEMES,theme_id,invalidate
class CompleteThemeTests(unittest.TestCase):
 def setUp(self):
  self.folder=tempfile.TemporaryDirectory();self.home=Path(self.folder.name)
  def file(path,text):
   dest=self.home/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(text)
  file('.config/ghostty/config','font-size = 23\nkeybind = ctrl+i=csi:105;5u\nbackground-opacity = 0.61\nbackground = 101010\nforeground = aaaaaa\npalette = 0=#000000\n')
  file('.config/starship.toml',"format = '$directory$character'\n[character]\nsuccess_symbol = '[➜](green)'\n")
  file('.config/nvim/lua/chadrc.lua','local M = {}\nM.base46 = { theme = "rosepine", transparency = true, hl_override = { Comment = {fg = "#908caa"} } }\nM.ui = {statusline = {theme = "minimal"}}\nreturn M\n')
  file('.config/orbit/environment.json',json.dumps({'wallpaper':{'folders':['/my/library']},'workspaces':{'names':['keep']}}))
  file('.config/bspwm/dunstrc','[global]\nfont = Inter 10\n[urgency_low]\nbackground = "#112233"\n[urgency_normal]\nbackground = "#112233"\n[urgency_critical]\nbackground = "#441122"\n')
  for name in ('tokyo.png','azul.jpg','space-black.png'):file('.local/share/backgrounds/'+name,'fixture')
 def tearDown(self):self.folder.cleanup();invalidate()
 def runner(self,args):return '#111111' if args[:2]==['bspc','config'] and len(args)==3 else ''
 def test_switches_both_themes_without_losing_settings_or_palette_accumulation(self):
  with patch('theme_runtime.render_wallpaper'),patch('theme_runtime.display_inventory',return_value=[]):
   for key in ('tokyo','severance','space-black','tokyo'):
    result=apply_theme(self.home,key,self.runner);self.assertTrue(Path(result['backup']).exists())
    terminal=(self.home/'.config/ghostty/config').read_text();self.assertIn('font-size = 23',terminal);self.assertIn('keybind = ctrl+i=csi:105;5u',terminal);self.assertIn('background-opacity = 0.61',terminal)
    self.assertEqual(terminal.count('palette = '),16);self.assertIn(THEMES[key]['background'][1:],terminal)
    environment=json.loads((self.home/'.config/orbit/environment.json').read_text());self.assertEqual(environment['workspaces']['names'],['keep']);self.assertEqual(environment['wallpaper']['folders'],['/my/library'])
    invalidate();self.assertEqual(theme_id(self.home),key)
    self.assertEqual((self.home/'.config/starship.toml').read_text().count('[palettes.orbit]'),1)
    editor=(self.home/'.config/nvim/lua/chadrc.lua').read_text();self.assertIn('transparency = true',editor);self.assertIn('theme = "minimal"',editor)
    self.assertIn('theme = "'+{'tokyo':'tokyonight','severance':'nord','space-black':'github_dark'}[key]+'"',editor)
    notices=(self.home/'.config/bspwm/dunstrc').read_text();self.assertEqual(notices.count('background = "#18191d"'),3);self.assertIn('foreground = "#eeeef0"',notices);self.assertIn('font = Inter 10',notices)
 def test_failed_validation_restores_every_original_file(self):
  originals={p.relative_to(self.home):p.read_bytes() for p in self.home.rglob('*') if p.is_file()}
  def runner(args):
   if args==['ghostty','+validate-config']:raise RuntimeError('validation failed')
   return self.runner(args)
  with patch('theme_runtime.render_wallpaper'),self.assertRaises(RuntimeError):apply_theme(self.home,'tokyo',runner)
  for relative,content in originals.items():self.assertEqual((self.home/relative).read_bytes(),content)
  self.assertFalse((self.home/'.config/orbit/theme.json').exists())
 def test_rejects_unknown_profile(self):
  with self.assertRaises(ValueError):apply_theme(self.home,'other',self.runner)
if __name__=='__main__':unittest.main()
