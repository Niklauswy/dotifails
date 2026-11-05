"""The VM detail screen: the data line, the tabs and the seven tab renderers."""
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
from wysun_cloud.model import Instance, Sample, TabData  # noqa: E402
from wysun_cloud.ui.detail import (  # noqa: E402
    HEADER_ROWS, TABS, DetailData, body_lines, draw_detail_header, draw_tab,
)
from wysun_cloud.ui.mosaic import VmView  # noqa: E402

BASE = 1793822400.0          # 2026-11-04T12:00:00Z, the newest point of the fixtures
PORTS = [
    'State  Recv-Q Send-Q Local Address:Port  Peer Address:Port Process',
    'LISTEN 0      511          0.0.0.0:80         0.0.0.0:*    users:(("nginx",pid=1,fd=6))',
    'LISTEN 0      128          0.0.0.0:22         0.0.0.0:*    users:(("sshd",pid=2,fd=3))',
    'LISTEN 0      4096       127.0.0.1:5432       0.0.0.0:*    users:(("postgres",pid=3,fd=5))',
]
JOURNAL = [
    '2026-11-04T18:05:12+0100 api-backend worker[1200]: Error: ECONNREFUSED 127.0.0.1:6379',
    '2026-11-04T17:58:40+0100 api-backend kernel: TCP: request_sock_TCP: Possible SYN flooding on port 443.',
]
DOCKER = [
    '{"Names":"api","Image":"ghcr.io/app/api:1.8.2","Status":"Up 12 days","State":"running","Ports":"0.0.0.0:3000->3000/tcp"}',
    '{"Names":"worker","Image":"ghcr.io/app/worker:1.8","Status":"Exited (1) 2 hours ago","State":"exited","Ports":""}',
]
FAILED = ['certbot.service loaded failed failed Challenge failed for domain api.ejemplo.com']
DU = ['43200000\t/var/lib/docker', '19148800\t/var/log', '14417920\t/home/app/uploads']


def read_json(name):
    return json.loads((FIXTURES / name).read_text(encoding='utf-8'))


def make_instance():
    return Instance.from_gcloud('mi-proyecto-prod', read_json('instances-mi-proyecto-prod.json')[0])


def make_sample():
    return Sample(cpu=0.42, cores=[0.42, 0.3, 0.1, 0.05], load=(2.4, 1.9, 1.1),
                  ram_used_gb=11.2, ram_total_gb=16.0, cache_gb=3.0,
                  swap_used_gb=0.0, swap_total_gb=2.0, rx_mbs=1.2, tx_mbs=0.3,
                  read_mbs=2.1, write_mbs=34.0,
                  mounts=[('/', 88.0, 100.0), ('/data', 210.0, 500.0)],
                  uptime_s=12 * 86400,
                  top=[(1200, 41.0, 2.1, 'node server.js'),
                       (1357, 9.0, 1.4, 'postgres: writer'),
                       (1494, 4.0, 0.3, 'dockerd'),
                       (1631, 2.1, 0.2, 'containerd'),
                       (1768, 1.2, 0.1, 'systemd-journald'),
                       (1905, 0.8, 0.0, 'sshd: nicolas'),
                       (2042, 0.7, 0.2, 'redis-server *:6379'),
                       (2179, 0.5, 0.4, 'node worker.js')])


def make_history(hours, count=96):
    step = hours * 3600 / (count - 1)
    return [(BASE - hours * 3600 + index * step, ((index * 7) % 10) / 10.0)
            for index in range(count)]


def full_data():
    operations = [item for item in read_json('operations.json')
                  if 'api-backend' in str(item.get('targetLink') or '')]
    return DetailData(
        tabs={
            'ports': TabData('ports', list(PORTS)),
            'journal': TabData('journal', list(JOURNAL)),
            'docker': TabData('docker', list(DOCKER)),
            'failed': TabData('failed', list(FAILED)),
            'du': TabData('du', list(DU)),
        },
        history={24: make_history(24), 168: make_history(168, 336)},
        operations=operations,
        firewall=read_json('firewall.json'),
        disks=read_json('disks.json'),
        errors={},
    )


def empty_data():
    kinds = ('ports', 'journal', 'docker', 'failed', 'du')
    return DetailData(tabs={kind: TabData(kind, []) for kind in kinds},
                      history={24: [], 168: []}, operations=[], firewall=[], disks=[],
                      errors={})


class DetailTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.home, True)
        self.patcher = mock.patch.dict(os.environ, {'HOME': self.home, 'WYSUN_THEME': ''})
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.palette = Palette.load(self.home)
        self.view = VmView(inst=make_instance(), sample=make_sample(), state='activo')

    # -- helpers ----------------------------------------------------------
    def canvas(self, width=120, height=36):
        return Canvas(width, height, self.palette['surface'])

    def render(self, tab, data, view=None, width=120, height=36, range_hours=24, sort='cpu'):
        view = self.view if view is None else view
        canvas = self.canvas(width, height)
        draw_detail_header(canvas, Rect(0, 0, width, HEADER_ROWS), view, self.palette, tab)
        rect = Rect(0, HEADER_ROWS, width, max(0, height - HEADER_ROWS))
        total = draw_tab(canvas, rect, tab, view, data, self.palette,
                         range_hours=range_hours, sort=sort)
        self.assertGreaterEqual(total, 0)
        return canvas

    @staticmethod
    def text_of(canvas):
        return '\n'.join(canvas.row_text(row) for row in range(canvas.height))

    # -- header -----------------------------------------------------------
    def test_header_data_line_and_seven_tabs(self):
        canvas = self.canvas()
        boxes = draw_detail_header(canvas, Rect(0, 0, 120, HEADER_ROWS),
                                   self.view, self.palette, 0)
        data = canvas.row_text(0)
        self.assertIn('api-backend', data)
        self.assertIn('encendida', data)
        self.assertIn('e2-small', data)
        self.assertIn('us-central1-a', data)
        self.assertIn('34.122.10.7 / 10.128.0.2', data)
        self.assertIn('US$/h', data)
        self.assertEqual(len(boxes), len(TABS))
        self.assertEqual(len(TABS), 7)
        self.assertIn('1 Resumen', canvas.row_text(2))
        self.assertIn('7 Historial', canvas.row_text(2))
        self.assertIn('─', canvas.row_text(3))

    def test_header_says_precio_desconocido_for_unknown_type(self):
        inst = Instance(project='p', name='raro', zone='mars-1-a', status='RUNNING',
                        machine_type='custom-99', external_ip=None, internal_ip='10.0.0.2',
                        spot=False, os='', disks=[], network='default', tags=[], started=None)
        view = VmView(inst=inst, sample=make_sample())
        canvas = self.canvas()
        draw_detail_header(canvas, Rect(0, 0, 120, HEADER_ROWS), view, self.palette, 0)
        self.assertIn('precio desconocido', canvas.row_text(0))

    # -- Resumen ----------------------------------------------------------
    def test_resumen_has_cpu_ram_disk_net_blocks(self):
        canvas = self.render(0, full_data())
        text = self.text_of(canvas)
        for block in ('CPU', 'NÚCLEOS', 'RAM', 'DISCO', 'RED', 'PROCESOS', 'SALUD'):
            self.assertIn(block, text)
        self.assertIn('11,2 / 16 GB', text)
        self.assertIn('88,0 / 100,0 GB', text)
        self.assertIn('↓ 1,2 MB/s', text)
        self.assertIn('↑ 0,3 MB/s', text)
        self.assertIn('node server.js', text)
        self.assertIn('certbot.service', text)

    def test_resumen_marks_full_disk_and_failed_unit(self):
        view = VmView(inst=make_instance(), sample=make_sample(), state='activo', failed='certbot.service')
        canvas = self.render(0, full_data(), view=view)
        text = self.text_of(canvas)
        self.assertIn('▲', text)
        row = next(row for row in (canvas.row_text(y) for y in range(canvas.height))
                   if 'certbot.service' in row)
        column = row.index('certbot.service')
        self.assertEqual(canvas.cell(column, self.row_of(canvas, row))[1].fg, self.palette['error'])

    def row_of(self, canvas, wanted):
        for y in range(canvas.height):
            if canvas.row_text(y) == wanted:
                return y
        raise AssertionError('row not found')

    # -- Procesos ---------------------------------------------------------
    def test_procesos_sorts_by_cpu_and_by_ram(self):
        by_cpu = self.text_of(self.render(1, full_data(), sort='cpu'))
        self.assertIn('node server.js', by_cpu)
        self.assertIn('ordenar', by_cpu)
        # The highest-CPU process is listed before the lowest one.
        self.assertLess(by_cpu.index('node server.js'), by_cpu.index('node worker.js'))

        by_ram = self.text_of(self.render(1, full_data(), sort='ram'))
        self.assertLess(by_ram.index('node server.js'), by_ram.index('node worker.js'))
        self.assertIn('2,1 G', by_ram)

    # -- Red --------------------------------------------------------------
    def test_red_flags_open_firewall_rule(self):
        canvas = self.render(3, full_data())
        rows = [canvas.row_text(y) for y in range(canvas.height)]
        flagged = next(row for row in rows if 'allow-3000-dev' in row)
        self.assertIn('!', flagged)
        self.assertIn('0.0.0.0/0', flagged)
        safe = next(row for row in rows if 'allow-iap-ssh' in row)
        self.assertNotIn('!', safe)

    def test_red_highlights_ports_exposed_to_everyone(self):
        canvas = self.render(3, full_data())
        rows = [canvas.row_text(y) for y in range(canvas.height)]
        exposed = next(row for row in rows if '0.0.0.0' in row and 'nginx' in row)
        column = exposed.index('0.0.0.0')
        self.assertEqual(canvas.cell(column, self.row_of(canvas, exposed))[1].fg,
                         self.palette['tertiary'])
        local = next(row for row in rows if '127.0.0.1' in row)
        column = local.index('127.0.0.1')
        self.assertEqual(canvas.cell(column, self.row_of(canvas, local))[1].fg,
                         self.palette['onSurfaceVariant'])

    def test_limited_tab_says_necesita_permisos(self):
        data = full_data()
        data.tabs['ports'] = TabData('ports', list(PORTS), limited=True)
        self.assertIn('necesita permisos', self.text_of(self.render(3, data)))

        data = full_data()
        data.tabs['journal'] = TabData('journal', list(JOURNAL), limited=True)
        self.assertIn('necesita permisos', self.text_of(self.render(5, data)))

        data = full_data()
        data.tabs['du'] = TabData('du', [], limited=True)
        self.assertIn('necesita permisos', self.text_of(self.render(2, data)))

    def test_tab_error_shows_its_message(self):
        data = full_data()
        data.tabs.pop('ports')
        data.errors['ports'] = 'ss no está instalado'
        text = self.text_of(self.render(3, data))
        self.assertIn('ss no está instalado', text)

    # -- Disco ------------------------------------------------------------
    def test_disco_lists_mounts_du_and_gcp_disks(self):
        text = self.text_of(self.render(2, full_data()))
        self.assertIn('PARTICIONES', text)
        self.assertIn('/data', text)
        self.assertIn('LO QUE MÁS OCUPA EN /', text)
        self.assertIn('/var/lib/docker', text)
        self.assertIn('41,2 GB', text)
        self.assertIn('DISCOS DE GCP', text)
        self.assertIn('api-backend', text)
        self.assertIn('pd-balanced', text)
        self.assertIn('snapshot:', text)

    # -- Servicios --------------------------------------------------------
    def test_servicios_lists_failed_units_and_containers(self):
        text = self.text_of(self.render(4, full_data()))
        self.assertIn('SYSTEMD', text)
        self.assertIn('certbot.service', text)
        self.assertIn('failed', text)
        self.assertIn('CONTENEDORES', text)
        self.assertIn('api', text)
        self.assertIn('ghcr.io/app/api:1.8.2', text)
        self.assertIn('worker', text)

    # -- Registro ---------------------------------------------------------
    def test_registro_colours_journal_by_priority(self):
        canvas = self.render(5, full_data())
        text = self.text_of(canvas)
        self.assertIn('JOURNAL', text)
        self.assertIn('ECONNREFUSED', text)
        row = next(row for row in (canvas.row_text(y) for y in range(canvas.height))
                   if 'ECONNREFUSED' in row)
        column = row.index('Error')
        self.assertEqual(canvas.cell(column, self.row_of(canvas, row))[1].fg, self.palette['error'])

    # -- Historial --------------------------------------------------------
    def test_historial_lists_operations_and_toggles_range(self):
        canvas = self.render(6, full_data(), range_hours=24)
        text = self.text_of(canvas)
        self.assertIn('últimas 24 h', text)
        self.assertIn('OPERACIONES DE GCP', text)
        self.assertIn('start', text)
        self.assertIn('ana@example.com', text)
        self.assertIn('Ops Agent', text)

        other = self.text_of(self.render(6, full_data(), range_hours=168))
        self.assertIn('últimos 7 días', other)
        self.assertNotIn('últimas 24 h', other)
        # The fixture's start operation falls inside the 7-day range: it is marked on
        # the graph and listed below it.
        self.assertIn('▲', other)

    def test_historial_missing_points_says_cargando(self):
        data = DetailData()
        text = self.text_of(self.render(6, data))
        self.assertIn('últimas 24 h', text)
        self.assertIn('cargando…', text)

    # -- missing data -----------------------------------------------------
    def test_missing_data_says_cargando(self):
        data = DetailData()
        for tab in (2, 3, 4, 5, 6):
            self.assertIn('cargando…', self.text_of(self.render(tab, data)),
                          f'tab {TABS[tab]}')

    def test_empty_data_says_what_is_empty(self):
        data = empty_data()
        self.assertIn('sin datos', self.text_of(self.render(2, data)))
        self.assertIn('sin puertos', self.text_of(self.render(3, data)))
        self.assertIn('sin reglas', self.text_of(self.render(3, data)))
        self.assertIn('sin servicios con fallo', self.text_of(self.render(4, data)))
        self.assertIn('sin contenedores', self.text_of(self.render(4, data)))
        self.assertIn('sin entradas', self.text_of(self.render(5, data)))
        self.assertIn('sin datos de Monitoring', self.text_of(self.render(6, data)))
        self.assertIn('sin operaciones', self.text_of(self.render(6, data)))

    def tall_text(self, tab, data):
        canvas = self.render(tab, data, height=60)
        return '\n'.join(canvas.row_text(y) for y in range(60))

    def test_command_errors_in_tab_data_are_shown_not_read_as_empty(self):
        data = full_data()
        data.tabs['failed'] = TabData('failed', [], error='no se pudo leer')
        data.tabs['docker'] = TabData('docker', [], error='docker no está instalado')
        text = self.tall_text(TABS.index('Servicios'), data)
        self.assertIn('no se pudo leer', text)
        self.assertIn('docker no está instalado', text)
        self.assertNotIn('sin servicios con fallo', text)
        self.assertNotIn('sin contenedores', text)

    def test_ipv6_listeners_are_parsed(self):
        data = full_data()
        data.tabs['ports'] = TabData('ports', [
            'State  Recv-Q Send-Q Local Address:Port Peer Address:Port Process',
            'LISTEN 0      128             :::22             :::*     users:(("sshd",pid=1,fd=4))',
            'LISTEN 0      128     [fe80::1]:8080         [::]:*     users:(("app",pid=2,fd=4))',
        ])
        text = self.tall_text(TABS.index('Red'), data)
        self.assertIn('sshd', text)
        self.assertIn('8080', text)
        self.assertNotIn('sin puertos a la escucha', text)

    def test_deny_and_disabled_rules_are_not_exposure(self):
        data = full_data()
        data.firewall = [
            {'name': 'deny-all', 'direction': 'INGRESS', 'sourceRanges': ['0.0.0.0/0'],
             'denied': [{'IPProtocol': 'all'}]},
            {'name': 'old-3000', 'direction': 'INGRESS', 'disabled': True,
             'sourceRanges': ['0.0.0.0/0'], 'allowed': [{'IPProtocol': 'tcp', 'ports': ['3000']}]},
        ]
        text = self.tall_text(TABS.index('Red'), data)
        self.assertNotIn('expuesta', text)
        self.assertIn('deniega', text)
        self.assertIn('desactivada', text)

    def test_registro_keeps_the_newest_entries(self):
        data = full_data()
        data.tabs['journal'] = TabData('journal', [
            f'2026-11-04T10:{index:02d}:00+0000 host app[1]: entrada {index}' for index in range(25)])
        lines = body_lines(TABS.index('Registro'), self.view, data, self.palette, 120)
        text = '\n'.join(''.join(piece for piece, _style in line) for line in lines)
        self.assertIn('entrada 24', text)

    # -- body_lines / draw_tab contract -----------------------------------
    def test_body_lines_returns_styled_segments_and_draw_tab_reports_height(self):
        lines = body_lines(0, self.view, full_data(), self.palette, 120)
        self.assertGreater(len(lines), 10)
        for line in lines:
            for text, style in line:
                self.assertIsInstance(text, str)
                self.assertIsInstance(style.fg, tuple)
        canvas = self.canvas()
        rect = Rect(0, HEADER_ROWS, 120, 10)
        total = draw_tab(canvas, rect, 0, self.view, full_data(), self.palette)
        self.assertEqual(total, len(lines))

    def test_draw_tab_clips_and_scrolls(self):
        data = full_data()
        full = self.canvas(120, 60)
        draw_tab(full, Rect(0, HEADER_ROWS, 120, 56), 1, self.view, data, self.palette)
        top = [full.row_text(y) for y in range(HEADER_ROWS, HEADER_ROWS + 6)]
        # Nothing is painted above the rect.
        blank = self.canvas(120, 60)
        draw_tab(blank, Rect(0, HEADER_ROWS, 120, 56), 1, self.view, data, self.palette)
        self.assertEqual(blank.row_text(0), ' ' * 120)
        self.assertIn('PID', top[0])

        scrolled = self.canvas(120, 60)
        draw_tab(scrolled, Rect(0, HEADER_ROWS, 120, 6), 1, self.view, data,
                 self.palette, scroll=2)
        self.assertNotEqual(scrolled.row_text(HEADER_ROWS), top[0])
        self.assertNotIn('PID', scrolled.row_text(HEADER_ROWS))

    # -- sizes ------------------------------------------------------------
    def test_every_tab_renders_at_any_size_with_any_data(self):
        variants = {'missing': DetailData(), 'empty': empty_data(), 'full': full_data()}
        sizes = ((60, 16), (80, 24), (120, 36), (200, 60))
        for label, data in variants.items():
            for width, height in sizes:
                for tab in range(len(TABS)):
                    with self.subTest(data=label, size=(width, height), tab=TABS[tab]):
                        canvas = self.render(tab, data, width=width, height=height)
                        self.assertEqual(canvas.width, width)
                        self.assertEqual(canvas.height, height)


if __name__ == '__main__':
    unittest.main()
