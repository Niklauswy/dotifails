# Integración de Wysun Archivos

La fuente de la aplicación está en `apps/orbit/files_app.py`; el instalador administra su copia en `~/.local/share/orbit/app/`. No editar directamente la copia instalada.

## Instalación

Desde la raíz de dotifails, ejecutar `./instalar.sh --orbit-only`. El perfil completo `desktop` despliega los mismos archivos. Ambos usan el registro de respaldos y conflictos del instalador para instalar:

- `bin/orbit-files` → `~/.local/bin/orbit-files` (ejecutable).
- `home/.local/share/applications/orbit-files.desktop` → `~/.local/share/applications/orbit-files.desktop`.
- La aplicación, junto con el resto de `apps/orbit/`.

Si el código de Wysun presenta conflictos, resolverlos antes de activar el nuevo gestor. Tras una instalación sin conflictos, ejecutar `~/.local/bin/orbit reload` y comprobar la apertura real. El lanzador independiente acepta rutas y URL `file://`, por ejemplo `orbit-files "$HOME/Downloads"`.

El perfil de escritorio del instalador configura **Wysun Archivos como gestor predeterminado** para `inode/directory`, tanto en una instalación nueva como con `--orbit-only`. La asociación se escribe en el hogar de destino y participa en los respaldos y la recuperación del instalador. Las preferencias MIME de otros tipos de archivo se conservan.

También instala el selector de archivos de Wysun y el servicio «Mostrar en carpeta» para aplicaciones compatibles. En una instalación completa se incluyen `xdg-desktop-portal`, su alternativa GTK y `gio`. Véase [Integración con el escritorio](files-integration.md).

## Comprobación del gestor predeterminado

Después de iniciar la sesión del escritorio instalado:

```sh
xdg-mime query default inode/directory
xdg-open "$HOME/Downloads"
```

La primera orden debe devolver `orbit-files.desktop`; la segunda debe abrir Wysun. Las aplicaciones que incorporan un selector propio o llaman directamente a otro ejecutable pueden mantener su comportamiento particular.

## Reversión

Para volver al gestor anterior, ejecutar `xdg-mime default IDENTIFICADOR_ANTERIOR.desktop inode/directory` usando exactamente el identificador guardado. Si no había una asociación explícita, retirar solamente la entrada añadida para `inode/directory` o restaurar el respaldo si no hubo cambios posteriores. No sobrescribir cambios MIME posteriores sin revisarlos.

El instalador conserva su propio diario de recuperación para los archivos desplegados. Los archivos personales no pertenecen a la aplicación y nunca deben eliminarse al revertirla.

## Uso

- `Super + Alt + F` abre el gestor mediante el comando existente `orbit files`; no se reasignan teclas.
- El lanzador ofrece «Wysun Archivos». La búsqueda interna anterior permanece disponible.
- Ctrl+T/Ctrl+W: abrir/cerrar pestaña. Ctrl+L: escribir una ruta. Alt+flechas: historial y carpeta superior.
- Ctrl+F filtra nombres en la carpeta actual; no es una búsqueda recursiva.
- Ctrl+H muestra ocultos. Ctrl+C/X/V copia, corta y pega desde las vistas de archivos.
- F2 cambia el nombre; Supr envía a la papelera tras confirmación; Espacio muestra el panel de vista previa.
- Las operaciones se ejecutan en segundo plano, una a la vez. Se rechazan colisiones en lugar de reemplazar archivos existentes. Una operación por lotes puede completarse parcialmente: el mensaje identifica los destinos ya procesados.
- Favoritos y preferencias se guardan mediante QSettings fuera del código.

## Alcance de esta versión

Gestión de archivos locales con pestañas, lista/cuadrícula, favoritos, propiedades, terminal y vista previa existente de Wysun. No implementa montaje de volúmenes, conexiones remotas, extracción de archivos comprimidos, búsqueda recursiva ni una vista propia para restaurar la papelera. El gestor alternativo permanece disponible para esas tareas. Las aplicaciones compatibles con el portal utilizan el selector de Wysun.

## Verificación

`python3 -m unittest discover -s tests -p test_files_ops.py -v` comprueba las operaciones con archivos temporales. `QT_QPA_PLATFORM=offscreen python3 tests/files_ui.py` comprueba modelos, navegación y operaciones desde la interfaz. Repetir sin offscreen en la sesión X11 para validar la apertura gráfica; no basta la asociación MIME.
