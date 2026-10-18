"""Narrow, repeatable migration for the supported dotifails Picom 12 rules."""
import re


def orbit_glass_rules(text):
    # Do not replace global opacity or unrelated per-application rules.
    pattern=r'\{\s*match\s*=\s*"class_g = \'Orbit\'";[^{}]*\}'
    rule='{ match = "class_g = \'Orbit\'"; corner-radius = 22; shadow = true; blur-background = true; fade = false; }'
    text,count=re.subn(pattern,lambda _:rule,text,count=1)
    if not count:raise ValueError('No se encontró la regla simple de Wysun; conserva y revisa tu configuración de Picom.')
    text=text.replace('"window_type = \'normal\' && !fullscreen"','"window_type = \'normal\' && !fullscreen && class_g != \'Orbit\'"')
    return text
