"""LANShare: command line (wysun lanshare …)."""
import contextlib
import io
import os
import random
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps/python'))

from wysun_lanshare import options  # noqa: E402


def parse(*argv):
    return options.parse(list(argv), rng=random.Random(7))


class OptionsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        (self.dir / 'a.txt').write_text('a')
        (self.dir / 'sub').mkdir()
        self.cwd = os.getcwd()
        os.chdir(self.dir)

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def fails(self, *argv):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parse(*argv)

    def test_defaults(self):
        o = parse()
        self.assertEqual(o.paths, [str(self.dir)])
        self.assertFalse(o.uploads)
        self.assertIsNone(o.password)
        self.assertEqual((o.port, o.port_given, o.idle, o.stop), (8000, False, 3600, None))

    def test_uploads_and_port(self):
        o = parse('sub', '--subidas', '--puerto', '9000')
        self.assertTrue(o.uploads)
        self.assertEqual((o.port, o.port_given), (9000, True))
        self.assertEqual(parse('-p', '9001').port, 9001)
        self.assertEqual(parse('--port', '9002').port, 9002)
        self.assertFalse(parse('--readonly').uploads)

    def test_password(self):
        generated = parse('--clave').password
        self.assertEqual(len(generated), 6)
        self.assertTrue(set(generated) <= set(options.ALPHABET))
        self.assertFalse(set('l1o0') & set(options.ALPHABET))
        self.assertEqual(parse('--clave', 'gato123').password, 'gato123')
        self.assertEqual(parse('sub', '--clave', 'gato123').paths, [str(self.dir / 'sub')])

    def test_password_before_a_path_is_its_value_only_when_not_a_path(self):
        o = parse('--clave', 'sub')
        self.assertEqual(o.paths, [str(self.dir / 'sub')])
        self.assertEqual(len(o.password), 6)

    def test_idle(self):
        self.assertEqual(parse('--inactivo', '30m').idle, 1800)
        self.assertEqual(parse('--inactivo', '2h').idle, 7200)
        self.assertEqual(parse('--inactivo', '90').idle, 90 * 60)
        self.assertIsNone(parse('--sin-limite').idle)
        self.fails('--inactivo', '5x')

    def test_uploads_only_for_one_folder(self):
        self.fails('--subidas', 'a.txt')
        self.fails('--subidas', 'sub', 'a.txt')

    def test_uploads_refused_where_a_file_could_become_a_command(self):
        home = self.dir / 'casa'
        (home / 'bin').mkdir(parents=True)
        with unittest.mock.patch.dict(os.environ, {'HOME': str(home), 'PATH': f'{home / "bin"}:/usr/bin'}):
            self.fails(str(home), '--subidas')
            self.fails('/', '--subidas')
            self.fails(str(home / 'bin'), '--subidas')
            self.assertTrue(parse('sub', '--subidas').uploads)

    def test_several_paths(self):
        self.assertEqual(parse('a.txt', 'sub').paths, [str(self.dir / 'a.txt'), str(self.dir / 'sub')])

    def test_missing_path(self):
        self.fails('nada')

    def test_stop(self):
        self.assertEqual(parse('--detener', '123').stop, 123)


if __name__ == '__main__':
    unittest.main()
