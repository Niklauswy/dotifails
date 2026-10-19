"""Coordinate provenance fixtures only; no host/compositor/PipeWire/devices."""
import unittest
from unittest.mock import Mock,patch
from types import SimpleNamespace
from PySide6.QtGui import QImage,QColor
from test_desktop_cursor import output


class CoordinateTests(unittest.TestCase):
    def setUp(self):
        from loomrec.desktop_capture import topology_from_hypr
        self.outputs=topology_from_hypr([output('A',-32,width=64,height=48,scale=2),output('B',0)])
        self.raw=dict(mapping_id='A',position=[0,0],size=[64,48],source_type=1,**{'pipewire-serial':44})
    def test_authorized_mapping_replaces_xdph_shm_with_logical_coordinates(self):
        from loomrec.desktop_capture import coordinate_metadata
        from loomrec.pipewire_bridge import pixel_crop,source_geometry
        from loomrec.wayland_pointer import native_point
        meta=coordinate_metadata(self.raw,self.outputs)
        self.assertEqual(self.raw['position'],[0,0]);self.assertEqual(meta['position'],(-32,0));self.assertEqual(meta['size'],(32,24))
        self.assertEqual(meta['pipewire-serial'],44);self.assertEqual(source_geometry(64,48,meta),(64,48))
        crop=pixel_crop(64,48,meta,[-24,4,16,16]);self.assertEqual(crop,[16,8,32,32])
        self.assertEqual(native_point((-16,12),meta,(64,48),crop),(16,16))
        self.assertIsNone(native_point((8,8),meta,(64,48),crop))
    def test_identity_unknown_missing_duplicate_and_raw_geometry_change_fail(self):
        from loomrec.desktop_capture import coordinate_metadata
        from loomrec.pipewire_bridge import source_geometry
        for change in ({'mapping_id':'missing'},{'mapping_id':''},{'source_type':2},{'size':[32,24]}):
            with self.assertRaises(RuntimeError):coordinate_metadata(dict(self.raw,**change),self.outputs)
        meta=coordinate_metadata(self.raw,self.outputs)
        with self.assertRaisesRegex(RuntimeError,'píxel'):source_geometry(32,24,meta)
    def test_rotated_authorized_source_is_oriented_before_crop_and_pointer_mapping(self):
        from loomrec.desktop_capture import topology_from_hypr,coordinate_metadata
        from loomrec.pipewire_bridge import source_geometry,source_frame,pixel_crop
        from loomrec.wayland_pointer import native_point
        outputs=topology_from_hypr([output('A',-24,width=64,height=48,scale=2,transform=1)])
        meta=coordinate_metadata(self.raw,outputs);self.assertEqual(meta['size'],(24,32))
        self.assertEqual(source_geometry(64,48,meta),(48,64))
        image=QImage(64,48,QImage.Format_ARGB32);image.fill(QColor('red'));image.setPixelColor(0,47,QColor('blue'))
        data=bytes(image.constBits());crop=pixel_crop(48,64,meta,[-24,0,16,16])
        packed=source_frame(data,image.bytesPerLine(),64,48,meta,crop)
        oriented=QImage(packed,crop[2],crop[3],crop[2]*4,QImage.Format_ARGB32)
        self.assertEqual(oriented.pixelColor(0,0),QColor('blue'))
        self.assertEqual(native_point((-16,8),meta,(48,64),crop),(16,16))
    def test_plain_portal_coordinates_preserved_outside_normalized_hypr_route(self):
        from loomrec.pipewire_bridge import source_geometry,source_frame
        image=QImage(32,24,QImage.Format_ARGB32);image.fill(QColor('blue'))
        meta=dict(position=[-32,0],size=[32,24])
        self.assertEqual(source_geometry(32,24,meta),(32,24))
        self.assertEqual(source_frame(bytes(image.constBits()),image.bytesPerLine(),32,24,meta,[0,0,32,24]),bytes(image.constBits()))
    def test_adapter_normalizes_region_before_start_and_rejects_changed_topology(self):
        from loomrec.wayland_capture import PipeWireCapture
        from loomrec.desktop_capture import topology_from_hypr
        config=SimpleNamespace(source_type='region',cursor=True,rect=[-24,4,16,16])
        portal=Mock();portal.screencast.return_value=(47,self.raw)
        changed=topology_from_hypr([output('A',-32,width=64,height=48,scale=1)])
        with patch.dict('os.environ',{'HYPRLAND_INSTANCE_SIGNATURE':'own-fixture'}),patch('loomrec.wayland_capture.Portal',return_value=portal),patch('loomrec.desktop_capture.read_topology',side_effect=[self.outputs,changed]):
            capture=PipeWireCapture(config)
            self.assertEqual(capture.metadata['position'],(-32,0));self.assertEqual(capture.metadata['size'],(32,24))
            with self.assertRaisesRegex(RuntimeError,'topología'):capture.begin(Mock())
            capture.close();portal.close.assert_called_once()
    def test_fullcursor18_explicit_raw_contract_is_not_normalized_twice(self):
        from loomrec.wayland_capture import PipeWireCapture
        config=SimpleNamespace(source_type='monitor',cursor=True,cursor_effects={'halo':True},normalize_coordinates=False)
        portal=Mock();portal.screencast.return_value=(47,self.raw)
        with patch.dict('os.environ',{'HYPRLAND_INSTANCE_SIGNATURE':'own-fixture'}),patch('loomrec.wayland_capture.Portal',return_value=portal),patch('loomrec.desktop_capture.read_topology') as inventory:
            capture=PipeWireCapture(config);self.assertEqual(capture.metadata,self.raw);inventory.assert_not_called();capture.close()

if __name__=='__main__':unittest.main()
