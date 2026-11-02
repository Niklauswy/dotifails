import importlib.util
import errno
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

repository = Path(__file__).resolve().parent
if repository.name == 'tests':
    repository = repository.parent
spec = importlib.util.spec_from_file_location('wysun_files.ops', repository / 'apps/python/wysun_files/ops.py')
ops = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ops)


class FileOperationsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'document.txt'
        self.source.write_text('original')
        self.dest = self.root / 'destination'
        self.dest.mkdir()

    def test_progress_is_reported_after_each_item(self):
        second = self.root / 'b.txt'
        second.write_text('b')
        seen = []
        ops.execute_operation('copy', [str(self.source), str(second)], str(self.dest), progress=lambda done, total: seen.append((done, total)))
        self.assertEqual(seen, [(1, 2), (2, 2)])

    def test_restore_from_trash_puts_the_file_back_and_never_overwrites(self):
        trash = self.root / 'Trash'
        (trash / 'files').mkdir(parents=True)
        (trash / 'info').mkdir()
        original = self.root / 'notas con espacio.txt'
        (trash / 'files/notas con espacio.txt').write_text('hola')
        (trash / 'info/notas con espacio.txt.trashinfo').write_text(
            '[Trash Info]\nPath=' + str(original).replace(' ', '%20') + '\nDeletionDate=2026-11-01T10:00:00\n')
        self.assertEqual(ops.trashed_name(str(original), trash), 'notas con espacio.txt')
        ops.restore_from_trash(str(original), trash)
        self.assertEqual(original.read_text(), 'hola')
        self.assertFalse((trash / 'info/notas con espacio.txt.trashinfo').exists())
        (trash / 'files/notas con espacio.txt').write_text('otra')
        (trash / 'info/notas con espacio.txt.trashinfo').write_text(
            '[Trash Info]\nPath=' + str(original).replace(' ', '%20') + '\nDeletionDate=2026-11-01T11:00:00\n')
        with self.assertRaises(FileExistsError):
            ops.restore_from_trash(str(original), trash)
        self.assertEqual(original.read_text(), 'hola')
        self.assertTrue((trash / 'files/notas con espacio.txt').exists())

    def test_restore_picks_the_newest_entry_for_a_path(self):
        trash = self.root / 'Trash'
        (trash / 'files').mkdir(parents=True)
        (trash / 'info').mkdir()
        original = self.root / 'a.txt'
        for name, date in (('a.txt', '2026-11-01T10:00:00'), ('a.2.txt', '2026-11-01T12:00:00')):
            (trash / 'files' / name).write_text(name)
            (trash / 'info' / (name + '.trashinfo')).write_text(f'[Trash Info]\nPath={original}\nDeletionDate={date}\n')
        self.assertEqual(ops.trashed_name(str(original), trash), 'a.2.txt')
        self.assertIsNone(ops.trashed_name(str(self.root / 'nada'), trash))

    def test_copy_preserves_original_and_rejects_collision(self):
        result = ops.execute_operation('copy', [str(self.source)], str(self.dest))
        self.assertEqual(Path(result[0]).read_text(), 'original')
        self.source.write_text('changed')
        with self.assertRaises(FileExistsError):
            ops.execute_operation('copy', [str(self.source)], str(self.dest))
        self.assertEqual((self.dest / self.source.name).read_text(), 'original')

    def test_symlink_copy_preserves_link_including_dangling(self):
        link = self.root / 'link'
        link.symlink_to('missing')
        ops.execute_operation('copy', [str(link)], str(self.dest))
        self.assertTrue((self.dest / 'link').is_symlink())
        self.assertEqual((self.dest / 'link').readlink(), Path('missing'))
        self.assertEqual(Path(ops.unique_destination(str(self.dest), 'link')).name, 'link (2)')

    def test_directory_symlinks_are_not_followed(self):
        folder = self.root / 'folder'
        folder.mkdir()
        (folder / 'linked').symlink_to(self.source)
        ops.execute_operation('copy', [str(folder)], str(self.dest))
        self.assertTrue((self.dest / 'folder/linked').is_symlink())

    def test_self_copy_through_symlink_is_rejected(self):
        folder = self.root / 'folder'
        folder.mkdir()
        alias = self.root / 'alias'
        alias.symlink_to(folder, target_is_directory=True)
        for kind in ('copy', 'move'):
            with self.assertRaises(ValueError):
                ops.execute_operation(kind, [str(folder)], str(alias))

    def test_rename_and_move(self):
        renamed = self.root / 'renamed.txt'
        self.assertEqual(ops.execute_operation('rename', [str(self.source)], str(renamed)), [str(renamed)])
        self.assertFalse(self.source.exists())
        ops.execute_operation('move', [str(renamed)], str(self.dest))
        self.assertEqual((self.dest / renamed.name).read_text(), 'original')
        self.assertFalse(renamed.exists())

    def test_preflight_batch_collision_does_not_move_anything(self):
        extra = self.root / 'extra'
        extra.write_text('extra')
        (self.dest / 'extra').write_text('existing')
        with self.assertRaises(FileExistsError):
            ops.execute_operation('move', [str(self.source), str(extra)], str(self.dest))
        self.assertTrue(self.source.exists())

    def test_copy_failure_cleans_only_new_destination(self):
        with patch.object(ops.shutil, 'copy2', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                ops.execute_operation('copy', [str(self.source)], str(self.dest))
        self.assertFalse((self.dest / self.source.name).exists())
        self.assertEqual(self.source.read_text(), 'original')

    def test_trash_uses_gio_and_never_falls_back_to_delete(self):
        with patch.object(ops.subprocess, 'run') as run:
            run.return_value.returncode = 1
            run.return_value.stderr = 'Trash unavailable'
            with self.assertRaises(OSError):
                ops.execute_operation('trash', [str(self.source)])
            self.assertEqual(run.call_args.args[0], ['gio', 'trash', '--', str(self.source)])
        self.assertTrue(self.source.exists())

    def test_names_and_mkdir(self):
        for name in ('', '.', '..', 'a/b', 'a\x00b'):
            with self.assertRaises(ValueError):
                ops.validate_name(name)
        target = self.root / 'Nueva carpeta'
        ops.execute_operation('mkdir', [], str(target))
        self.assertTrue(target.is_dir())
        with self.assertRaises(FileExistsError):
            ops.execute_operation('mkdir', [], str(target))

    def test_empty_source_is_not_interpreted_as_working_directory(self):
        with self.assertRaises(ValueError):
            ops.execute_operation('trash', [''])

    def test_cross_device_move_copies_then_removes_original(self):
        with patch.object(ops, '_rename_exclusive', side_effect=OSError(errno.EXDEV, 'different filesystem')):
            result = ops.execute_operation('move', [str(self.source)], str(self.dest))
        self.assertEqual(result, [str(self.dest / self.source.name)])
        self.assertEqual(Path(result[0]).read_text(), 'original')
        self.assertFalse(self.source.exists())

    def test_cross_device_move_copy_failure_preserves_original(self):
        with patch.object(ops, '_rename_exclusive', side_effect=OSError(errno.EXDEV, 'different filesystem')):
            with patch.object(ops.shutil, 'copy2', side_effect=OSError(errno.ENOSPC, 'disk full')):
                with self.assertRaises(OSError):
                    ops.execute_operation('move', [str(self.source)], str(self.dest))
        self.assertEqual(self.source.read_text(), 'original')
        self.assertFalse((self.dest / self.source.name).exists())


if __name__ == '__main__':
    unittest.main()
