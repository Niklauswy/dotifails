"""The cheat sheet is generated from the active Hyprland binds on every call."""
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / 'apps/shell/modules/cheatsheet/backend.py'
spec = importlib.util.spec_from_file_location('wysun_cheatsheet_backend', SOURCE)
backend = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend)

STOCK = 'hl.bind("SUPER + Return", hl.dsp.exec_cmd("wysun-terminal"), {description="Wysun | equivalent | Abrir wysun-terminal"})\n'
NEW = 'hl.bind("SUPER + SHIFT + N", hl.dsp.exec_cmd("true"), {description="Wysun | %s | %s"})\n'


def groups(text):
    return {g['category']: g['items'] for g in backend.collect(text)}


class CheatsheetTests(unittest.TestCase):
    def test_new_bind_appears_in_existing_category(self):
        found = groups(STOCK + NEW % ('Apps', 'Open the thing'))
        self.assertIn({'keys': ['Super', 'Shift', 'N'], 'label': 'Open the thing'}, found['Apps'])
        self.assertIn('Terminal', [i['label'] for i in found['Apps']])

    def test_new_categories_are_created(self):
        found = groups(STOCK + NEW % ('Notes', 'Quick note'))
        self.assertEqual(found['Notes'], [{'keys': ['Super', 'Shift', 'N'], 'label': 'Quick note'}])

    def test_recover_bind_is_listed_under_session(self):
        line = 'hl.bind("SUPER + Escape", hl.dsp.exec_cmd("sh -c \'wysun recover; hyprctl reload\'"), {description="Wysun | session | Recover desktop"})\n'
        self.assertEqual(groups(line)['Session'][0]['keys'], ['Super', 'Esc'])

    def test_legacy_provenance_tags_keep_derived_labels(self):
        found = groups(STOCK)
        self.assertEqual(found['Apps'][0]['label'], 'Terminal')
        self.assertNotIn('equivalent', found)

    def test_later_bind_on_same_keys_replaces_earlier(self):
        found = groups(NEW % ('Notes', 'Old') + NEW % ('Notes', 'New'))
        self.assertEqual([i['label'] for i in found['Notes']], ['New'])

    def test_every_run_reads_the_file_again(self):
        with tempfile.TemporaryDirectory() as home:
            config = Path(home) / 'hyprland.lua'
            config.write_text(STOCK, encoding='utf-8')
            run = lambda: json.loads(subprocess.run(['python3', '-I', str(SOURCE), str(config)], capture_output=True, text=True, check=True).stdout)
            self.assertNotIn('Notes', [g['category'] for g in run()])
            config.write_text(STOCK + NEW % ('Notes', 'Quick note'), encoding='utf-8')
            self.assertIn('Notes', [g['category'] for g in run()])


if __name__ == '__main__':
    unittest.main()
