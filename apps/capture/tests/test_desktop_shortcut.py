import importlib.util,tempfile,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('desktop_shortcut',Path(__file__).resolve().parents[1]/'scripts/desktop-shortcut.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class ShortcutTests(unittest.TestCase):
 def test_exact_block_removal_preserves_later_edits_and_backup(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);config=root/'sxhkdrc';state=root/'state.json';launcher=root/'loomrec'
   original='super + Return\n    terminal\n';config.write_text(original);launcher.write_text('#!/bin/sh\n');launcher.chmod(0o755)
   result=module.install(config,state,launcher);self.assertEqual(Path(result['backup']).read_text(),original)
   self.assertTrue(module.install(config,state,launcher)['already_present'])
   config.write_text(config.read_text()+'\n# user new content\n')
   module.uninstall(state);self.assertEqual(config.read_text(),original+'\n# user new content\n')
 def test_conflict_and_modified_block_fail_closed(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);config=root/'sxhkdrc';state=root/'state';launcher=root/'loomrec';launcher.write_text('');launcher.chmod(0o755)
   config.write_text('super + shift + {l,x}\n    command\n')
   with self.assertRaises(ValueError):module.install(config,state,launcher)
   config.write_text('');module.install(config,state,launcher)
   config.write_text(config.read_text().replace('--quick-record','--user-change'))
   with self.assertRaises(ValueError):module.uninstall(state)

 def test_migrate_only_managed_chord_and_refuse_new_conflict(self):
  import json
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);config=root/'sxhkdrc';state=root/'state';launcher=root/'loomrec';launcher.write_text('');launcher.chmod(0o755)
   original='super + Return\n    terminal\n';config.write_text(original)
   module.install(config,state,launcher,'super + ctrl + shift + l')
   before=config.read_text();config.write_text(before+'super + shift + {l,x}\n    private-command\n')
   conflicted=config.read_text();record=state.read_bytes()
   with self.assertRaises(ValueError):module.install(config,state,launcher)
   self.assertEqual(config.read_text(),conflicted);self.assertEqual(state.read_bytes(),record)
   config.write_text(before);result=module.install(config,state,launcher)
   self.assertEqual(Path(result['backup']).read_text(),before)
   self.assertEqual(json.loads(state.read_text())['chord'],'super + shift + l')
   self.assertNotIn('super + ctrl + shift + l',config.read_text())
   module.uninstall(state);self.assertEqual(config.read_text(),original)
