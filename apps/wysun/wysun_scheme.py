"""Wysun's Material You scheme generator.

Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
Adapted from caelestia-dots/cli; see THIRD_PARTY.md for the source commit and
file map. Wysun's image quantizer below is original Python code; the vendored
HCT and dynamic roles are from materialyoucolor (MIT).
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Protocol, Any

from PIL import Image

VENDOR = Path(__file__).with_name('vendor')
if str(VENDOR) not in sys.path:
    sys.path.insert(0, str(VENDOR))

from materialyoucolor.blend import Blend
from materialyoucolor.dislike.dislike_analyzer import DislikeAnalyzer
from materialyoucolor.dynamiccolor.material_dynamic_colors import MaterialDynamicColors
from materialyoucolor.hct import Hct
from materialyoucolor.scheme.scheme_content import SchemeContent
from materialyoucolor.scheme.scheme_expressive import SchemeExpressive
from materialyoucolor.scheme.scheme_fidelity import SchemeFidelity
from materialyoucolor.scheme.scheme_fruit_salad import SchemeFruitSalad
from materialyoucolor.scheme.scheme_monochrome import SchemeMonochrome
from materialyoucolor.scheme.scheme_neutral import SchemeNeutral
from materialyoucolor.scheme.scheme_rainbow import SchemeRainbow
from materialyoucolor.scheme.scheme_tonal_spot import SchemeTonalSpot
from materialyoucolor.scheme.scheme_vibrant import SchemeVibrant
from materialyoucolor.utils.color_utils import argb_from_rgb
from materialyoucolor.utils.math_utils import difference_degrees, rotation_direction, sanitize_degrees_double


# The base DynamicScheme class requires a 'variant' argument, but the specific
# subclasses in get_scheme() handle that internally. This Protocol tells the type
# checker to expect our specific 3-argument setup instead of the base class signature.
class SchemeConstructor(Protocol):
    def __call__(self, source_color_hct: Any, is_dark: bool, contrast_level: float) -> "DynamicScheme": ...

try:
    from materialyoucolor.dynamiccolor.dynamic_scheme import DynamicScheme
except ImportError:
    from materialyoucolor.scheme.dynamic_scheme import DynamicScheme


def hex_to_hct(hex: str) -> Hct:
    return Hct.from_int(int(f"0xFF{hex}", 16))


light_gruvbox = [
    hex_to_hct("FDF9F3"),
    hex_to_hct("FF6188"),
    hex_to_hct("A9DC76"),
    hex_to_hct("FC9867"),
    hex_to_hct("FFD866"),
    hex_to_hct("F47FD4"),
    hex_to_hct("78DCE8"),
    hex_to_hct("333034"),
    hex_to_hct("121212"),
    hex_to_hct("FF6188"),
    hex_to_hct("A9DC76"),
    hex_to_hct("FC9867"),
    hex_to_hct("FFD866"),
    hex_to_hct("F47FD4"),
    hex_to_hct("78DCE8"),
    hex_to_hct("333034"),
]

dark_gruvbox = [
    hex_to_hct("282828"),
    hex_to_hct("CC241D"),
    hex_to_hct("98971A"),
    hex_to_hct("D79921"),
    hex_to_hct("458588"),
    hex_to_hct("B16286"),
    hex_to_hct("689D6A"),
    hex_to_hct("A89984"),
    hex_to_hct("928374"),
    hex_to_hct("FB4934"),
    hex_to_hct("B8BB26"),
    hex_to_hct("FABD2F"),
    hex_to_hct("83A598"),
    hex_to_hct("D3869B"),
    hex_to_hct("8EC07C"),
    hex_to_hct("EBDBB2"),
]

light_catppuccin = [
    hex_to_hct("dc8a78"),
    hex_to_hct("dd7878"),
    hex_to_hct("ea76cb"),
    hex_to_hct("8839ef"),
    hex_to_hct("d20f39"),
    hex_to_hct("e64553"),
    hex_to_hct("fe640b"),
    hex_to_hct("df8e1d"),
    hex_to_hct("40a02b"),
    hex_to_hct("179299"),
    hex_to_hct("04a5e5"),
    hex_to_hct("209fb5"),
    hex_to_hct("1e66f5"),
    hex_to_hct("7287fd"),
]

dark_catppuccin = [
    hex_to_hct("f5e0dc"),
    hex_to_hct("f2cdcd"),
    hex_to_hct("f5c2e7"),
    hex_to_hct("cba6f7"),
    hex_to_hct("f38ba8"),
    hex_to_hct("eba0ac"),
    hex_to_hct("fab387"),
    hex_to_hct("f9e2af"),
    hex_to_hct("a6e3a1"),
    hex_to_hct("94e2d5"),
    hex_to_hct("89dceb"),
    hex_to_hct("74c7ec"),
    hex_to_hct("89b4fa"),
    hex_to_hct("b4befe"),
]

kcolours = [
    {"name": "klink", "hct": hex_to_hct("2980b9")},
    {"name": "kvisited", "hct": hex_to_hct("9b59b6")},
    {"name": "knegative", "hct": hex_to_hct("da4453")},
    {"name": "kneutral", "hct": hex_to_hct("f67400")},
    {"name": "kpositive", "hct": hex_to_hct("27ae60")},
]

colour_names = [
    "rosewater",
    "flamingo",
    "pink",
    "mauve",
    "red",
    "maroon",
    "peach",
    "yellow",
    "green",
    "teal",
    "sky",
    "sapphire",
    "blue",
    "lavender",
]


def grayscale(colour: Hct, light: bool) -> Hct:
    colour = darken(colour, 0.35) if light else lighten(colour, 0.65)
    colour.chroma = 0
    return colour


def mix(a: Hct, b: Hct, w: float) -> Hct:
    return Hct.from_int(Blend.cam16_ucs(a.to_int(), b.to_int(), w))


def harmonize(from_hct: Hct, to_hct: Hct, tone_boost: float) -> Hct:
    difference_degrees_ = difference_degrees(from_hct.hue, to_hct.hue)
    rotation_degrees = min(difference_degrees_ * 0.8, 100)
    output_hue = sanitize_degrees_double(from_hct.hue + rotation_degrees * rotation_direction(from_hct.hue, to_hct.hue))
    return Hct.from_hct(output_hue, from_hct.chroma, from_hct.tone * (1 + tone_boost))


def lighten(colour: Hct, amount: float) -> Hct:
    diff = (100 - colour.tone) * amount
    return Hct.from_hct(colour.hue, colour.chroma + diff / 5, colour.tone + diff)


def darken(colour: Hct, amount: float) -> Hct:
    diff = colour.tone * amount
    return Hct.from_hct(colour.hue, colour.chroma - diff / 5, colour.tone - diff)


def get_scheme(scheme: str) -> SchemeConstructor:
    if scheme == "content":
        return SchemeContent
    if scheme == "expressive":
        return SchemeExpressive
    if scheme == "fidelity":
        return SchemeFidelity
    if scheme == "fruitsalad":
        return SchemeFruitSalad
    if scheme == "monochrome":
        return SchemeMonochrome
    if scheme == "neutral":
        return SchemeNeutral
    if scheme == "rainbow":
        return SchemeRainbow
    if scheme == "tonalspot":
        return SchemeTonalSpot
    return SchemeVibrant


def gen_scheme(scheme, primary: Hct) -> dict[str, str]:
    is_light = scheme.mode == "light"

    colours = {}

    # Material colours
    primary_scheme = get_scheme(scheme.variant)(source_color_hct=primary, is_dark=not is_light, contrast_level=0.0)
    if hasattr(MaterialDynamicColors, "all_colors"):  # materialyoucolor-python >= 3.0.0
        dyn_colours = MaterialDynamicColors()
        for colour in dyn_colours.all_colors:
            colours[colour.name] = colour.get_hct(primary_scheme)
    else:
        for colour in vars(MaterialDynamicColors).keys():
            colour_name = getattr(MaterialDynamicColors, colour)
            if hasattr(colour_name, "get_hct"):
                colours[colour] = colour_name.get_hct(primary_scheme)

    # Backwards compatibility with old colour names
    if "primaryPaletteKeyColor" in colours:  # materialyoucolor-python >= 3.0.0
        for colour in "primary", "secondary", "tertiary", "neutral":
            colours[f"{colour}_paletteKeyColor"] = colours[f"{colour}PaletteKeyColor"]
        colours["neutral_variant_paletteKeyColor"] = colours["neutralVariantPaletteKeyColor"]

    # Harmonize terminal colours
    for i, hct in enumerate(light_gruvbox if is_light else dark_gruvbox):
        if scheme.variant == "monochrome":
            colours[f"term{i}"] = grayscale(hct, is_light)
        else:
            colours[f"term{i}"] = harmonize(
                hct, colours["primary_paletteKeyColor"], (0.35 if i < 8 else 0.2) * (-1 if is_light else 1)
            )

    # Harmonize named colours
    for i, hct in enumerate(light_catppuccin if is_light else dark_catppuccin):
        if scheme.variant == "monochrome":
            colours[colour_names[i]] = grayscale(hct, is_light)
        else:
            colours[colour_names[i]] = harmonize(hct, colours["primary_paletteKeyColor"], (-0.2 if is_light else 0.05))

    # KColours
    for colour in kcolours:
        colours[colour["name"]] = harmonize(colour["hct"], colours["primary"], 0.1)
        colours[f"{colour['name']}Selection"] = harmonize(colour["hct"], colours["onPrimaryFixedVariant"], 0.1)
        if scheme.variant == "monochrome":
            colours[colour["name"]] = grayscale(colours[colour["name"]], is_light)
            colours[f"{colour['name']}Selection"] = grayscale(colours[f"{colour['name']}Selection"], is_light)

    if scheme.variant == "neutral":
        for name, hct in colours.items():
            colours[name].chroma -= 15

    # Darken surfaces for hard flavour
    if scheme.flavour == "hard":
        for colour in "background", *(k for k in colours.keys() if k.startswith("surface")):
            colours[colour] = lighten(colours[colour], 0.4) if is_light else darken(colours[colour], 0.8)
        colours["term0"] = lighten(colours["term0"], 0.4) if is_light else darken(colours["term0"], 0.9)

    # FIXME: deprecated stuff
    colours["text"] = colours["onBackground"]
    colours["subtext1"] = colours["onSurfaceVariant"]
    colours["subtext0"] = colours["outline"]
    colours["overlay2"] = mix(colours["surface"], colours["outline"], 0.86)
    colours["overlay1"] = mix(colours["surface"], colours["outline"], 0.71)
    colours["overlay0"] = mix(colours["surface"], colours["outline"], 0.57)
    colours["surface2"] = mix(colours["surface"], colours["outline"], 0.43)
    colours["surface1"] = mix(colours["surface"], colours["outline"], 0.29)
    colours["surface0"] = mix(colours["surface"], colours["outline"], 0.14)
    colours["base"] = colours["surface"]
    colours["mantle"] = darken(colours["surface"], 0.03)
    colours["crust"] = darken(colours["surface"], 0.05)

    # More darkening if hard flavour
    if scheme.flavour == "hard":
        for colour in "base", "mantle", "crust":
            colours[colour] = lighten(colours[colour], 0.4) if is_light else darken(colours[colour], 0.9)
        for i in range(3):
            colours[f"overlay{i}"] = (
                lighten(colours[f"overlay{i}"], 0.4) if is_light else darken(colours[f"overlay{i}"], 0.8)
            )
            colours[f"surface{i}"] = (
                lighten(colours[f"surface{i}"], 0.4) if is_light else darken(colours[f"surface{i}"], 0.8)
            )

    # For debugging
    # print("\n".join(["{}: \x1b[48;2;{};{};{}m   \x1b[0m".format(n, *c.to_rgba()[:3]) for n, c in colours.items()]))

    colours = {k: hex(v.to_int())[4:] for k, v in colours.items()}

    # Extended material
    if is_light:
        colours["success"] = "4F6354"
        colours["onSuccess"] = "FFFFFF"
        colours["successContainer"] = "D1E8D5"
        colours["onSuccessContainer"] = "0C1F13"
    else:
        colours["success"] = "B5CCBA"
        colours["onSuccess"] = "213528"
        colours["successContainer"] = "374B3E"
        colours["onSuccessContainer"] = "D1E9D6"

    return colours


VARIANTS = ('content', 'expressive', 'fidelity', 'fruitsalad', 'monochrome', 'neutral', 'rainbow', 'tonalspot', 'vibrant')


def quantize_pixels(pixels, maximum=128):
    """Deterministic median-cut quantization in Python; no native extension."""
    counts = Counter(tuple(int(channel) for channel in pixel[:3]) for pixel in pixels)
    boxes = [sorted(counts.items())]
    while len(boxes) < maximum:
        candidates = []
        for index, box in enumerate(boxes):
            if len(box) < 2:
                continue
            ranges = [max(colour[channel] for colour, _ in box) - min(colour[channel] for colour, _ in box)
                      for channel in range(3)]
            channel = max(range(3), key=lambda n: (ranges[n], -n))
            population = sum(count for _, count in box)
            candidates.append((ranges[channel] * population, index, channel))
        if not candidates:
            break
        _, index, channel = max(candidates)
        box = sorted(boxes.pop(index), key=lambda item: (item[0][channel], item[0]))
        midpoint = (sum(count for _, count in box) + 1) // 2
        population = 0
        split = 1
        for split, (_, count) in enumerate(box, 1):
            population += count
            if population >= midpoint:
                break
        split = min(max(split, 1), len(box) - 1)
        boxes[index:index] = [box[:split], box[split:]]

    result = {}
    for box in boxes:
        population = sum(count for _, count in box)
        rgb = tuple(round(sum(colour[channel] * count for colour, count in box) / population) for channel in range(3))
        argb = argb_from_rgb(*rgb)
        result[argb] = result.get(argb, 0) + population
    return result


def score_colors(colors_to_population):
    """Caelestia's Material hue-proportion/chroma scoring, over pure-Python bins."""
    if not colors_to_population:
        raise ValueError('El fondo no contiene colores que se puedan cuantizar.')
    colours = [(Hct.from_int(rgb), population) for rgb, population in colors_to_population.items()]
    hue_population = [0] * 360
    population_sum = sum(population for _, population in colours)
    for hct, population in colours:
        hue_population[int(hct.hue) % 360] += population
    excited = [0.0] * 360
    for hue, population in enumerate(hue_population):
        proportion = population / population_sum
        for offset in range(-14, 16):
            excited[(hue + offset) % 360] += proportion
    scored = []
    for hct, _ in colours:
        proportion = excited[int(round(hct.hue)) % 360]
        chroma_weight = 0.3 if hct.chroma >= 48 else 0.1
        score = proportion * 100 * 0.7 + (hct.chroma - 48) * chroma_weight
        scored.append((score, hct))
    scored.sort(key=lambda item: (-item[0], item[1].to_int()))
    for cutoff in range(20, -1, -1):
        primary = next((hct for _, hct in scored if hct.chroma > cutoff and hct.tone > cutoff * 3), None)
        if primary is not None:
            return DislikeAnalyzer.fix_if_disliked(primary)
    return scored[0][1]


def image_colourfulness(image):
    rg, yb = [], []
    for red, green, blue in image.getdata():
        rg.append(abs(red - green))
        yb.append(abs(0.5 * (red + green) - blue))
    mean_rg = sum(rg) / len(rg)
    mean_yb = sum(yb) / len(yb)
    std_rg = math.sqrt(sum((value - mean_rg) ** 2 for value in rg) / len(rg))
    std_yb = math.sqrt(sum((value - mean_yb) ** 2 for value in yb) / len(yb))
    return math.hypot(std_rg, std_yb) + 0.3 * math.hypot(mean_rg, mean_yb)


def automatic_variant(image):
    score = image_colourfulness(image)
    return 'neutral' if score < 10 else 'content' if score < 20 else 'tonalspot'


def _file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def generate_dynamic(image_path, mode=None, variant=None):
    """Generate a Caelestia-shaped scheme without retaining source image data."""
    image_path = Path(image_path).expanduser()
    if mode is not None and mode not in ('light', 'dark'):
        raise ValueError('--mode debe ser light o dark.')
    if variant is not None and variant not in VARIANTS:
        raise ValueError('Variante Material desconocida: ' + str(variant))
    try:
        with Image.open(image_path) as source:
            image = source.convert('RGB')
            image.thumbnail((128, 128), Image.Resampling.NEAREST)
            pixels = list(image.getdata())
    except (OSError, ValueError, Image.DecompressionBombError) as error:
        raise ValueError('No se pudo leer el fondo seleccionado en Ajustes.') from error
    if not pixels:
        raise ValueError('El fondo seleccionado está vacío.')
    primary = score_colors(quantize_pixels(pixels))
    average = tuple(round(sum(pixel[i] for pixel in pixels) / len(pixels)) for i in range(3))
    source_hct = Hct.from_int(argb_from_rgb(*average))
    selected_mode = mode or ('light' if source_hct.tone > 60 else 'dark')
    selected_variant = variant or automatic_variant(image)
    scheme = SimpleNamespace(name='dynamic', flavour='default', mode=selected_mode, variant=selected_variant)
    return {
        'name': scheme.name,
        'flavour': scheme.flavour,
        'mode': scheme.mode,
        'variant': scheme.variant,
        'colours': gen_scheme(scheme, primary),
        'wallpaper_hash': _file_hash(image_path),
    }


def _hex(value):
    return str(value).lstrip('#')[:6].lower()


def fixed_scheme(style, variant):
    """Expose an existing Wysun preset through Material role names for the shell."""
    import theme_core
    values = theme_core.resolve(style, variant)
    colours = {}
    for dynamic in MaterialDynamicColors().all_colors:
        name = dynamic.name
        token = None
        if name.endswith('PaletteKeyColor'):
            palette = name.removesuffix('PaletteKeyColor')
            token = {'primary': 'accent', 'secondary': 'accent_alt', 'tertiary': 'warning',
                     'neutral': 'surface', 'neutralVariant': 'well', 'error': 'danger'}.get(palette)
        elif name.startswith('onPrimary'):
            token = 'on_accent' if 'Container' not in name and 'Variant' not in name else 'selection_text'
        elif name.startswith('primary'):
            token = 'selection' if 'Container' in name else 'accent'
        elif name.startswith('onSecondary') or name.startswith('onTertiary'):
            token = 'selection_text' if 'Container' in name or 'Variant' in name else 'on_accent'
        elif name.startswith('secondary'):
            token = 'selection' if 'Container' in name else 'accent_alt'
        elif name.startswith('tertiary'):
            token = 'selection' if 'Container' in name else 'success'
        elif name.startswith('onError'):
            token = 'danger'
        elif name.startswith('error'):
            token = 'danger_soft' if 'Container' in name else 'danger'
        elif name == 'background' or name == 'surfaceDim':
            token = 'canvas'
        elif name == 'onBackground' or name == 'onSurface':
            token = 'text'
        elif name == 'surface' or name.startswith('surfaceContainer') or name == 'surfaceBright':
            token = 'surface_raised' if ('High' in name or 'Bright' in name) else 'surface'
        elif name == 'surfaceVariant':
            token = 'well'
        elif name == 'onSurfaceVariant':
            token = 'muted'
        elif name.startswith('outline'):
            token = 'line_strong' if name == 'outline' else 'line'
        elif name in ('inverseSurface', 'inverseOnSurface', 'inversePrimary', 'shadow', 'scrim', 'surfaceTint'):
            token = {'inverseSurface': 'tooltip', 'inverseOnSurface': 'on_tooltip', 'inversePrimary': 'accent_hover',
                     'shadow': 'shadow', 'scrim': 'scrim', 'surfaceTint': 'accent'}[name]
        colours[name] = _hex(values[token])
    colours.update({f'term{i}': _hex(value) for i, value in enumerate(values['external']['palette'])})
    colours['text'] = colours['onBackground']
    colours['subtext1'] = colours['onSurfaceVariant']
    colours['subtext0'] = colours['outline']
    colours['success'] = _hex(values['success'])
    colours['onSuccess'] = _hex(values['surface'])
    colours['successContainer'] = _hex(values['selection'])
    colours['onSuccessContainer'] = _hex(values['selection_text'])
    return {
        'name': variant,
        'flavour': 'default',
        'mode': 'light' if style == 'fluent' and variant == 'light' else 'dark',
        'variant': variant,
        'colours': colours,
    }


def _current_wallpaper(home=None):
    from environment_settings import EnvironmentSettings
    values = EnvironmentSettings(home).wallpaper_values()
    path = values.get('default')
    if not path:
        path = next((entry.get('path') for entry in values.get('monitors', {}).values() if entry.get('path')), None)
    if not path or not Path(path).is_file():
        raise ValueError('Selecciona primero un fondo en Ajustes de Wysun.')
    return Path(path)


def regenerate_if_dynamic(home, wallpaper_values):
    """Refresh the user-selected dynamic scheme after Wysun changes its wallpaper."""
    import theme_core
    current = theme_core.read_scheme(home)
    if not current or current.get('name') != 'dynamic':
        return None
    path = wallpaper_values.get('default') or next(
        (entry.get('path') for entry in wallpaper_values.get('monitors', {}).values() if entry.get('path')), None)
    if not path:
        return None
    if current.get('wallpaper_hash') == _file_hash(path):
        return theme_core.scheme_path(home)
    scheme = generate_dynamic(path, current['mode'], current['variant'])
    return theme_core.write_scheme(scheme, home)


def set_scheme(args, home=None):
    import theme_core
    if args.dynamic:
        if args.theme:
            raise ValueError('Usa --dynamic o un tema fijo, no ambos.')
        if args.variant and args.variant not in VARIANTS:
            raise ValueError('Variante Material desconocida: ' + args.variant)
        scheme = generate_dynamic(_current_wallpaper(home), args.mode, args.variant)
        theme_core.write_scheme(scheme, home)
        return f"Esquema dinámico listo · {scheme['mode']} · {scheme['variant']}"
    if not args.theme:
        raise ValueError('Indica --dynamic o uno de los cinco temas fijos.')
    if args.variant:
        raise ValueError('--variant se usa con --dynamic.')
    selected = theme_core.parse(args.theme)
    if not selected:
        raise ValueError('Tema fijo desconocido. Usa space-black, tokyo, severance, fluent:light o fluent:dark.')
    style, variant = selected
    scheme = fixed_scheme(style, variant)
    if args.mode and args.mode != scheme['mode']:
        raise ValueError('--mode no cambia un tema fijo; elige fluent:light o fluent:dark.')
    config_path = theme_core.selection_path(home)
    previous = config_path.read_bytes() if config_path.exists() else None
    theme_core.write_selection_preserving(style, variant, home)
    try:
        theme_core.write_scheme(scheme, home)
    except Exception:
        if previous is None:
            config_path.unlink(missing_ok=True)
        else:
            theme_core._atomic_write(config_path, previous.decode('utf-8'))
        theme_core.invalidate()
        raise
    return f"Tema fijo listo · {scheme['name']} · {scheme['mode']}"


def main(argv=None):
    parser = argparse.ArgumentParser(prog='wysun scheme', description='Esquema de color de Wysun')
    subparsers = parser.add_subparsers(dest='action', required=True)
    command = subparsers.add_parser('set', help='activar un esquema fijo o generar colores desde el fondo')
    command.add_argument('theme', nargs='?', help='space-black, tokyo, severance, fluent:light o fluent:dark')
    command.add_argument('--dynamic', action='store_true', help='usar el fondo global configurado en Ajustes de Wysun')
    command.add_argument('--mode', choices=('light', 'dark'), help='forzar el modo de color dinámico')
    command.add_argument('--variant', choices=VARIANTS, help='elegir la variante Material You')
    args = parser.parse_args(argv)
    try:
        print(set_scheme(args))
    except (OSError, ValueError, RuntimeError) as error:
        parser.error(str(error))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
