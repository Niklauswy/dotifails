"""Navigation routes of the QML UI as strings, and the stored form (a list, like the Widgets UI kept).

Routes: ``home``, ``search`` / ``search:<text>``, ``downloads``, ``library:<albums|artists|songs|lists>`` and
``collection:<id>`` (ids may contain ``:``, e.g. ``collection:artist:Name``)."""
LIBRARY_TABS = ('albums', 'artists', 'songs', 'lists')
# The Widgets UI stored tuples such as ('artists',) or ('collection', 'all'); map them on restore.
LEGACY = {('artists',): 'library:artists', ('albums',): 'library:albums', ('collection', 'all'): 'library:songs'}


def valid(route):
    kind, _, rest = str(route).partition(':')
    if kind in ('home', 'downloads'):
        return not rest
    if kind == 'search':
        return True
    if kind == 'library':
        return rest in LIBRARY_TABS
    return kind == 'collection' and bool(rest)


def restore(stored):
    """The route kept in the store (list) as a route string; anything unknown is ``home``."""
    parts = tuple(str(p) for p in (stored or ()))
    if parts in LEGACY:
        return LEGACY[parts]
    route = ':'.join(parts) if parts else 'home'
    return route if valid(route) else 'home'


def store(route):
    kind, sep, rest = route.partition(':')
    return [kind, rest] if sep else [kind]
