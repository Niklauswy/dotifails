"""Synthetic pixel and persistence contracts; no desktop/media capture."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import json
from pathlib import Path
import tempfile
import unittest
from dataclasses import replace
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage,QColor
from wybieshot.schema import Rect,Layer,CaptureRequest
from wybieshot.document import Document
from wybieshot.storage import Storage
from wybieshot.capture import CaptureEngine,FrozenDesktop

app=QApplication.instance() or QApplication([])

def image(color='#ffffff',width=120,height=90):
    i=QImage(width,height,QImage.Format_ARGB32);i.fill(QColor(color));return i

class DocumentTests(unittest.TestCase):
    def test_masks_crop_undo_reopen_export(self):
        doc=Document(image('#ec3456'))
        source=doc.original;source.fill(QColor('blue'))
        self.assertEqual(doc.original.pixelColor(0,0).name(),'#ec3456')
        layer=Layer('mask',((10,10),(50,45)),color='#000000')
        doc.add_layer(layer);doc.set_crop(Rect(5,5,70,60))
        result=doc.render();self.assertEqual(result.size().width(),70)
        self.assertEqual(result.pixelColor(10,10).name(),'#000000')
        self.assertEqual(result.pixelColor(0,0).name(),'#ec3456')
        self.assertTrue(doc.undo());self.assertIsNone(doc.crop)
        self.assertTrue(doc.undo());self.assertEqual(doc.render(),doc.original)
        self.assertTrue(doc.redo());self.assertTrue(doc.redo())
        with tempfile.TemporaryDirectory() as root:
            s=Storage(Path(root)/'private');id=s.save(doc);loaded=s.load(id)
            self.assertEqual(loaded.render(),doc.render());self.assertEqual(loaded.layers,doc.layers)
            self.assertFalse(loaded.can_undo)
            p=s.export(doc,Path(root)/'out.png');self.assertEqual(QImage(str(p)),doc.render())
            with self.assertRaises(FileExistsError):s.export(doc,p)
            s.export(doc,Path(root)/'out.jpg');self.assertFalse(QImage(str(Path(root)/'out.jpg')).isNull())
            self.assertEqual(s.list_sessions()[0]['id'],id)
            self.assertEqual((s.sessions/id).stat().st_mode&0o777,0o700)
            self.assertEqual((s.sessions/id/'document.json').stat().st_mode&0o777,0o600)
            self.assertEqual((s.sessions/id/'original.png').stat().st_mode&0o777,0o600)
            self.assertEqual(p.stat().st_mode&0o777,0o600)

    def test_all_annotations_and_editable_steps(self):
        for tool in ('text','arrow','rectangle','ellipse','pen','highlight','number','mask','blur'):
            with self.subTest(tool=tool):
                doc=Document(image('#123456' if tool=='blur' else '#ffffff'))
                if tool=='blur':
                    doc.add_layer(Layer('mask',((20,20),(31,31)),color='#ffffff'))
                baseline=doc.render()
                layer=Layer(tool,((20,20),(80,60)),text='Paso 1',number=2)
                doc.add_layer(layer);self.assertNotEqual(doc.render(),baseline)
                doc.replace_layer(layer.id,replace(layer,color='#ff0000',number=9))
                self.assertEqual(doc.layers[-1].number,9)
                doc.remove_layer(layer.id);self.assertEqual(doc.render(),baseline)

    def test_crop_validation(self):
        doc=Document(image())
        with self.assertRaises(ValueError):doc.set_crop(Rect(-1,0,10,10))
        for args in ((0,0,0,10),(0.5,0,1,1)):
            with self.assertRaises(ValueError):Rect(*args)
        with self.assertRaises(ValueError):Layer('mask',((0,0),(2,2)),color='#00000000')
        with self.assertRaises(ValueError):Layer('pen',((float('nan'),0),))

    def test_composition_compare(self):
        a,b=Document(image('#ff0000',20,10)),Document(image('#0000ff',20,10))
        h=Document.compose([a,b],gap=2).render();self.assertEqual((h.width(),h.height()),(42,10))
        self.assertEqual(h.pixelColor(23,0).name(),'#0000ff')
        v=Document.compose([a,b],axis='vertical',gap=3).render();self.assertEqual((v.width(),v.height()),(20,23))
        c=Document.compare(a,b,.5).render()
        self.assertEqual(c.pixelColor(9,0).name(),'#ff0000');self.assertEqual(c.pixelColor(10,0).name(),'#0000ff')
        with self.assertRaises(ValueError):Document.compare(a,Document(image()))

    def test_exact_mask_and_annotation_pixels(self):
        doc=Document(image('#ffffff'))
        doc.add_layer(Layer('mask',((10,10),(30,30)),color='#000000'))
        result=doc.render()
        for x,y in ((10,10),(20,20),(29,29)):
            self.assertEqual(result.pixelColor(x,y).name(),'#000000')
            self.assertEqual(result.pixelColor(x,y).alpha(),255)
        self.assertEqual(result.pixelColor(9,9).name(),'#ffffff')
        doc.add_layer(Layer('arrow',((40,40),(90,40)),color='#ff0000',width=4))
        self.assertEqual(doc.render().pixelColor(60,40).name(),'#ff0000')
        doc.add_layer(Layer('highlight',((50,60),(80,80)),color='#0000ff'))
        pixel=doc.render().pixelColor(60,70)
        self.assertEqual((pixel.red(),pixel.green(),pixel.blue(),pixel.alpha()),(170,170,255,255))

    def test_history_branch(self):
        doc=Document(image());a=Layer('number',((20,20),));doc.add_layer(a);doc.undo()
        doc.add_layer(Layer('text',((2,2),),text='nuevo'));self.assertFalse(doc.can_redo)

class StorageTests(unittest.TestCase):
    def test_symlinks_and_traversal(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root);s=Storage(path/'private');doc=Document(image())
            id=s.save(doc)
            with self.assertRaises(ValueError):s.load('../escape')
            export=path/'link.png';export.symlink_to(path/'target.png')
            with self.assertRaises(ValueError):s.export(doc,export)
            (s.sessions/id/'original.png').unlink();(s.sessions/id/'original.png').symlink_to(path/'target.png')
            with self.assertRaises(ValueError):s.load(id)
            link=path/'link';link.symlink_to(path/'private',target_is_directory=True)
            with self.assertRaises(ValueError):Storage(link)

    def test_preferences_and_corrupt_library(self):
        with tempfile.TemporaryDirectory() as root:
            s=Storage(Path(root)/'private');s.set_output(Path(root)/'pictures')
            self.assertEqual(Storage(s.root).default_output,Path(root)/'pictures')
            s.update_settings(format='JPEG',delay=5,include_cursor=True)
            s.set_output(Path(root)/'other')
            restored=Storage(s.root)
            self.assertEqual(restored.settings['format'],'JPEG')
            self.assertEqual(restored.settings['delay'],5)
            self.assertTrue(restored.settings['include_cursor'])
            with self.assertRaises(ValueError):s.update_settings(delay=-1)
            with self.assertRaises(ValueError):s.update_settings(cloud=True)
            id=s.save(Document(image()));(s.sessions/id/'document.json').write_text('bad')
            self.assertEqual(s.list_sessions(),[])
            with self.assertRaises(ValueError):s.load(id)

    def test_autosave_keeps_original_and_recovers_latest_state(self):
        with tempfile.TemporaryDirectory() as root:
            s=Storage(root);doc=Document(image('#ec3456'))
            id=s.save(doc);original=(s.sessions/id/'original.png').read_bytes()
            doc.add_layer(Layer('mask',((0,0),(40,40)),color='#000000'))
            self.assertEqual(s.save(doc),id)
            self.assertEqual((s.sessions/id/'original.png').read_bytes(),original)
            loaded=s.load(id);self.assertEqual(loaded.render().pixelColor(20,20).name(),'#000000')
            self.assertEqual(loaded.original.pixelColor(20,20).name(),'#ec3456')
            bad={'version':1,'id':id,'title':'corrupt','updated':'bad','width':120,'height':90}
            (s.sessions/id/'document.json').write_text(json.dumps(bad))
            self.assertEqual(s.list_sessions(),[])

    def test_clipboard_bitmap(self):
        with tempfile.TemporaryDirectory() as root:
            doc=Document(image());doc.add_layer(Layer('mask',((0,0),(20,20))))
            Storage(root).copy(doc);self.assertEqual(app.clipboard().image(),doc.render())

class CaptureTests(unittest.TestCase):
    def test_frozen_global_negative_coordinates(self):
        frozen=FrozenDesktop(image('#236789',300,100),Rect(-100,0,300,100),(Rect(-100,0,100,100),Rect(0,0,200,100)))
        engine=CaptureEngine();r=engine.capture(CaptureRequest(region=Rect(-80,10,20,30)),frozen)
        self.assertEqual((r.image.width(),r.image.height()),(20,30));self.assertEqual(r.geometry.x,-80)
        r=engine.capture(CaptureRequest(mode='monitor',monitor=1),frozen);self.assertEqual(r.image.width(),200)
        with self.assertRaises(ValueError):engine.capture(CaptureRequest(region=Rect(-200,0,10,10)),frozen)
        with self.assertRaises(ValueError):engine.capture(CaptureRequest(delay_ms=20),frozen)
        with self.assertRaises(ValueError):engine.capture(CaptureRequest(mode='window'),frozen)
        with self.assertRaises(ValueError):engine.capture(CaptureRequest(mode='monitor',monitor=4),frozen)

    def test_offscreen_never_captures(self):
        with self.assertRaises(RuntimeError):CaptureEngine().freeze()

if __name__=='__main__':unittest.main()
