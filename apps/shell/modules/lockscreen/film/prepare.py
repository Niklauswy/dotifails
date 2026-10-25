#!/usr/bin/env python3
"""Wysun lock · the founder's film: turns the source paintings into the film's pixel art.

The sources are generated paintings kept outside the repository (their paths are arguments); what the
lock ships is the result in this folder. Each source is reduced onto a real pixel grid (backgrounds at
320x180, layers at 640x180), the magenta backdrop of layers and sprite sheets becomes transparency,
sprite sheets are cut into frames that keep their motion within the sheet, and everything shares one
small palette taken from the backgrounds, so the film reads as a single piece of pixel art.

    python3 prepare.py SKY CLOUDS FAR MID NEAR SEA PEAK LEDGE STAND JUMP FLY EAGLE TURN

Development tool only (needs Pillow); the lock itself only loads the PNGs.
"""
from pathlib import Path
import sys

from PIL import Image

OUT = Path(__file__).resolve().parent
COLOURS = 48
# Sprite sizes on the 320x180 canvas, in art pixels.
STAND_HEIGHT = 56       # the founder standing (and jumping, same scale)
FLY_WIDTH = 76          # the founder in flight, arms spread
GAP = 12                # empty columns that separate two frames in a sheet


def magenta(pixel):
    r, g, b = pixel[:3]
    return r > 150 and b > 150 and g < 110 and abs(r - b) < 90


def keyed(image):
    """The magenta backdrop (and its fringe) becomes transparent."""
    image = image.convert('RGBA')
    pixels = image.load()
    for y in range(image.height):
        for x in range(image.width):
            if magenta(pixels[x, y]):
                pixels[x, y] = (0, 0, 0, 0)
    return image


def reduce(image, size):
    """Down onto the pixel grid: an area average, then hard alpha."""
    small = image.resize(size, Image.BOX)
    if small.mode == 'RGBA':
        pixels = small.load()
        for y in range(small.height):
            for x in range(small.width):
                r, g, b, a = pixels[x, y]
                if a < 140 or magenta((r, g, b)):
                    pixels[x, y] = (0, 0, 0, 0)
                else:
                    # Undo the backdrop's tint on the edges it blended into.
                    pixels[x, y] = (min(r, (g + b) // 2 + 60), g, min(b, (r + g) // 2 + 60), 255) if r > g + 80 and b > g + 80 else (r, g, b, 255)
    return small


def filled(image):
    """Close the pin holes keying leaves inside shapes (shadows that looked like the magenta backdrop)."""
    pixels = image.load()
    for _ in range(2):
        holes = []
        for y in range(1, image.height - 1):
            for x in range(1, image.width - 1):
                if pixels[x, y][3]:
                    continue
                around = [pixels[x + dx, y + dy] for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy]
                solid = [c for c in around if c[3]]
                if len(solid) >= 5:
                    holes.append((x, y, tuple(sum(c[i] for c in solid) // len(solid) for i in range(3)) + (255,)))
        for x, y, colour in holes:
            pixels[x, y] = colour
    return image


def palettised(image, palette):
    """Onto the shared palette, keeping transparency."""
    rgb = image.convert('RGB').quantize(palette=palette, dither=Image.Dither.NONE).convert('RGB')
    if image.mode == 'RGBA':
        result = rgb.convert('RGBA')
        result.putalpha(image.getchannel('A'))
        return result
    return rgb


def frames(sheet):
    """Column ranges of the frames in a keyed sheet, and the rows they all share."""
    alpha = sheet.getchannel('A')
    columns = [any(alpha.getpixel((x, y)) for y in range(0, sheet.height, 2)) for x in range(sheet.width)]
    runs, start, gap = [], None, 0
    for x, filled in enumerate(columns + [False] * GAP):
        if filled:
            if start is None:
                start = x
            gap = 0
        elif start is not None:
            gap += 1
            if gap >= GAP:
                runs.append((start, x - gap + 1))
                start, gap = None, 0
    top, bottom = sheet.getbbox()[1], sheet.getbbox()[3]
    return runs, top, bottom


def cut(sheet, scale):
    """Frames of equal size, each centred on its figure, keeping the vertical motion of the sheet."""
    runs, top, bottom = frames(sheet)
    width = max(b - a for a, b in runs)
    result = []
    for a, b in runs:
        centre = (a + b) // 2
        box = (centre - width // 2, top, centre - width // 2 + width, bottom)
        frame = sheet.crop(box)
        result.append(filled(reduce(frame, (max(1, round(frame.width * scale)), max(1, round(frame.height * scale))))))
    return result


def figure_extent(sheet):
    runs, top, bottom = frames(sheet)
    heights, widths = [], []
    for a, b in runs:
        box = sheet.crop((a, top, b, bottom)).getbbox()
        widths.append(box[2] - box[0])
        heights.append(box[3] - box[1])
    return max(widths), max(heights), widths, heights


def main(paths):
    if len(paths) != 13:
        raise SystemExit(__doc__)
    sky, clouds, far, mid, near, sea, peak, ledge, stand, jump, fly, eagle, turn = (Image.open(p) for p in paths)

    backgrounds = {'sky': reduce(sky.convert('RGB'), (640, 180)), 'peak': reduce(peak.convert('RGB'), (320, 180)),
                   'ledge': reduce(ledge.convert('RGB'), (320, 180))}
    layers = {'clouds': clouds, 'range-far': far, 'range-mid': mid, 'range-near': near, 'cloud-sea': sea}
    layers = {name: filled(reduce(keyed(image), (640, 180))) for name, image in layers.items()}

    stand, jump, fly, eagle, turn = (keyed(image) for image in (stand, jump, fly, eagle, turn))
    standing = STAND_HEIGHT / figure_extent(stand)[1]
    flying = FLY_WIDTH / figure_extent(fly)[0]
    # The turn sheet starts as the flying man and ends as the eagle: it sets both of their sizes.
    turn_widths = figure_extent(turn)[2]
    turning = FLY_WIDTH / turn_widths[0]
    eagle_scale = turn_widths[-1] * turning / figure_extent(eagle)[0]
    sprites = {'founder-stand': cut(stand, standing), 'founder-jump': cut(jump, standing),
               'founder-fly': cut(fly, flying), 'founder-turn': cut(turn, turning), 'eagle': cut(eagle, eagle_scale)}

    # One palette for the whole film, from its three painted backgrounds plus the figures.
    sample = Image.new('RGB', (640, 540 + 64))
    sample.paste(backgrounds['sky'], (0, 0))
    sample.paste(backgrounds['peak'], (0, 180))
    sample.paste(backgrounds['ledge'], (320, 180))
    sample.paste(layers['range-near'].convert('RGB'), (0, 360))
    x = 0
    for frame in sprites['founder-stand'] + sprites['founder-fly'][:1] + sprites['eagle'][:1]:
        sample.paste(frame.convert('RGB'), (x, 540), frame)
        x += frame.width
    palette = sample.quantize(colors=COLOURS, method=Image.Quantize.MEDIANCUT)

    for stale in OUT.glob('*.png'):
        stale.unlink()
    for name, image in {**backgrounds, **layers}.items():
        palettised(image, palette).save(OUT / f'{name}.png', optimize=True)
    for name, images in sprites.items():
        for index, image in enumerate(images):
            palettised(image, palette).save(OUT / f'{name}-{index}.png', optimize=True)
    counts = {name: len(images) for name, images in sprites.items()}
    print('Film written to', OUT, counts)


if __name__ == '__main__':
    main(sys.argv[1:])
