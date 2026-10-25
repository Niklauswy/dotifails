"""Synthetic media for the player tests and benchmarks: generated with ffmpeg and Qt, never from private files."""
import struct
import subprocess
import sys
from pathlib import Path

from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter

SIZE_1080 = '1920x1080'


def ffmpeg(*args):
    done = subprocess.run(['ffmpeg', '-v', 'error', '-y', *args], timeout=240, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if done.returncode:
        raise RuntimeError(f'ffmpeg falló al generar un medio de prueba: {done.stderr[-400:]}')


def video(path, codec, *, size='640x360', rate=30, seconds=3, audio=True, extra=()):
    """Test pattern plus (optionally) a sine tone, with a visible frame counter so seeks are checkable."""
    inputs = ['-f', 'lavfi', '-i', f'testsrc2=size={size}:rate={rate}:duration={seconds}']
    if audio:
        inputs += ['-f', 'lavfi', '-i', f'sine=frequency=440:duration={seconds}']
    ffmpeg(*inputs, '-c:v', codec, *extra, *(['-c:a', 'aac' if str(path).endswith(('.mp4', '.mov', '.m4v')) else 'libopus'] if audio else ['-an']),
           '-shortest', str(path))


def tone(path, *extra, seconds=3):
    ffmpeg('-f', 'lavfi', '-i', f'sine=frequency=330:duration={seconds}', *extra, str(path))


def exif_orientation(jpeg_bytes, orientation):
    """Insert a minimal EXIF APP1 carrying only the orientation tag after SOI."""
    tiff = b'MM\0*' + struct.pack('>I', 8) + struct.pack('>H', 1) + struct.pack('>HHIHH', 0x0112, 3, 1, orientation, 0) + struct.pack('>I', 0)
    body = b'Exif\0\0' + tiff
    return jpeg_bytes[:2] + b'\xff\xe1' + struct.pack('>H', len(body) + 2) + body + jpeg_bytes[2:]


def pattern(width, height, alpha=False):
    """Four coloured quadrants with a white corner marker, so rotation is visible in pixels."""
    image = QImage(width, height, QImage.Format_ARGB32 if alpha else QImage.Format_RGB32)
    image.fill(QColor(0, 0, 0, 0) if alpha else QColor('black'))
    painter = QPainter(image)
    half_w, half_h = width // 2, height // 2
    for index, colour in enumerate(('#d33', '#3d3', '#33d', '#dd3')):
        painter.fillRect((index % 2) * half_w, (index // 2) * half_h, half_w, half_h, QColor(colour))
    painter.fillRect(0, 0, max(4, width // 8), max(4, height // 8), QColor('white'))
    painter.end()
    return image


def build(directory):
    """Create the whole set under ``directory``; returns {name: Path}. Safe to call repeatedly."""
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    out = {}

    def target(name):
        out[name] = root / name
        return out[name]

    if QGuiApplication.instance() is None:
        raise RuntimeError('Crea una QGuiApplication antes de generar imágenes')
    video(target('h264.mp4'), 'libx264', extra=('-pix_fmt', 'yuv420p', '-g', '15'))
    video(target('vp9.webm'), 'libvpx-vp9', extra=('-b:v', '1M', '-deadline', 'realtime', '-cpu-used', '8'))
    video(target('hevc.mkv'), 'libx265', extra=('-pix_fmt', 'yuv420p', '-x265-params', 'log-level=error'))
    video(target('av1.mkv'), 'libsvtav1', extra=('-preset', '12', '-pix_fmt', 'yuv420p', '-svtav1-params', 'log=0'))
    video(target('h264.mov'), 'libx264', extra=('-pix_fmt', 'yuv420p'))
    video(target('silent.mp4'), 'libx264', audio=False, extra=('-pix_fmt', 'yuv420p'))
    video(target('p1080.mp4'), 'libx264', size=SIZE_1080, rate=60, seconds=6, extra=('-pix_fmt', 'yuv420p', '-preset', 'veryfast', '-g', '60'))
    tone(target('tone.mp3'), '-c:a', 'libmp3lame')
    tone(target('tone.flac'), '-c:a', 'flac')
    tone(target('tone.ogg'), '-c:a', 'libvorbis')
    tone(target('tone.opus'), '-c:a', 'libopus')
    tone(target('tone.m4a'), '-c:a', 'aac')
    tone(target('tone.wav'))
    cover = root / '_cover.png'
    pattern(300, 300).save(str(cover))
    ffmpeg('-f', 'lavfi', '-i', 'sine=frequency=220:duration=2', '-i', str(cover), '-map', '0:a', '-map', '1:v', '-c:a', 'libmp3lame',
           '-c:v', 'copy', '-id3v2_version', '3', '-metadata:s:v', 'title=Cover', str(target('cover.mp3')))
    pattern(120, 80).save(str(target('plain.png')))
    pattern(64, 64, alpha=True).save(str(target('alpha.png')))
    pattern(120, 80).save(str(target('plain.bmp')))
    pattern(120, 80).save(str(target('plain.tiff')))
    pattern(120, 80).save(str(target('plain.webp')))
    pattern(120, 80).save(str(target('plain.jpg')), 'JPEG', 95)
    big = pattern(6000, 4000)
    big.save(str(target('big.jpg')), 'JPEG', 70)
    plain = (root / 'plain.jpg').read_bytes()
    for orientation in range(1, 9):
        target(f'exif{orientation}.jpg').write_bytes(exif_orientation(plain, orientation))
    ffmpeg('-f', 'lavfi', '-i', 'testsrc2=size=160x90:rate=10:duration=1', '-loop', '0', str(target('anim.gif')))
    ffmpeg('-f', 'lavfi', '-i', 'testsrc2=size=160x90:rate=10:duration=1', '-loop', '0', str(target('anim.webp')))
    target('corrupt.png').write_bytes(b'\x89PNG\r\n\x1a\n' + b'\0' * 64)
    target('truncated.jpg').write_bytes(plain[:len(plain) // 3])
    target('empty.jpg').write_bytes(b'')
    target('fake.mp4').write_bytes(b'not a video at all')
    target('list.m3u').write_text('/etc/passwd\nhttp://example.invalid/stream\n')
    cover.unlink(missing_ok=True)
    return out


if __name__ == '__main__':
    app = QGuiApplication(sys.argv[:1] + ['-platform', 'offscreen'])
    destination = sys.argv[1] if len(sys.argv) > 1 else 'media-fixtures'
    for name, path in build(destination).items():
        print(f'{name:14} {path.stat().st_size:>10} B')
