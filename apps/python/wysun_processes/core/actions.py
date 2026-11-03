"""Identity-checked actions on a process (`p:<pid>:<start>`) or on every process of an app (`g:<app>`):
terminate, force, pause, resume and priority. Each target is pinned by PID and start time (pidfd), so a reused PID
is never signalled. Messages are in Spanish and never include command lines."""
import os

from wysun_services.process_data import Processes

_guard = None


def guard():
    global _guard
    if _guard is None:
        _guard = Processes()
    return _guard


def targets(sampler, key):
    """Rows `{pid, start, name}` the key stands for."""
    if key.startswith('p:'):
        _, pid, start = key.split(':', 2)
        return [dict(pid=int(pid), start=start, name='')]
    if key.startswith('g:'):
        app = key[2:]
        return [dict(pid=r['pid'], start=r['start'], name=r['name']) for r in sampler.rows if r['app'] == app]
    raise ValueError('Selección no válida')


def _checked(row):
    try:
        return guard().checked(row)
    except (FileNotFoundError, ProcessLookupError):
        raise RuntimeError('El proceso ya terminó.') from None


def act(sampler, key, action):
    """Send `action` (terminate, kill, pause, resume). Returns how many processes received it."""
    rows = targets(sampler, key)
    if not rows:
        raise RuntimeError('No hay procesos que coincidan.')
    done, problems = 0, []
    for row in rows:
        try:
            current = _checked(row)
            reason = guard().action_reason(current)
            if reason:
                raise PermissionError(reason)
            guard().act(row, action)
            done += 1
        except (RuntimeError, PermissionError, ProcessLookupError) as error:
            if len(rows) == 1:
                if isinstance(error, ProcessLookupError):
                    raise RuntimeError('El proceso ya terminó.') from None
                raise
            problems.append(str(error))
    if not done and problems:
        raise PermissionError(problems[0])
    return done


def set_priority(sampler, key, nice):
    if not -20 <= int(nice) <= 19:
        raise ValueError('La prioridad va de −20 a 19.')
    done = 0
    for row in targets(sampler, key):
        current = _checked(row)
        reason = guard().action_reason(current)
        if reason:
            raise PermissionError(reason)
        try:
            _checked(row)
            os.setpriority(os.PRIO_PROCESS, current['pid'], int(nice))
            done += 1
        except PermissionError:
            raise PermissionError('Subir la prioridad necesita permisos de administrador.') from None
    return done
