# Integración de Archivos con el escritorio

`./instalar.sh --orbit-only` registra por usuario el backend `orbit` de
`org.freedesktop.impl.portal.FileChooser` y el servicio `org.freedesktop.FileManager1`.
Configura además `inode/directory=orbit-files.desktop` en el hogar de destino, conservando las otras asociaciones MIME. La instalación completa incluye los paquetes del portal y `gio`. El código está en `apps/orbit/files_chooser.py` y `files_service.py`.

El selector usa las vistas de Wysun: abrir uno o varios archivos, elegir una
carpeta, guardar, elegir filtros MIME/glob, opciones adicionales y cancelar.
Guardar devuelve una ubicación a la aplicación; el selector no escribe el archivo.
Confirma reemplazos y devuelve nombres disponibles para guardados múltiples.
Los diálogos no ofrecen los atajos de borrar, cortar o renombrar del gestor.
Ctrl+H muestra archivos ocultos; Ctrl+L permite escribir una ruta.

El portal requiere xdg-desktop-portal 1.20 o posterior para descubrir el backend
en `~/.local/share/xdg-desktop-portal/portals/orbit.portal`. La preferencia
`~/.config/xdg-desktop-portal/portals.conf` cambia solo FileChooser y conserva las
otras preferencias, con GTK como alternativa. La activación se registra en
`~/.local/share/dbus-1/services` y en el servicio de usuario
`orbit-files-integration.service`.

Después de instalar, ejecutar `systemctl --user daemon-reload` y reiniciar
`xdg-desktop-portal.service` cuando no haya un selector abierto. No reiniciar los
portales durante una sesión activa de compartir pantalla. El navegador puede
conservar el selector anterior hasta cerrar todas sus ventanas y abrirlo de nuevo.
No es necesario reiniciar BSPWM. Algunas aplicaciones incorporan sus propios
diálogos y no utilizan el portal; no pueden sustituirse mediante esta asociación.
`GTK_USE_PORTAL=1` se prepara para los próximos inicios de sesión X11 y servicios.

`ShowItems` abre la carpeta y selecciona los elementos; `ShowFolders` abre carpetas;
`ShowItemProperties` presenta sus propiedades. Se aceptan rutas locales.
Si otro gestor mantiene el nombre FileManager1 sin permitir reemplazo, hay que
cerrar ese gestor normalmente para que Wysun pueda adquirirlo.

Comprobaciones:

```sh
QT_QPA_PLATFORM=offscreen python3 tests/files_chooser_ui.py
# El bus es temporal; no modifica el portal de la sesión gráfica.
dbus-run-session -- env QT_QPA_PLATFORM=offscreen python3 tests/files_portal_dbus.py
systemctl --user status orbit-files-integration.service
xdg-mime query default inode/directory
```

El instalador guarda las configuraciones previas en su respaldo habitual. Para
revertir, usar la recuperación del instalador y reiniciar el portal cuando esté
inactivo.
