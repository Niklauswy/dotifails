#!/usr/bin/env python3
"""Native tools panel: routing, project data, background jobs and server lifecycle."""
import contextlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'apps/orbit'))
from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QApplication
from tools_window import ToolsWindow,load_projects,cli_argv

class ToolsUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.w=ToolsWindow(test=True)
    def tearDown(self):self.w.shutdown_jobs();self.w.close();self.app.processEvents();self.tmp.cleanup()
    def wait(self,predicate,seconds=5):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            self.app.processEvents()
            if predicate():return
            time.sleep(.02)
        self.fail('No se completó el trabajo en el plazo.')
    def project(self):
        p=self.root/'project';p.mkdir();(p/'package.json').write_text(json.dumps({'packageManager':'npm@11','scripts':{'dev':'vite','build':'vite build'},'dependencies':{'vite':'1'}}));return p
    def test_project_add_select_deduplicate_and_forget_preserves_folder(self):
        p=self.project();self.w.add_project(p);self.w.add_project(p)
        self.assertEqual(self.w.project_list.count(),1);self.assertEqual(self.w.task.count(),2);self.assertTrue(self.w.task_button.isEnabled())
        self.w.forget_project();self.assertTrue((p/'package.json').exists());self.assertFalse(self.w.task_button.isEnabled())
    def test_terminal_uses_exact_project_argv(self):
        p=self.project();self.w.add_project(p);self.w.test=False
        with patch('tools_window.launch') as launch:
            self.w.run_task();argv=launch.call_args[0][0]
        self.assertIn(str(p),argv);self.assertIn('dev',argv);self.assertNotIn('sh',argv)
    def test_project_jobs_show_structured_result_and_missing_env(self):
        p=self.project();self.w.add_project(p);self.w.project_check('doctor');self.wait(lambda:not self.w.jobs)
        self.assertIn('Gestor del proyecto',self.w.project_output.toPlainText())
        self.w.project_check('env');self.wait(lambda:not self.w.jobs);self.assertIn('No existe',self.w.project_output.toPlainText())
    def test_all_pages_and_themes_render(self):
        from theme_tokens import refresh_widgets
        self.w.show()
        for theme in ('tokyo','severance','space-black'):
            with patch.dict(os.environ,{'ORBIT_THEME':theme}):
                refresh_widgets()
                for index in range(4):
                    self.w.page(index);self.app.processEvents();self.assertFalse(self.w.grab().isNull())
        self.assertEqual(self.w.pages.count(),4)
    def test_diagnostic_requires_explicit_target(self):
        self.w.audit_kind.setCurrentIndex(2)
        with patch.object(self.w,'run_job') as run:
            self.w.audit();run.assert_not_called()
        self.assertIn('objetivo',self.w.status.text())
    def test_share_local_start_stop_and_close(self):
        with socket.socket() as probe:probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
        self.w.share_path.setText(str(self.root));self.w.share_port.setValue(port);self.w.start_share()
        self.wait(lambda:self.w.open_share_button.isEnabled())
        with socket.create_connection(('127.0.0.1',port),timeout=2) as conn:
            conn.sendall(b'GET / HTTP/1.0\r\n\r\n');self.assertIn(b'200',conn.recv(1024))
        self.w.close();self.wait(lambda:self.w.sharing.state()==QProcess.NotRunning)
        self.assertFalse(self.w.open_share_button.isEnabled())
    def test_loaded_projects_are_private_metadata_and_validate_shape(self):
        p=self.root/'projects.json';p.write_text('{"projects":["/tmp/one","/tmp/one"]}')
        self.assertEqual(load_projects(p),['/tmp/one'])
    def test_reset_rows_are_read_only_and_show_empty_state(self):
        self.w.show_resets('[]');self.assertEqual(self.w.resets_table.rowCount(),0)
        self.w.show_resets('[{"name":"lab","service":"test","resets":[{"label":"weekly","remaining_seconds":3601}]}]')
        self.assertEqual(self.w.resets_table.item(0,3).text(),'1 h 0 min')
    def test_cancel_long_job_releases_controls(self):
        self.w.run_job([sys.executable,'-c','import time;time.sleep(15)'],self.w.audit_output)
        self.wait(lambda:self.w.jobs[0].state()==QProcess.Running);self.w.cancel_jobs();self.wait(lambda:not self.w.jobs)
        self.assertTrue(self.w.audit_button.isEnabled());self.assertFalse(self.w.cancel_audit.isEnabled())

if __name__=='__main__':unittest.main()
