"""The parts of wysun_media's mpv glue that need no libmpv: the numeric locale and the software renderer's frame buffer."""
import ctypes as C
import unittest
from unittest.mock import patch

import media_support  # noqa: F401  (puts apps/python on the path)
from wysun_media import mpv  # noqa: E402
from wysun_media.software import render  # noqa: E402


class MpvGlueTests(unittest.TestCase):
    def test_numeric_locale_is_normalized_before_creating_handle(self):
        with patch('wysun_media.mpv.locale.setlocale') as normalize:
            mpv.normalize_numeric_locale()
        normalize.assert_called_once_with(mpv.locale.LC_NUMERIC, 'C')

    def test_software_renderer_buffer_alignment_and_frame_ownership(self):
        seen = []

        class Library:
            def mpv_render_context_render(self, context, params):
                size = C.cast(params[0].data, C.POINTER(C.c_int))
                stride = C.cast(params[2].data, C.POINTER(C.c_size_t)).contents.value
                self.address, self.count = params[3].data, stride * size[1]
                seen.append((self.address % 64, stride % 64))
                C.memset(self.address, 127, self.count)
                for offset in range(3, self.count, 4):
                    C.c_ubyte.from_address(self.address + offset).value = 255      # bgra: opaque
                return 0

        pixels, width, height, stride = render(Library(), None, 21, 19)
        self.assertEqual(seen, [(0, 0)])
        self.assertEqual((width, height, stride % 64), (21, 19, 0))
        self.assertEqual(pixels[:4], bytes([127, 127, 127, 255]), 'the frame owns its pixels after the render buffer is gone')


if __name__ == '__main__':
    unittest.main()
