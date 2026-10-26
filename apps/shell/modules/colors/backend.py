#!/usr/bin/env python3
"""Small serialized JSON service for the native Colors panel's existing store."""
import json
import sys

# The shell runs this with the Wysun package root in PYTHONPATH (Paths.python).
from wysun_services.utility_data import Colors
from wysun_services.color_data import parse_color


def handle(request, store):
    action = request.get('action', 'read')
    if action == 'read':
        return {'data': store.read()}
    if action not in ('parse', 'save', 'favorite'):
        raise ValueError('Acción desconocida')
    color = parse_color(str(request.get('color', '')))
    if not color.isValid():
        raise ValueError('Introduce un color HEX, RGB o HSL válido, sin transparencia.')
    result = {'color': color.name().upper()}
    if action != 'parse':
        result['data'] = store.save(result['color'], action == 'favorite')
    return result


def main():
    store = Colors()
    for line in sys.stdin:
        request = {}
        try:
            request = json.loads(line)
            result = handle(request, store)
        except (ValueError, TypeError, AttributeError, OSError) as error:
            result = {'error': str(error)}
        if isinstance(request, dict):
            result.update(action=request.get('action'), revision=request.get('revision'))
        print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
