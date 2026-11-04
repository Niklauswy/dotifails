# Wysun Desktop

El escritorio Wysun sobre **Hyprland/Wayland**, preparado para instalarse en **Parrot 7 o Debian 13, x86_64**: Wysun, Quickshell, Ghostty, Neovim y Zsh. Mantiene los atajos, transparencias y animaciones rápidas. Incluye tres perfiles: **Severance**, **Tokyo** y **Space Black**.

## Familia Wysun

Wysun es el nuevo nombre de Órbita. El lanzador, Music, Files y Recorder se desarrollan y distribuyen desde este repositorio. Recorder está en `apps/recorder/` y la captura de pantalla en el shell (`apps/shell/modules/areapicker`); el lanzador y los paneles siguen en `apps/python/`.

- `wysun`: lanzador y búsqueda.
- `wysun music`, `wysun files`, `wysun settings`: aplicaciones y ajustes.
- `wysun recorder`: biblioteca y editor de vídeo; `wysun recorder --quick-record`: preparar una grabación.
- `wysun-shell screenshot`: selecciona una región para copiar y guardar, anotar o leer su texto.
- `wysun update`: actualizar la familia completa.

La actualización no sustituye las grabaciones activas; los datos privados viven fuera del repositorio, bajo las rutas `wysun`. [Integración, nombres y compatibilidad](docs/wysun.md).

## Sesión Wysun / Hyprland

La instalación prepara la sesión **Wysun / Hyprland**, Quickshell y las aplicaciones Python/PySide6 conservadas. Revisa paquetes, portales, sesión y recuperación en la [guía Wayland](docs/wayland.md).

## Instalar en otro equipo

Desde una cuenta normal con acceso a `sudo`, conexión a Internet y varios GB libres:

```sh
git clone https://github.com/Niklauswy/dotifails.git ~/.local/share/wysun/source
~/.local/share/wysun/source/instalar.sh
```

`sh bootstrap.sh` hace exactamente eso: clona la rama `main` y ejecuta el instalador. La copia se queda en `~/.local/share/wysun/source` y es la fuente de las actualizaciones de ese equipo. Si ya tienes el repositorio, ejecuta `./instalar.sh` desde su raíz.

`./instalar.sh` instala todo: paquetes, runtime privado del shell, sesión Wysun / Hyprland, aplicaciones, terminal, Neovim, arranque (GRUB, Plymouth y la pantalla de acceso) y Brave/Discord/Obsidian por Flatpak. No tiene opciones y solo acepta `--dry-run`, que muestra el plan sin cambiar nada. No lo ejecutes con `sudo`: pide autorización cuando la necesita. Una instalación nueva usa el fondo `purple-abstract` y Material You: los colores salen del wallpaper y el modo (automático, claro u oscuro) se conserva al actualizar. Al terminar, cierra sesión cuando quieras y elige **Wysun / Hyprland** en el gestor de acceso. El instalador conserva los cambios personales, muestra conflictos, guarda el registro y permite recuperar respaldos.

El instalador se valida con HOME/XDG temporales y con una sesión Wayland anidada. Consulta el alcance exacto en [Validación](docs/validation.md) y la [guía del instalador](docs/installer.md).

## Qué incluye

- Hyprland y su configuración en Lua, monitores detectados, escritorios administrados por el compositor y agentes de D-Bus y Polkit. Al desconectar pantallas se recuperan los perfiles y las ventanas permanecen donde el compositor las coloque.
- Quickshell (runtime privado compilado por `installer/runtime_build.py`, ver [ARCHITECTURE.md](ARCHITECTURE.md)): barra con módulos de recursos, conexiones, audio, calendario y notificaciones; paneles de escritorio integrados con Wysun. La apariencia se mantiene mediante transparencias y animaciones del compositor.
- Wysun nativa en Qt: aplicaciones, ventanas, portapapeles, OCR local en español/inglés, archivos con vistas previas, reproductor multimedia, snippets, calculadora y emojis a color.
- Conexiones Wi-Fi, Bluetooth, VPN y SSH; menú de sesión; ajustes visuales de Hyprland, pantallas, barra y atajos.
- Notas Markdown, procesos y selector de color con lupa, integrado con el portal de color.
- Ghostty **1.2.3**, Neovim **0.11.5**, Node **24.19.0**, Starship **1.24.1**; versiones y SHA-256 en `manifests/artifacts.json`. Ghostty se extrae una vez, sin depender de FUSE al abrir terminales.
- NvChad con plugins fijados por `lazy-lock.json`, LSP, formato, búsqueda difusa, tareas, depuración y herramientas de JS/TS, C/C++ y Python. Las versiones de Mason están en `manifests/mason.json`.
- Zsh, autocompletado/sugerencias, resaltado, fzf y prompt Starship. Mise **2026.9.14** cambia versiones por proyecto; Node está disponible directamente y NVM se conserva bajo demanda.
- Apariencia: GTK Arc-Darker, iconos Win11-Dark, cursor Fluent y el prompt compacto de Starship.
- Incluye la barra, notificaciones, paleta de Ghostty, Neovim, CaskaydiaCove Nerd Font (terminal), Google Sans Flex (interfaz y GTK), Noto Color Emoji, `eza`, `bat` y FZF. El fondo queda en la biblioteca de Wysun.

Los paquetes APT y las aplicaciones Flatpak reciben las versiones que publica cada distribución. Los binarios externos y plugins tienen versiones fijadas; los paquetes del sistema no forman una imagen inmutable.

## Atajos principales

| Teclas | Acción |
| --- | --- |
| Super + Enter | Terminal |
| Super + Espacio / D | Wysun |
| Super + V | Portapapeles |
| Super + Alt + F | Archivos |
| Super + C / L | Calculadora / emoji |
| Super + N | Conexiones |
| Super + X | Sesión y energía |
| Super + Alt + coma | Ajustes del escritorio y atajos |
| Super + Shift + N / K / C | Notas / procesos / colores |
| Super + Shift + W | Fondo de pantalla |
| Super + J / K | Ventana siguiente / anterior |
| Super + W / Ctrl + W | Cerrar / forzar cierre |
| Super + F | Pantalla completa |

Ver todos en [hyprland.lua](config/.config/wysun/hyprland.lua). Los paneles tienen navegación por teclado y Escape para cerrar.

## Actualizar

```sh
wysun update
wysun update --check
wysun doctor
```

`wysun update` hace `git pull --ff-only` en la copia fuente y vuelve a aplicar. Siempre: código, aplicaciones, configuración, atajos y lanzador. Solo cuando cambiaron sus entradas: paquetes del sistema, reconstrucción del runtime privado, herramientas de Neovim, pantallas de arranque y registro de la sesión; pide `sudo` solo entonces. Después ejecuta `wysun reload` y, si cambió `apps/shell`, reinicia solo el shell. Aplica solo los componentes que ese equipo ya tiene.

Un icono en la barra avisa cuando hay cambios en `main`; al pulsarlo abre una terminal con `wysun update`. `wysun update --check` escribe `~/.local/state/wysun/update.json` e imprime el mismo JSON sin aplicar nada.

Las configuraciones se instalan como **copias** editables. Antes de reemplazarlas se guardan en `~/.local/state/wysun/install/backups/ID/before/`, junto con un diario de operaciones. Si has editado un archivo administrado, una actualización lo conserva y deja la propuesta en `incoming/`; devuelve código 2 para indicar conflictos. Los cambios locales incluyen archivos borrados deliberadamente.

Para desarrollar los menús, edita `apps/python/` en este repositorio, haz commit y `git push`, y despliega con `wysun update`. Así el escritorio usa el mismo código que recibirá una instalación nueva. Notas y Color son ventanas nativas independientes; sus datos privados se conservan aparte. [Flujo de desarrollo y actualización](docs/maintenance.md#cambiar-wysun-y-usar-la-misma-versión-en-tu-escritorio).

## Recuperar

```sh
wysun restore
wysun restore ID_DEL_RESPALDO
```

`wysun restore` recupera el estado anterior y conserva ediciones posteriores en `changes-before-restore/`. Se deben restaurar los respaldos de más reciente a más antiguo. No desinstala paquetes APT/Flatpak ni borra datos personales de Wysun. Una instalación fallida muestra el ID recuperable y puede repetirse después de corregir la causa.

La configuración del escritorio y las fuentes viven en `~/.config` y `~/.local/share`; los comandos en `~/.local/bin`. Las herramientas conservan directorios por versión para permitir restaurar los enlaces activos. [Arquitectura y pruebas](docs/maintenance.md).

Ghostty: **Ctrl + Alt + Shift + flechas** ajusta los splits internos en pasos de 10 píxeles. Se oculta el indicador de dimensiones durante el ajuste. El redimensionado sigue siendo por pasos, sin interpolación animada.

## Versiones por proyecto con mise

Mise se instala con versión y SHA-256 fijados, y Zsh lo activa al abrir una terminal. Desde la raíz de un proyecto, `mise use node@24` o `mise use python@3.12` instala la versión elegida y la registra en `mise.toml`. Al entrar en esa carpeta se activa; al salir se recuperan las versiones del entorno anterior. `mise ls` muestra lo instalado y `mise use --global node@24` fija el valor predeterminado. Para scripts o tareas sin shell interactiva: `mise exec -- comando`.

La instalación inicial conserva el Node fijado del escritorio como alternativa cuando el proyecto no selecciona otra versión. NVM sigue disponible manualmente; evita alternar ambos gestores dentro de la misma shell. No se cambia el Python del sistema. Las instalaciones personales de lenguajes y sus preferencias globales no se copian al repositorio; comparte el `mise.toml` de cada proyecto.

## Privacidad y alcance

No incluye historial del portapapeles, notas, conexiones Wi-Fi, claves SSH, tokens, cachés ni proyectos personales. Cada usuario empieza con datos nuevos. No cambia Git global, contraseñas, particiones ni el gestor de acceso existente.

Esta versión está orientada a Wysun / Hyprland sobre Wayland y a las rutas XDG predeterminadas del usuario. No convierte otras distribuciones automáticamente. El soporte de Wi-Fi, Bluetooth, aceleración gráfica y pantallas depende de los controladores del equipo.

[Manual de Wysun](apps/python/README.md) · [Neovim](config/.config/nvim/README.md) · [Créditos](docs/credits.md) · [Validación](docs/validation.md)

En Ajustes → Wallpaper & style eliges el fondo con el carrusel (`Super+Shift+W`) y el modo —automático, claro u oscuro—; los colores y el acento salen siempre del wallpaper actual y se aplican al instante en todas las aplicaciones, sin reinstalar el escritorio ([guía de temas](docs/themes.md)). Cada cambio se respalda.

### Utilidades del día a día

Cada utilidad es un paquete propio en `apps/python` y se abre con `wysun`; se instalan y actualizan con el resto de Wysun (`wysun update`). [Guía](docs/utilities.md).

- `wysun lanshare [CARPETA]`: comparte una carpeta con la red local desde el navegador (explorar, ver video con miniaturas, subir y descargar carpetas en `.zip`).

### Arranque y acceso

La instalación completa incluye el arranque inspirado en *Severance*: GRUB como la tarjeta azul de una cinta de formación (con efecto VHS), y Plymouth como un CRT de oficina en fósforo que hojea el índice de proyectos, abre Cold Harbor y llena el indicador con el progreso real. Forma parte de la instalación completa y `wysun update` lo reaplica cuando cambian sus archivos; los respaldos del sistema se recuperan desde la terminal. [Instalación, compatibilidad y recuperación](docs/boot.md).
