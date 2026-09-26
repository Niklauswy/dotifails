"""Process table interaction regressions; all process actions use a fake backend."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).parents[1]/'apps/orbit'))
from PySide6.QtCore import Qt, QItemSelectionModel, QEvent
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QKeyEvent
from processes_window import ProcessesWindow

def row(pid,name,cpu=0,ppid=1,start='100'):
    return dict(pid=pid,name=name,cpu=cpu,ppid=ppid,start=start,uid=os.getuid(),
        user='usuario',state='S',memory=104857600,threads=4,nice=0,age=120,
        read_rate=4096,write_rate=0)

class ProcessUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.model=Mock();self.model.action_reason.return_value=None
        self.w=ProcessesWindow(self.model);self.w.scan=Mock();self.w.show()
        self.w.rows=[row(10,'terminal',9),row(20,'python',80,10),row(30,'node',100)]
        self.w.render();self.app.processEvents()
    def tearDown(self):
        self.w.close();self.app.processEvents();self.w.deleteLater();self.app.processEvents()
    def select(self,*pids):
        self.w.tree.clearSelection()
        for pid in pids:self.w.items[(pid,'100')].setSelected(True)
        self.w.tree.setCurrentItem(self.w.items[(pids[0],'100')],0,QItemSelectionModel.NoUpdate)
    def test_numeric_sort_and_stable_multiple_selection(self):
        self.assertEqual(self.w.tree.topLevelItem(0).text(1),'30')
        self.select(10,20);self.w.rows=list(reversed(self.w.rows));self.w.rows[0]['cpu']=1;self.w.render()
        self.assertEqual({r['pid'] for r in self.w.selected()},{10,20});self.assertEqual(self.w.current()['pid'],10)
    def test_tree_preserves_parent_context_and_filters(self):
        self.w.view.setCurrentIndex(1);self.w.search.setText('pid:20')
        self.assertEqual(self.w.tree.topLevelItemCount(),1)
        self.assertEqual(self.w.items[(20,'100')].parent(),self.w.items[(10,'100')])
        self.assertTrue(self.w.items[(10,'100')].isExpanded())
    def test_reused_pid_is_not_selected_and_empty_result_has_no_action(self):
        self.select(20);self.w.rows=[row(20,'replacement',start='200')];self.w.render()
        self.assertFalse(self.w.selected());self.assertFalse(self.w.normal.isEnabled())
        self.w.search.setText('nothing-matches');self.assertFalse(self.w.selected())
        self.assertIn('Sin procesos',self.w.tree.topLevelItem(0).text(0))
    def test_freezing_and_manual_refresh(self):
        self.w.freeze.click();before=list(self.w.rows)
        data=dict(rows=[row(99,'new')],summary=dict(cpu=25,memory=100,total_memory=200,
            swap=0,total_swap=0,count=1,running=1),details=None,manual=False)
        self.w.loaded(data);self.assertEqual(self.w.rows,before);self.assertFalse(self.w.timer.isActive())
        data['manual']=True;self.w.loaded(data);self.assertEqual(self.w.rows[0]['pid'],99)
    def test_cancel_and_confirm_batch_action(self):
        self.select(10,20)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Cancel):self.w.act('kill')
        self.model.act.assert_not_called()
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):self.w.act('pause')
        self.assertEqual(self.model.act.call_count,2)
        self.assertEqual({c.args[0]['pid'] for c in self.model.act.call_args_list},{10,20})
        self.assertTrue(all(c.args[1]=='pause' for c in self.model.act.call_args_list))
    def test_search_keyboard_and_contextual_actions(self):
        self.w.search.setText('pid:20');self.w.search.setFocus();self.app.sendEvent(self.w.search,QKeyEvent(QEvent.KeyPress,Qt.Key_Down,Qt.NoModifier))
        self.assertEqual(self.w.current()['pid'],20)
        self.w.actions();self.app.processEvents();self.assertTrue(self.w.popup.isVisible())
        names=[entry[0] for entry in self.w.popup.entries]
        self.assertIn('Copiar PID',names);self.assertIn('Forzar cierre…',names);self.w.popup.close()

if __name__=='__main__':unittest.main()
