# Instalador de Wysun

El instalador gráfico recorre tres momentos, cada uno con una pieza animada propia: **Tu equipo** (la distribución se lee y sus
comprobaciones aparecen como píldoras; única opción: actualizar también el sistema), **Contenido** (Wysun siempre incluido, más Neovim,
Wysun Tools y el arranque Macrodata, y Brave/Discord/Obsidian por Flatpak) e **Instalación** (una forma que cambia en cada etapa real de
`main.py`). Las comprobaciones de la selección corren en segundo plano y «Instalar» sale de Contenido; «Detalles» muestra
etapas, orden y paquetes. Arriba, un indicador de formas marca el paso; abajo, la barra lleva la acción y el progreso.

Código: `installer/gui.py` (controlador y páginas), `installer/scenes.py` (piezas expresivas), `installer/material_widgets.py`
(controles sobre el kit Material de Music/Files) y `installer/journey.py` (textos, etapas y comprobaciones, sin Qt).
Las opciones avanzadas (`--config-only`, `--skip-nvim-tools`, perfiles, pantalla de acceso) quedan solo en la CLI.

## Abrir

Desde la raíz del proyecto:

```sh
./wysun-installer
./wysun-installer-preview
# También: ./instalar.sh --gui o ./instalar.sh --preview
```

El modo normal reconoce una instalación por su recibo y por los archivos de Wysun. Ofrece mantenimiento, diagnóstico, recuperación y modificación de componentes. La vista previa ignora esa detección y permite completar el recorrido: sus operaciones se simulan en memoria, no solicita privilegios ni ejecuta instalación, restauración o reinicio.

El ejecutable del repositorio necesita el resto del proyecto junto a él; no es un AppImage. La instalación administrada publica `wysun-installer`, **Instalador de Wysun** y **Vista previa del instalador de Wysun** en el menú. El gestor instalado lleva una copia pequeña de los controles Material, fuentes, tokens y fondos, por lo que abre aunque la copia original del proyecto desaparezca. Para aplicar una instalación real necesita una fuente completa y válida.

Si falta PySide6, el lanzador normal ofrece preparar su dependencia desde una terminal. La vista previa nunca prepara dependencias automáticamente.

## Instalación completa

La base admitida es Debian 13 o Parrot 7, x86_64. La revisión comprueba distribución, arquitectura, archivos, destino, permisos, espacio, estado de dpkg y requisitos del arranque. La resolución APT se realiza antes de actualizar o instalar paquetes.

La selección permite preparar:

- Aplicaciones Wysun: Music, Files, Recorder y utilidades.
- Escritorio: Hyprland, shell Quickshell, lanzador, Settings, capturas, bloqueo y runtime privado.
- Terminal y shell, Neovim y herramientas del proyecto.
- Arranque Macrodata: GRUB, Plymouth y la pantalla de acceso con greetd (la misma terminal del bloqueo). Cambia el gestor de acceso a greetd para el próximo arranque, con el anterior registrado para restaurarlo; ver [docs/boot.md](boot.md).
- Brave, Discord y Obsidian mediante Flatpak, de forma opcional.

El escritorio requiere sus aplicaciones y la terminal en la selección gráfica. Los perfiles de hardware son opcionales; no se trasladan datos personales o ajustes particulares de otra máquina.

Las opciones nuevas de preparación son explícitas:

```sh
./instalar.sh --cli --components desktop,wayland,terminal,editor,tools,boot \
  --boot-components grub,plymouth --upgrade-system --prepare-repositories

# Plan sin modificaciones:
./instalar.sh --cli --components desktop,wayland,terminal,editor,tools,boot \
  --boot-components grub,plymouth --upgrade-system --prepare-repositories --plan
```

`--prepare-repositories` añade solo los backports oficiales de la distribución detectada si faltan. No reemplaza fuentes existentes, cambia de distribución, descarga claves nuevas ni desactiva firmas. Usa [Debian Backports](https://backports.debian.org/Instructions/) en Debian y [los repositorios de Parrot](https://www.parrotsec.org/docs/mirrors/mirrors-list/) en Parrot. Se guarda un diario previo en `/var/lib/dotifails/repositories/backups/`.

Después se actualizan los índices APT y se simula la resolución de dependencias. Las versiones y la compatibilidad ABI de Hyprland siguen comprobándose mediante `wayland.py` y los manifiestos fijados. Un fallo de resolución detiene el proceso antes de actualizar paquetes o copiar configuraciones.

`--upgrade-system` actualiza los paquetes de la distribución actual con `--no-remove` y conserva los archivos de configuración existentes. No realiza un salto de distribución. Estas opciones se rechazan junto a `--config-only` y los modos `--only`.

El proceso conserva el motor de instalación con diario, respaldos, conflictos, registros privados y cancelación entre operaciones. APT, compilación e initramfs no se interrumpen por la fuerza. La recuperación de archivos no desinstala paquetes ni revierte una actualización del sistema.

Al completar la instalación real se ofrece un reinicio voluntario. La sesión registrada es **Wysun / Hyprland**; el usuario la elige en su gestor de acceso existente. No se cambia su sesión predeterminada ni se sustituye el gestor de acceso.

## Wysun Player

`--orbit-only` instala `~/.local/bin/wysun-player` y `wysun-player.desktop`, pero no cambia aplicaciones predeterminadas ni instala
dependencias. La instalación completa añade `python3-pyside6.qtopengl` y `python3-pyside6.qtopenglwidgets` (render por GPU) y fija
Wysun Player como predeterminado de sus tipos de imagen, video y audio en `~/.config/mimeapps.list`, conservando lo anterior como
alternativa; `dotifails restore ID` lo deshace. `dotifails doctor` avisa si falta OpenGL (el reproductor usa entonces el render por
software). Ver `docs/player.md`.

## Mantenimiento y validación

```sh
./instalar.sh --installer-only
QT_QPA_PLATFORM=offscreen python3 tests/installer_ui.py
python3 -m unittest discover -s tests -p 'test_*installer*.py' -v
python3 -m unittest discover -s tests -p test_boot.py -v
python3 -m unittest discover -s tests -p test_wayland_install.py -v
python3 tests/check_manifest.py
python3 tests/wysun_installed_smoke.py
```

`--installer-only` despliega el gestor y sus entradas de menú con respaldo, sin instalar paquetes ni modificar el escritorio. No se ha desplegado este prototipo en la instalación activa.

Las pruebas gráficas incluyen claro y oscuro, el recorrido simulado, mantenimiento, teclado, instalación/restauración reales en HOME temporal, errores y cancelación. La copia instalada se prueba fuera del checkout, sin depender del repositorio original. Estas pruebas no equivalen a una instalación integral ni a un arranque físico en una máquina Debian nueva.
