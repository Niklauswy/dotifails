# Instalador de Wysun

`./instalar.sh` instala el escritorio completo: paquetes del sistema, runtime privado del shell, sesión Wysun /
Hyprland, todas las aplicaciones, terminal, Neovim con sus plugins y Mason, arranque (GRUB, Plymouth y la pantalla
de acceso con greetd) y Brave, Discord y Obsidian por Flatpak. No tiene opciones de usuario; solo acepta
`--dry-run`, que imprime el plan y no cambia nada. Se ejecuta como usuario normal con `sudo` disponible.

## Otro equipo

```sh
git clone https://github.com/Niklauswy/dotifails.git ~/.local/share/wysun/source
~/.local/share/wysun/source/instalar.sh
```

O bien `sh bootstrap.sh`, que clona la rama `main` y ejecuta exactamente eso. La copia se queda en
`~/.local/share/wysun/source`: es la fuente de las actualizaciones de ese equipo. Si ya tienes el repositorio,
ejecuta `./instalar.sh` desde su raíz. La base admitida es Debian 13 o Parrot 7, x86_64, con Internet y varios GB
libres.

La instalación pide autorización cuando la necesita y conserva los cambios personales con respaldos y conflictos.
Una instalación nueva usa el fondo `purple-abstract` y Material You; al terminar, elige **Wysun / Hyprland** en el
gestor de acceso.

## Actualizar

```sh
wysun update
wysun update --check
```

`wysun update` hace `git pull --ff-only` en la copia fuente registrada al instalar y vuelve a aplicar. Siempre:
código, aplicaciones, configuración, atajos (`hyprland.lua`) y lanzador. Solo cuando sus entradas cambiaron desde
la última instalación o actualización: paquetes del sistema, reconstrucción del runtime privado, herramientas de
Neovim, pantallas de arranque y registro de la sesión; el `sudo` se pide solo entonces. Después ejecuta
`wysun reload` y, si cambió `apps/shell`, reinicia solo el shell. Aplica únicamente los componentes que ese equipo
ya tiene.

Un icono en la barra avisa cuando hay cambios en `main`; al pulsarlo abre una terminal con `wysun update`.
`wysun update --check` consulta esos cambios, escribe `~/.local/state/wysun/update.json` e imprime el mismo JSON,
sin aplicar nada.

Para desarrollar: edita el repositorio, haz commit y `git push`; despliega en el equipo principal con
`wysun update` (con la copia al día o por delante, el `pull` no hace nada). Los demás equipos usan
`wysun update` o el aviso de la barra.

## Conflictos y respaldos

Las configuraciones se instalan como copias editables. Antes de reemplazarlas se guardan en
`~/.local/state/wysun/install/backups/ID/before/`, con un diario de operaciones. Si editaste un archivo
administrado, la actualización lo conserva y deja la versión nueva en `incoming/`. Los archivos borrados
deliberadamente también cuentan como cambios locales. Una actualización no toma archivos que Wysun nunca
administró en ese equipo (por ejemplo, un `~/.config/gtk-3.0` propio): los deja tal cual y los nombra al final.

`wysun doctor` diagnostica la instalación y `wysun restore` lista los respaldos; `wysun restore ID` recupera uno y
conserva las ediciones posteriores en `changes-before-restore/`. Restaura de más reciente a más antiguo. No
desinstala paquetes ni borra datos personales.

## Perfiles de equipo

No hay perfiles en el instalador. Si un equipo necesita ajustes propios (por ejemplo, la pantalla táctil), copia
el perfil a mano:

```sh
cp machines/samsung-touchscreen.sh ~/.config/wysun/machine.sh
```

## Desarrollo del plugin

`python3 installer/runtime_build.py` construye el runtime privado y el plugin `Wysun.*`; `wysun update` también lo
reconstruye cuando cambia `plugin/`. Para el resto de comprobaciones, ver [mantenimiento](maintenance.md).
