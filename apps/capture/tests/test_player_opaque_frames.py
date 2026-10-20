"""Embedded playback frames are opaque so the desktop never shows through."""
import os
import unittest
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtGui import QImage
from loomrec.ui.mpv_embed import sw_frame


class FakeMpv:
    """Renders a mid-grey frame and leaves rgb0's padding byte at zero."""
    def mpv_render_context_render(self, context, params):
        import ctypes as C
        width, height = C.cast(params[0].data, C.POINTER(C.c_int * 2)).contents
        stride = C.cast(params[2].data, C.POINTER(C.c_size_t)).contents.value
        view = (C.c_ubyte * (stride * height)).from_address(params[3].data)
        for row in range(height):
            for column in range(width):
                offset = row * stride + column * 4
                view[offset:offset + 4] = [96, 96, 96, 0]
        return 0


class OpaqueFrameTests(unittest.TestCase):
    def test_rgb0_padding_never_becomes_transparency(self):
        image = sw_frame(FakeMpv(), None, 8, 4)
        self.assertEqual(image.format(), QImage.Format_RGB32)
        self.assertEqual(image.pixel(3, 2) >> 24, 0xFF)
        self.assertEqual(image.pixelColor(3, 2).red(), 96)


if __name__ == '__main__':
    unittest.main()
