import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps/wysun'))
import theme_core
import wysun_scheme
from PIL import Image
from theme_runtime import RETIRED_BAR_COLORS,restore_theme,theme_colors,theme_files
from theme_tokens import invalidate
def external(variant):return theme_core.resolve('material-you',variant)['external']
class PaletteFilesTests(unittest.TestCase):
 def setUp(self):
  self.folder=tempfile.TemporaryDirectory();self.home=Path(self.folder.name)
  def file(path,text):
   dest=self.home/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(text)
  file('.config/ghostty/config','font-size = 23\nkeybind = ctrl+i=csi:105;5u\nbackground-opacity = 0.61\nbackground = 101010\nforeground = aaaaaa\npalette = 0=#000000\n')
  file('.config/starship.toml',"format = '$directory$character'\n[character]\nsuccess_symbol = '[➜](green)'\n")
  file('.config/nvim/lua/chadrc.lua','local M = {}\nM.base46 = { theme = "rosepine", transparency = true, hl_override = { Comment = {fg = "#908caa"} } }\nM.ui = {statusline = {theme = "minimal"}}\nreturn M\n')
  file('.config/orbit/environment.json',json.dumps({'wallpaper':{'folders':['/my/library']},'workspaces':{'names':['keep']}}))
 def tearDown(self):self.folder.cleanup();invalidate()
 def write(self,variant):
  files=theme_files(self.home,variant)
  for path,text in files.items():path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
  return files
 def test_both_palettes_theme_the_programs_without_losing_settings_or_accumulating(self):
  for variant in ('dark','light','dark'):
   files=self.write(variant);ext=external(variant)
   terminal=(self.home/'.config/ghostty/config').read_text();self.assertIn('font-size = 23',terminal);self.assertIn('keybind = ctrl+i=csi:105;5u',terminal);self.assertIn('background-opacity = 0.61',terminal)
   self.assertEqual(terminal.count('palette = '),16);self.assertIn(ext['background'][1:],terminal)
   self.assertEqual((self.home/'.config/starship.toml').read_text().count('[palettes.orbit]'),1)
   editor=(self.home/'.config/nvim/lua/chadrc.lua').read_text();self.assertIn('transparency = true',editor);self.assertIn('theme = "minimal"',editor)
   self.assertIn('theme = "'+ext['nvim']+'"',editor)
   css=(self.home/'.config/gtk-4.0/gtk.css').read_text();self.assertEqual(css.count('BEGIN ORBIT THEME'),1);self.assertIn('accent_bg_color '+ext['accent'],css)
   self.assertEqual('theme_bg_color' in css,variant=='dark','the bundled GTK themes are dark: only the dark palette repaints the window')
   self.assertTrue(any(ext['accent'][1:7] in text for path,text in files.items() if path.name=='hypr-theme.lua'))
   self.assertEqual(json.loads((self.home/'.config/orbit/environment.json').read_text())['workspaces']['names'],['keep'],'the staging never touches preferences')
   self.assertNotIn(self.home/'.config/orbit/theme.json',files,'the mode is the installer\'s and the shell\'s to write')
   self.assertFalse((self.home/'.config/wysun/dunstrc').exists())      # notifications follow the shell theme; no separate daemon config
 def test_unknown_variant_uses_the_default_palette(self):
  files=theme_files(self.home,'tokyo')
  self.assertIn(external('dark')['background'][1:],files[self.home/'.config/ghostty/config'])
 def test_theme_generated_bar_colours_are_dropped_but_custom_ones_kept(self):
  bar=self.home/'.config/orbit/hypr-bar.json'
  for generated in (external('dark')['background'],'#101012','#101118'):
   bar.write_text(json.dumps({'height':40,'background':generated,'foreground':'#123456'}))
   saved=json.loads(theme_files(self.home,'light')[bar])
   self.assertEqual(saved,{'height':40,'foreground':'#123456'},generated)
  self.assertTrue(RETIRED_BAR_COLORS<=theme_colors())
 def test_restore_theme_paints_the_borders_with_the_active_scheme(self):
  image=self.home/'blue.png';Image.new('RGB',(32,32),(25,82,224)).save(image)
  scheme=wysun_scheme.generate_dynamic(image,'dark');theme_core.write_scheme(scheme,self.home)
  calls=[];restore_theme(self.home,lambda args:calls.append(list(args)) or '')
  self.assertEqual(calls[0][:2],['hyprctl','eval']);self.assertIn(scheme['colours']['primary'],calls[0][2])
 def test_restore_theme_without_a_scheme_uses_the_shipped_palette(self):
  calls=[];restore_theme(self.home,lambda args:calls.append(list(args)) or '')
  self.assertIn(theme_core.resolve('material-you','dark')['accent'][1:7],calls[0][2])
if __name__=='__main__':unittest.main()
