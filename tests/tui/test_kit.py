"""wysun_core.tui.kit: the shared look of Wysun terminal utilities (header, crumbs, footer, chips,
toast, help, half-block pictures) and that every utility is transparent and uses it."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/python'))

from wysun_core import theme  # noqa: E402
from wysun_core.tui import App, Canvas, Palette, kit  # noqa: E402
from wysun_core.tui.testing import VirtualTerminal  # noqa: E402


class KitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = mock.patch.dict(os.environ, {'WYSUN_REDUCED_MOTION': '1', 'WYSUN_THEME': ''})
        env.start()
        self.addCleanup(env.stop)
        theme.invalidate()
        self.palette = Palette.load(self.tmp.name)
        self.s = kit.Painter(self.palette)

    def canvas(self, width=80, height=3):
        return Canvas(width, height, self.palette['surface'])

    def test_header_with_tabs_trail_and_status(self):
        c = self.canvas()
        kit.header(c, self.s, 'Wysun Drive', kit.GLYPH['cloud'], tabs=['Subir', 'Recientes'], active=1,
                   status='nico · cloud.example')
        row = c.row_text(0)
        self.assertIn('Wysun Drive', row)
        self.assertIn(' 2 Recientes ', row)
        self.assertTrue(row.rstrip().endswith('● nico · cloud.example'))
        _, chip_style = c.cell(1, 0)
        self.assertEqual(chip_style.bg, self.palette['primary'])
        c = self.canvas(40)
        kit.header(c, self.s, 'Wysun Cloud', kit.GLYPH['cloud'], trail=['mosaico', 'proyecto-muy-largo', 'vm'],
                   status='9 s')
        self.assertIn('mosaico › ', c.row_text(0))

    def test_crumbs_collapse_the_middle(self):
        c = self.canvas(40)
        kit.crumbs(c, self.s, 1, ['~', 'Documentos', 'Universidad', 'Semestre-2026', 'Proyecto-final'], 'nota')
        row = c.row_text(1)
        self.assertIn('…', row)
        self.assertIn('Proyecto-final', row)
        self.assertTrue(row.rstrip().endswith('nota'))

    def test_footer_hints_stop_at_the_edge_and_chips(self):
        c = self.canvas(30)
        kit.footer(c, self.s, [('u', 'subir'), ('q', 'salir'), ('Tab', 'Recientes'), ('?', 'teclas')])
        row = c.row_text(2)
        self.assertIn('u subir', row)
        self.assertNotIn('teclas', row)
        width = kit.chip(c, self.s, 0, 0, 'con link', on=False)
        self.assertEqual(width, len(' con link '))
        self.assertEqual(c.cell(0, 0)[1].bg, self.palette['surfaceContainerHigh'])

    def test_pixels_are_half_blocks(self):
        c = self.canvas(4, 2)
        kit.pixels(c, 0, 0, [[((255, 0, 0), (0, 0, 255))]])
        char, style = c.cell(0, 0)
        self.assertEqual((char, style.fg, style.bg), ('▀', (255, 0, 0), (0, 0, 255)))

    def test_toast_and_help_layers(self):
        term = VirtualTerminal(80, 20)
        self.addCleanup(term.close)
        app = App(term=term, home=self.tmp.name)
        self.addCleanup(app.close)
        toast, help_layer = kit.Toast(), kit.HelpLayer(lambda: [('q', 'salir'), ('?', 'teclas')])
        app.layers.extend([toast, help_layer])
        app.run_for(0.02)
        toast.show(app, 'Link copiado', seconds=0.2)
        app.run_for(0.05)
        self.assertIn('● Link copiado', term.canvas_text()[-1])
        app.run_for(0.3)
        self.assertFalse(toast.visible)
        self.assertNotIn('Link copiado', term.canvas_text()[-1])
        help_layer.open(app)
        app.run_for(0.05)
        screen = '\n'.join(term.canvas_text())
        self.assertIn('Teclas', screen)
        self.assertIn('salir', screen)
        help_layer.close(app)
        app.run_for(0.05)
        self.assertNotIn('Teclas', '\n'.join(term.canvas_text()))


class SameBaseTests(unittest.TestCase):
    """Every Wysun terminal utility is transparent and draws its chrome with the kit."""

    def test_utilities_use_the_kit(self):
        from wysun_cloud.ui.cloudapp import CloudApp
        from wysun_drive.ui.app import DriveApp
        for cls in (CloudApp, DriveApp):
            self.assertTrue(cls.transparent, cls.__name__)
        for path in ('apps/python/wysun_cloud/ui/cloudapp.py', 'apps/python/wysun_drive/ui/view.py',
                     'apps/python/wysun_drive/ui/app.py'):
            text = (ROOT / path).read_text()
            self.assertIn('kit.', text, path)
        for path in ('apps/python/wysun_cloud/ui/cloudapp.py', 'apps/python/wysun_drive/ui/app.py'):
            text = (ROOT / path).read_text()
            self.assertIn('kit.Toast()', text, path)
            self.assertIn('kit.HelpLayer(', text, path)


if __name__ == '__main__':
    unittest.main()
