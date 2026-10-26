"""Music's own wording: durations and song counts."""


def long_duration(seconds):
    minutes = int(seconds or 0) // 60
    hours, minutes = divmod(minutes, 60)
    return f'{hours} h {minutes} min' if hours else f'{minutes} min'


def songs(count):
    return f'{count} canción' if count == 1 else f'{count} canciones'
