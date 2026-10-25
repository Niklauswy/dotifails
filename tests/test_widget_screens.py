"""Widget placement follows saved primary outputs, including hotplug fallback."""
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class WidgetScreensTests(unittest.TestCase):
    def test_primary_selection_and_surface_routing(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('Node is required for the shared QML JavaScript policy')
        source = (ROOT / 'apps/shell/services/WidgetScreens.js').read_text()
        script = source + '''
const assert = require('node:assert/strict');
const prefs = {profiles: {'A|B|C': [
    {name:'A', enabled:true, primary:false},
    {name:'B', enabled:true, primary:true},
    {name:'C', enabled:true, primary:false}
]}};
assert.equal(primaryName(['C','A','B'], prefs), 'B');
assert.equal(primaryName(['B','C','A'], prefs), 'B');
assert.equal(primaryName(['A','B'], prefs), 'B');
assert.equal(primaryName(['C','A'], prefs), 'A');
assert.equal(primaryName([], prefs), '');
assert.equal(primaryName(['C'], prefs), 'C');
assert.equal(primaryName(['C','A'], {}), 'A');
prefs.profiles['A|C'] = [{name:'C', enabled:true, primary:true}];
assert.equal(primaryName(['A','C'], prefs), 'C');
for (const kind of ['dashboard','menu','notifications','session','ai'])
    assert.equal(drawerSurface(kind), true);
for (const kind of ['launcher','overview','emoji','screenshot',undefined])
    assert.equal(drawerSurface(kind), false);
'''
        result = subprocess.run([node], input=script, text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
