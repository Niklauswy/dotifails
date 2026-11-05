"""The project-column mosaic: layout, cards, off lines and keyboard navigation."""
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / 'apps/python'
FIXTURES = ROOT / 'tests/fixtures/cloud'
sys.path.insert(0, str(APP))

from wysun_core.tui.anim import Rect  # noqa: E402
from wysun_core.tui.canvas import Canvas  # noqa: E402
from wysun_core.tui.theme import Palette  # noqa: E402
from wysun_cloud.model import Instance, Sample  # noqa: E402
from wysun_cloud.ui.mosaic import (  # noqa: E402
    VmView, draw_card, draw_mosaic, layout, navigate, project_titles,
)


def read_instances(project):
    data = json.loads((FIXTURES / f'instances-{project}.json').read_text(encoding='utf-8'))
    return [Instance.from_gcloud(project, item) for item in data]


def make_instance(project, name, status='RUNNING', zone='us-central1-a', machine_type='e2-small'):
    return Instance(project=project, name=name, zone=zone, status=status, machine_type=machine_type,
                    external_ip=None, internal_ip='10.0.0.2', spot=False, os='debian-12', disks=[name],
                    network='default', tags=[], started=None)


def make_sample(cpu=0.42, ram=11.2, ram_total=16.0, disk_used=88.0, disk_size=100.0,
                uptime=12 * 86400, command='node server.js', top_cpu=41.0,
                rx=1.2, tx=0.3):
    return Sample(cpu=cpu, cores=[cpu] * 4, load=(2.4, 1.9, 1.1),
                  ram_used_gb=ram, ram_total_gb=ram_total, cache_gb=ram_total * 0.19,
                  swap_used_gb=0.0, swap_total_gb=2.0, rx_mbs=rx, tx_mbs=tx,
                  read_mbs=2.1, write_mbs=34.0,
                  mounts=[('/', disk_used, disk_size)], uptime_s=uptime,
                  top=[(1200, top_cpu, 2.1, command)])


class MosaicTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.home, True)
        self.patcher = mock.patch.dict(os.environ, {'HOME': self.home, 'WYSUN_THEME': ''})
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.palette = Palette.load(self.home)

    # -- helpers ----------------------------------------------------------
    def canvas(self, width=120, height=36):
        return Canvas(width, height, self.palette['surface'])

    def running_view(self, inst, **sample_args):
        return VmView(inst=inst, sample=make_sample(**sample_args), state='activo')

    def off_view(self, inst):
        return VmView(inst=inst, sample=None)

    def three_projects(self):
        views = []
        for project in ('mi-proyecto-prod', 'personal-lab', 'cliente-x'):
            for inst in read_instances(project):
                views.append(self.running_view(inst) if inst.running else self.off_view(inst))
        return views, ['mi-proyecto-prod', 'personal-lab', 'cliente-x']

    # -- layout -----------------------------------------------------------
    def test_three_projects_three_columns(self):
        views, projects = self.three_projects()
        rects = layout(views, projects, 120, 36)
        coil = self.canvas()
        draw_mosaic(coil, views, projects, self.palette, selected=None, spin=0)

        # One 38-wide column per project: x = 1, 41, 81 (120 - 2 margin, two 2-cell gaps).
        self.assertEqual(project_titles(views, projects, 120, 36),
                         {'mi-proyecto-prod': (1, 2), 'personal-lab': (41, 2), 'cliente-x': (81, 2)})
        row = coil.row_text(2)
        self.assertTrue(row[1:].startswith('mi-proyecto-prod'))
        self.assertTrue(row[41:].startswith('personal-lab'))
        self.assertTrue(row[81:].startswith('cliente-x'))

        api = rects['api-backend.us-central1-a.mi-proyecto-prod']
        self.assertEqual((api.x, api.y, api.w, api.h), (1, 4, 38, 8))
        dev = rects['dev-box.us-west1-b.personal-lab']
        self.assertEqual((dev.x, dev.y, dev.w, dev.h), (41, 4, 38, 8))
        web = rects['web-cliente.southamerica-east1-a.cliente-x']
        self.assertEqual((web.x, web.y, web.w, web.h), (81, 4, 38, 8))

    def test_off_vms_are_one_line_at_the_end(self):
        views, projects = self.three_projects()
        views = [v for v in views if v.inst.project == 'mi-proyecto-prod']
        rects = layout(views, projects, 120, 36)

        first = rects['api-backend.us-central1-a.mi-proyecto-prod']
        second = rects['worker-1.us-central1-b.mi-proyecto-prod']
        off = rects['db-old.us-central1-a.mi-proyecto-prod']
        self.assertEqual((first.y, second.y), (4, 12))
        self.assertEqual((off.x, off.y, off.w, off.h), (2, 20, 37, 1))
        self.assertGreater(off.y, second.y + second.h - 1)

        coil = self.canvas()
        draw_mosaic(coil, views, projects, self.palette, selected=None, spin=0)
        row = coil.row_text(20)
        self.assertIn('○ db-old', row)
        self.assertIn('apagada', row)

    def test_one_project_spreads_cards(self):
        instances = [make_instance('mi-proyecto-prod', f'vm-{index}') for index in range(3)]
        views = [self.running_view(inst) for inst in instances]
        rects = layout(views, ['mi-proyecto-prod'], 120, 36)
        positions = [rects[inst.alias] for inst in instances]
        self.assertEqual({rect.x for rect in positions}, {1, 41, 81})
        self.assertEqual({(rect.y, rect.w, rect.h) for rect in positions}, {(4, 38, 8)})
        self.assertEqual(project_titles(views, ['mi-proyecto-prod'], 120, 36),
                         {'mi-proyecto-prod': (1, 2)})

    def test_narrow_terminal_stacks_projects(self):
        views = []
        for project in ('mi-proyecto-prod', 'personal-lab', 'cliente-x'):
            running = next(inst for inst in read_instances(project) if inst.running)
            stopped = next(inst for inst in read_instances(project) if not inst.running)
            views.extend([self.off_view(stopped), self.running_view(running)])
        projects = ['mi-proyecto-prod', 'personal-lab', 'cliente-x']

        titles = project_titles(views, projects, 80, 36)
        # One list: each title, a blank row, running card then the off line, a gap row.
        self.assertEqual(titles, {'mi-proyecto-prod': (1, 2), 'personal-lab': (1, 14),
                                  'cliente-x': (1, 26)})
        rects = layout(views, projects, 80, 36)
        cards = [rects.get(v.inst.alias) for v in views if v.inst.running]
        self.assertEqual([rect.y for rect in cards[:2]], [4, 16])
        self.assertEqual({(rect.x, rect.w) for rect in cards[:2]}, {(1, 78)})
        self.assertIsNone(cards[2])                      # rows 28..35 do not fit: omitted...
        offs = [rects.get(v.inst.alias) for v in views if not v.inst.running]
        self.assertEqual([rect.y for rect in offs[:2]], [12, 24])
        last = next(v for v in views if v.inst.running and v.inst.project == 'cliente-x')
        scrolled = layout(views, projects, 80, 36, selected=last.inst.alias)
        self.assertLessEqual(scrolled[last.inst.alias].y + 8, 35)   # ...until selected

        coil = self.canvas(80, 36)
        draw_mosaic(coil, views, projects, self.palette, selected=None, spin=0)
        self.assertIn('mi-proyecto-prod', coil.row_text(2))
        self.assertIn('personal-lab', coil.row_text(14))
        self.assertIn('cliente-x', coil.row_text(26))

    def test_stacked_small_terminal_scrolls_to_the_selection(self):
        views = [self.running_view(make_instance(project, f'vm-{project}'))
                 for project in ('mi-proyecto-prod', 'personal-lab', 'cliente-x')]
        projects = ['mi-proyecto-prod', 'personal-lab', 'cliente-x']
        for view in views:
            rects = layout(views, projects, 80, 24, selected=view.inst.alias)
            rect = rects[view.inst.alias]
            self.assertGreaterEqual(rect.y, 2)
            self.assertLessEqual(rect.y + rect.h, 23)
            canvas = self.canvas(80, 24)
            draw_mosaic(canvas, views, projects, self.palette, view.inst.alias, 0)
            self.assertTrue(any(view.inst.name in canvas.row_text(y) for y in range(24)))

    def test_navigate_follows_a_spread_single_project(self):
        insts = [make_instance('mi-proyecto-prod', f'run-{index}') for index in range(3)]
        views = [self.running_view(inst) for inst in insts]
        rects = layout(views, ['mi-proyecto-prod'], 120, 36)
        self.assertEqual(sorted({rect.x for rect in rects.values()}), [1, 41, 81])
        right = navigate(views, ['mi-proyecto-prod'], insts[0].alias, 'right', 120, 36)
        self.assertEqual(rects[right].x, 41)
        down = navigate(views, ['mi-proyecto-prod'], insts[0].alias, 'down', 120, 36)
        self.assertEqual(down, insts[0].alias)           # alone in its drawn column

    def test_long_name_truncated_in_title(self):
        inst = make_instance('mi-proyecto-prod', 'api-backend-with-a-very-long-name')
        view = self.running_view(inst)
        projects = ['mi-proyecto-prod', 'personal-lab', 'cliente-x']
        rects = layout([view], projects, 120, 36)
        # A 38-wide card leaves 34 title cells; the name alone is 33 plus the dot and type.
        self.assertEqual(rects[inst.alias].w, 38)
        coil = self.canvas(120, 36)
        draw_card(coil, rects[inst.alias], view, self.palette, selected=False, spin=0)

        title = coil.row_text(rects[inst.alias].y)
        self.assertIn('…', title)
        self.assertNotIn('api-backend-with-a-very-long-name', title)

    def test_column_overflow_keeps_selected_visible(self):
        instances = [make_instance('mi-proyecto-prod', f'vm-{index:02d}') for index in range(12)]
        views = [self.running_view(inst) for inst in instances]
        selected = instances[-1].alias
        rects = layout(views, ['mi-proyecto-prod'], 120, 36, selected=selected)

        chosen = rects[selected]
        self.assertGreaterEqual(chosen.y, 4)
        self.assertLessEqual(chosen.y + chosen.h, 36 - 1)
        # The first card of the selected sub-column scrolled out and is omitted; 12 cards
        # over three columns, three fully visible per column, plus the selected fourth.
        self.assertNotIn(instances[8].alias, rects)
        self.assertEqual(len(rects), 9)

    def test_card_shows_sin_ssh_reason(self):
        inst = make_instance('mi-proyecto-prod', 'api-backend')
        view = VmView(inst=inst, sample=None, state='sin-ssh', reason='llave rechazada')
        coil = self.canvas()
        rects = layout([view], ['mi-proyecto-prod'], 120, 36)
        draw_card(coil, rects[inst.alias], view, self.palette, selected=False, spin=0)
        self.assertIn('sin SSH · llave rechazada', coil.row_text(rects[inst.alias].y + 1))

    def test_navigate_between_columns(self):
        off0 = make_instance('mi-proyecto-prod', 'stopped-0', status='TERMINATED')
        run0a = make_instance('mi-proyecto-prod', 'run-0a')
        run0b = make_instance('mi-proyecto-prod', 'run-0b')
        run1 = make_instance('personal-lab', 'run-1')
        off1 = make_instance('personal-lab', 'stopped-1', status='TERMINATED')
        run2 = make_instance('cliente-x', 'run-2')
        views = [self.off_view(off0), self.running_view(run0a), self.running_view(run0b),
                 self.running_view(run1), self.off_view(off1), self.running_view(run2)]
        projects = ['mi-proyecto-prod', 'personal-lab', 'cliente-x']

        current = run0a.alias
        current = navigate(views, projects, current, 'down')
        self.assertEqual(current, run0b.alias)          # running cards come first
        current = navigate(views, projects, current, 'down')
        self.assertEqual(current, off0.alias)
        current = navigate(views, projects, current, 'down')
        self.assertEqual(current, off0.alias)           # clamped at the bottom
        current = navigate(views, projects, current, 'right')
        self.assertEqual(current, off1.alias)           # same index, clamped to the column
        current = navigate(views, projects, current, 'right')
        self.assertEqual(current, run2.alias)
        current = navigate(views, projects, current, 'right')
        self.assertEqual(current, run2.alias)           # clamped at the last project
        current = navigate(views, projects, current, 'left')
        self.assertEqual(current, run1.alias)
        current = navigate(views, projects, current, 'end')
        self.assertEqual(current, off1.alias)
        current = navigate(views, projects, current, 'home')
        self.assertEqual(current, run1.alias)

    def test_disk_over_85_shows_warning(self):
        inst = make_instance('mi-proyecto-prod', 'api-backend')
        full = self.running_view(inst, disk_used=90.0, disk_size=100.0)
        coil = self.canvas()
        rects = layout([full], ['mi-proyecto-prod'], 120, 36)
        draw_card(coil, rects[inst.alias], full, self.palette, selected=False, spin=0)
        row = coil.row_text(rects[inst.alias].y + 4)
        self.assertIn('90%', row)
        self.assertIn('▲', row)
        column = row.index('▲')
        self.assertEqual(coil.cell(column, rects[inst.alias].y + 4)[1].fg, self.palette['error'])

        calm = self.running_view(inst, disk_used=50.0, disk_size=100.0)
        other = self.canvas()
        draw_card(other, rects[inst.alias], calm, self.palette, selected=False, spin=0)
        row = other.row_text(rects[inst.alias].y + 4)
        self.assertIn('50%', row)
        self.assertNotIn('▲', row)


if __name__ == '__main__':
    unittest.main()
