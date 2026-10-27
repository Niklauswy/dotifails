"""Music's wording in Spanish: durations, song counts, greeting and date (no Qt)."""
import time

DAYS = ('lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo')
MONTHS = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre',
          'noviembre', 'diciembre')


def clock(seconds):
    """m:ss, or h:mm:ss from one hour."""
    seconds = max(0, int(seconds or 0))
    hours, rest = divmod(seconds, 3600)
    return f'{hours}:{rest // 60:02}:{rest % 60:02}' if hours else f'{rest // 60}:{rest % 60:02}'


def long_duration(seconds):
    minutes = int(seconds or 0) // 60
    hours, minutes = divmod(minutes, 60)
    return f'{hours} h {minutes} min' if hours else f'{minutes} min'


def songs(count):
    return f'{count} canción' if count == 1 else f'{count} canciones'


def greeting(hour=None):
    hour = time.localtime().tm_hour if hour is None else hour
    return 'Buenos días' if 5 <= hour < 12 else 'Buenas tardes' if 12 <= hour < 20 else 'Buenas noches'


def today(now=None):
    now = now or time.localtime()
    return f'{DAYS[now.tm_wday]} {now.tm_mday} de {MONTHS[now.tm_mon - 1]}'
