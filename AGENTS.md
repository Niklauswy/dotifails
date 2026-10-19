# Wysun Desktop

- `apps/orbit/` es la fuente del lanzador y sus paneles. Las copias históricas en otros directorios no son la fuente de desarrollo.
- `apps/capture/` es la fuente integrada de Wysun Recorder y Wysun Screenshot; el repositorio histórico `loom` no se usa para distribuir ni desarrollar estos componentes.
- La aplicación instalada vive en `~/.local/share/orbit/app/`. No editar esa copia directamente: las actualizaciones comprueban su integridad y conservarían la edición como conflicto.
- Para cambios de Wysun pedidos para el escritorio activo, probar primero y después desplegar con `./instalar.sh --orbit-only`. Si termina sin conflictos, ejecutar `~/.local/bin/orbit reload` en la sesión gráfica. Comprobar la apertura real de los menús afectados antes de afirmar que el cambio está activo. El instalador completo usa el mismo código.
- `--wysun-only` es un alias de `--orbit-only`. Wysun es el nombre público; conservar rutas de datos, namespaces y comandos técnicos anteriores para mantener compatibilidad. Las versiones de captura se instalan separadas de los datos y no se retiran mientras puedan usarlas procesos activos.
- `--orbit-only` no instala dependencias ni cambia atajos. Si cambian, actualizar `home/.config/sxhkd/sxhkdrc` y migrar cuidadosamente la configuración activa con respaldo, preservando otras asignaciones del usuario y comprobando conflictos.
- Mantener notas, colores, historial, conexiones y cualquier otro dato privado fuera del repositorio. Se almacenan separados de `app/`.
- No reiniciar BSPWM, cerrar otras aplicaciones ni reinstalar todo el entorno para actualizar un panel.
- Comprobaciones relevantes: `python3 -m unittest discover -s tests -v`, `QT_QPA_PLATFORM=offscreen python3 tests/utility_ui.py`, `python3 tests/check_manifest.py`. Ejecutar también `python3 apps/capture/run_tests.py` y `python3 tests/wysun_installed_smoke.py`, con medios serializados. Las pruebas de sockets y escritorio necesitan acceso a la sesión; un bloqueo del sandbox no demuestra un fallo del producto.

- La sesión adicional Wysun / Hyprland usa `apps/quickshell/`, `home/.config/wysun/hyprland.lua` (Hyprland 0.55.x Lua) y el componente opcional `wayland`. Mantener BSPWM/X11 intacto; no cambiar el login, instalar dependencias del host ni reiniciar audio/portales sin autorización expresa. Validar con HOME/XDG temporales y medios sintéticos; pruebas de medios/compositor serializadas.
- El registro de sesión es independiente y reversible con `installer/session_registration.py`; nunca modificar por esa vía la sesión predeterminada ni el gestor de acceso. `docs/wayland.md` detalla preparación y recuperación.
