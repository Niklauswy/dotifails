"""Cloud VMs in the bar: indicator logic (CloudVmsLogic.js, node) and static QML wiring."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

SHELL = Path(__file__).resolve().parents[2] / 'apps/shell'


def js(body):
    node = shutil.which('node')
    if not node:
        raise unittest.SkipTest('node not available')
    source = (SHELL / 'services/CloudVmsLogic.js').read_text().replace('.pragma library', '')
    script = source + '\nprocess.stdout.write(JSON.stringify((() => {' + body + '})()));'
    result = subprocess.run([node], input=script, capture_output=True, text=True, timeout=10)
    if result.returncode:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


STATE = """{updated: 1000, total: 4, running: [
    {project: "mi-proyecto-prod", name: "api-backend", zone: "us-central1-a"},
    {project: "personal-lab", name: "batch-spot", zone: "us-central1-b"},
    {project: "mi-proyecto-prod", name: "worker-1", zone: "us-central1-a"}
]}"""


class LogicTests(unittest.TestCase):
    def test_running_ignores_stale_and_broken(self):
        out = js(f'''const s = {STATE};
            return [
                running(s, 1000).map(vm => vm.name),
                running(s, 1600).map(vm => vm.name),
                running(s, 1601),
                running(null, 1000),
                running({{}}, 1000),
                running({{updated: "1000", running: []}}, 1000),
                running({{updated: 1000, running: null}}, 1000),
                running({{updated: 1000, running: [null, {{}}, {{project: "p"}},
                    {{project: "p", name: "ok", zone: "z"}}]}}, 1000).map(vm => vm.name)
            ]''')
        self.assertEqual(out, [
            ['api-backend', 'batch-spot', 'worker-1'],
            ['api-backend', 'batch-spot', 'worker-1'],
            [],
            [],
            [],
            [],
            [],
            ['ok'],
        ])

    def test_tooltip_groups_by_project(self):
        out = js(f'''return tooltip(running({STATE}, 1000))''')
        self.assertEqual(out, 'mi-proyecto-prod: api-backend, worker-1\npersonal-lab: batch-spot')
        self.assertEqual(js('return [tooltip([]), tooltip(null)]'), ['', ''])

    def test_label_counts_vms(self):
        self.assertEqual(js(f'return label(running({STATE}, 1000))'), '3')
        self.assertEqual(js('return [label([]), label(null)]'), ['0', '0'])


class WiringTests(unittest.TestCase):
    def test_status_icons_has_cloud_entry_bound_to_active(self):
        text = (SHELL / 'modules/bar/components/StatusIcons.qml').read_text()
        self.assertIn('name: "cloudvms"', text)
        self.assertIn('visible: CloudVms.active', text)
        self.assertIn('CloudVms.open()', text)

    def test_service_polls_estado_every_two_minutes(self):
        text = (SHELL / 'services/CloudVms.qml').read_text()
        self.assertIn('interval: 120000', text)
        self.assertIn('"--estado"', text)
        self.assertIn('Logic.running(', text)
        self.assertIn('wysun-cloud', text)
        self.assertIn('"--terminal"', text)


if __name__ == '__main__':
    unittest.main()
