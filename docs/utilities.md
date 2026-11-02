# Utilidades del día a día

Herramientas pequeñas que acompañan al escritorio Wysun. Reemplazan a `wysun tools`, que se retiró.

## Dónde van

Cada utilidad es **un paquete propio** en `apps/python/`, como cualquier app de Wysun:

```
apps/python/wysun_NOMBRE/
  __init__.py      una línea: qué hace
  __main__.py      `python3 -m wysun_NOMBRE`
  …                módulos y recursos (p. ej. static/)
```

- Se abre con `wysun NOMBRE`: una entrada en `MODULES` de `bin/wysun` (`'NOMBRE': ('app', 'wysun_NOMBRE', [])`) y una línea en su ayuda. Nada de lanzadores sueltos ni alias.
- Se instala y actualiza con el resto de Wysun (`./instalar.sh --wysun-only` → `~/.local/share/wysun/app/`).
- Solo biblioteca estándar salvo motivo explícito; si un programa externo (como `ffmpeg`) falta, la utilidad sigue funcionando sin esa parte.
- Datos y caché fuera del repositorio: `~/.cache/wysun/NOMBRE`, `~/.local/share/wysun/NOMBRE`, `~/.config/wysun/NOMBRE*`.
- Añade el paquete a `PACKAGES` de `tests/test_python_layout.py` y una prueba en `tests/shell_bridge/test_dispatcher.py`.

## LANShare

```sh
wysun lanshare ~/Videos            # http://IP-LOCAL:8000 en la red
wysun lanshare . --port 9000
wysun lanshare ~/Fotos --readonly  # sin subidas ni carpetas nuevas
```

Explorador de carpetas con miniaturas y vistas previas de video (con `ffmpeg`/`ffprobe`; sin ellos no hay miniaturas), reproducción con saltos (Range, compatible con Safari/iPhone), subida de archivos y descarga de carpetas en `.zip`. Caché en `~/.cache/wysun/lanshare`.

Escucha en todas las interfaces y **no pide contraseña**: cualquiera en la misma red ve la carpeta y, sin `--readonly`, puede subir archivos. Úsalo en redes de confianza y detenlo con `Ctrl+C` al terminar.
