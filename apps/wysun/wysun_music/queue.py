"""What plays next: the context order plus the user's explicit "up next" list.

Like a streaming client, songs the user queues by hand play before the rest
of the context (playlist, album, search…) and do not move the context cursor,
so going back after them returns to where the context was.
"""
from music_library import PlaybackOrder

REPEAT_MODES = ('off', 'all', 'one')


class PlayQueue:
    def __init__(self):
        self.order = PlaybackOrder()
        self.up_next = []
        self.repeat = 'off'
        self.context = None

    @property
    def shuffle(self):
        return self.order.shuffle

    def start(self, keys, current, shuffle, context=None):
        self.order.start(keys, current, shuffle)
        self.order.repeat = self.repeat == 'all'
        self.context = context

    def set_shuffle(self, enabled):
        """Reshuffle only the unvisited future: history stays reversible."""
        order = self.order
        order.shuffle = enabled
        if order.current is None:
            return
        future = order.keys[order.index + 1:]
        if enabled:
            import random
            random.shuffle(future)
        else:
            future = [key for key in order.source if key in future]
        order.keys = order.keys[:order.index + 1] + future

    def set_repeat(self, mode):
        self.repeat = mode if mode in REPEAT_MODES else 'off'
        self.order.repeat = self.repeat == 'all'

    def cycle_repeat(self):
        self.set_repeat(REPEAT_MODES[(REPEAT_MODES.index(self.repeat) + 1) % len(REPEAT_MODES)])
        return self.repeat

    def add(self, keys):
        self.up_next.extend(keys)

    def add_next(self, keys):
        self.up_next[:0] = keys

    def remove_upcoming(self, index):
        """Remove the n-th entry of ``upcoming()``."""
        if index < len(self.up_next):
            del self.up_next[index]
            return
        position = self.order.index + 1 + index - len(self.up_next)
        if self.order.index < position < len(self.order.keys):
            del self.order.keys[position]

    def next(self, available):
        while self.up_next:
            key = self.up_next.pop(0)
            if available(key):
                return key
        return self.order.move(1, available)

    def previous(self, available):
        return self.order.move(-1, available)

    def has_next(self):
        return bool(self.up_next) or self.repeat != 'off' and bool(self.order.keys) \
            or self.order.index < len(self.order.keys) - 1

    def has_previous(self):
        return self.order.index > 0 or self.repeat == 'all' and bool(self.order.keys)

    def upcoming(self, limit=80):
        rest = self.order.keys[self.order.index + 1:]
        if self.repeat == 'all':
            rest += self.order.keys[:self.order.index]
        return (self.up_next + rest)[:limit]

    def export(self):
        return dict(order=self.order.export(), up_next=self.up_next, repeat=self.repeat, context=self.context)

    def restore(self, data):
        if not data:
            return
        self.order.restore(data.get('order') or data)
        self.up_next = list(data.get('up_next', []))
        self.context = data.get('context')
        repeat = data.get('repeat')
        # Sessions before the redesign stored a boolean "repeat list".
        self.set_repeat(repeat if isinstance(repeat, str) else 'all' if repeat or self.order.repeat else 'off')
