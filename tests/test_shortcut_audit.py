import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('shortcut_audit',ROOT/'installer/shortcut_audit.py');audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)

class ShortcutAuditTests(unittest.TestCase):
 def test_braces_correlate_modifiers_directions_and_actions(self):
  rows=audit.parse('super + {_,shift + }{Left,Down,Up,Right}\n  bspc node -{f,s} {west,south,north,east}\n')
  self.assertEqual(len(rows),8);self.assertEqual(rows[0]['key'],'SUPER + Left');self.assertEqual(rows[4]['key'],'SUPER + SHIFT + Left');self.assertEqual(rows[4]['command'],'bspc node -s west')
 def test_numeric_and_keypad_complete_expansion(self):
  rows=audit.parse('super + {_,shift + }{1-9,0}\n bspc {desktop -f,node -d} \'{1-9,10}\'\n')
  self.assertEqual(len(rows),20);self.assertEqual(rows[9]['command'],"bspc desktop -f '10'");self.assertEqual(rows[-1]['key'],'SUPER + SHIFT + 0')
  rows=audit.parse('super + {_,shift + }{KP_End,KP_Down,KP_Next,KP_Left,KP_Begin,KP_Right,KP_Home,KP_Up,KP_Prior,KP_Insert}\n bspc {desktop -f,node -d} \'{1-9,10}\'\n');self.assertEqual(len(rows),20)
 def test_comments_continuations_and_private_literal_are_never_executed(self):
  rows=audit.parse('# super + x\n# ignored\nsuper + shift + q\n "$HOME/.local/bin/wybie-screenshot" --path "$HOME/private path"\nsuper + o\n bspc wm -h off; \\\n bspc node older -f; \\\n bspc wm -h on\n')
  self.assertEqual(len(rows),2);self.assertIn('$HOME/private path',rows[0]['command']);self.assertEqual(rows[1]['command'],'bspc wm -h off; bspc node older -f; bspc wm -h on')
 def test_mismatch_is_not_silently_dropped(self):
  with self.assertRaises(ValueError):audit.parse('super + {a,b,c}\n command {one,two}\n')
 def test_conflicts_normalize_modifier_order(self):
  rows=audit.parse('alt + super + a\n one\nsuper + alt + A\n two\n');self.assertEqual(audit.duplicates(rows),{'SUPER + ALT + A':2})
 def test_lua_records_reject_dynamic_unaudited_binds(self):
  self.assertEqual(audit.literal_lua_bindings('hl.bind("SUPER + W", hl.dsp.window.close(), {description="Cerrar"})')[0]['key'],'SUPER + W')
  with self.assertRaises(ValueError):audit.literal_lua_bindings('hl.bind(key, action)')

class DistributedBindingsTests(unittest.TestCase):
 def test_every_distributed_binding_is_unique_and_matches_public_manifest(self):
  import json
  rows=audit.literal_lua_bindings((ROOT/'home/.config/wysun/hyprland.lua').read_text())
  spec=json.loads((ROOT/'manifests/wayland-shortcuts.json').read_text())['bindings']
  self.assertFalse(audit.duplicates(rows));self.assertEqual(len(rows),len(spec));self.assertEqual({r['key'] for r in rows},{r['key'] for r in spec})
  for a,b in zip(rows,spec):self.assertTrue(a['action'].startswith(b['action']+','));self.assertIn(b['status'],a['description'])
 def test_personal_capture_paths_are_quoted_not_executed_or_copied_to_repo(self):
  text='Print\n wybie-screenshot --region --delay 0\nsuper + shift + s\n wybie-screenshot --path "$HOME/capture folder"\nsuper + shift + q\n wybie-screenshot --path "$HOME/other folder"\nsuper + shift + a\n wybie-screenshot --region\n'
  fragment,rows=audit.private_capture_fragment(text,Path('/tmp/fixture-home'))
  self.assertEqual(len(rows),4);self.assertIn("'/tmp/fixture-home/other folder'",fragment);self.assertEqual(fragment.count('hl.unbind('),4)
  self.assertEqual(rows[1]['argv'],['--path','/tmp/fixture-home/capture folder'])
  self.assertNotIn('/home/nicolas',(ROOT/'manifests/wayland-shortcuts.json').read_text())

 def test_float_actions_use_native_idempotent_enum(self):
  import json
  rows={r['key']:r for r in json.loads((ROOT/'manifests/wayland-shortcuts.json').read_text())['bindings']}
  self.assertEqual(rows['SUPER + T']['action'],'hl.dsp.window.float({action="disable"})')
  self.assertEqual(rows['SUPER + S']['action'],'hl.dsp.window.float({action="enable"})')

 def test_capture_rules_never_float_generic_python_or_resize_orbit_family(self):
  text=(ROOT/'home/.config/wysun/hyprland.lua').read_text()
  rules=[line for line in text.splitlines() if line.startswith('hl.window_rule(')]
  python_rules=[line for line in rules if '"^python3$"' in line]
  self.assertEqual(len(python_rules),2)
  self.assertTrue(all('title = "^Wysun Recorder · ' in line for line in python_rules))
  family=next(line for line in rules if 'name = "wysun-orbit-panels"' in line)
  self.assertNotRegex(family,r'(?<!_)\bsize\s*=');self.assertNotIn('fullscreen',family)
  self.assertIn('orbit-music|orbit-settings',family)

if __name__=='__main__':unittest.main()
