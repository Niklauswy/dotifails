# Wysun Desktop · dotifails

El escritorio Wysun sobre **Hyprland/Wayland**, preparado para instalarse en **Parrot 7 o Debian 13, x86_64**: Wysun, Quickshell, Ghostty, Neovim y Zsh. Mantiene los atajos, transparencias y animaciones rápidas. Incluye tres perfiles: **Severance**, **Tokyo** y **Space Black**.

## Familia Wysun

Wysun es el nuevo nombre de Órbita. El lanzador, Music, Files, Recorder y Screenshot se desarrollan y distribuyen desde este repositorio. Recorder y Screenshot están en `apps/capture/`; el lanzador y los paneles siguen en `apps/wysun/`.

- `wysun`: lanzador y búsqueda.
- `wysun music`, `wysun files`, `wysun settings`: aplicaciones y ajustes.
- `wysun recorder`: biblioteca y editor de vídeo; `wysun recorder --quick-record`: preparar una grabación.
- `wysun screenshot`: captura y editor; `wysun screenshot --library`: biblioteca.
- `./instalar.sh --wysun-only`: actualizar la familia completa. `--orbit-only` sigue siendo compatible.

Las rutas privadas, los proyectos y los comandos antiguos se conservan. La actualización no migra datos ni sustituye las grabaciones activas. [Integración, nombres y compatibilidad](docs/wysun.md).

## Sesión Wysun / Hyprland

El componente `wayland` se instala por defecto y prepara **Wysun / Hyprland**, Quickshell y las aplicaciones Python/PySide6 conservadas. Revisa paquetes, portales, selección y recuperación en la [guía Wayland](docs/wayland.md).

```sh
./instalar.sh --source "$PWD" --components desktop,wayland --plan
```

## Instalar

Desde una cuenta normal con acceso a `sudo`, conexión a Internet y varios GB libres:

```sh
sudo apt-get update && sudo apt-get install --yes git python3 ca-certificates && git clone --depth 1 https://github.com/Niklauswy/dotifails.git && cd dotifails && ./instalar.sh
```

Si ya tienes esta carpeta, ejecuta `./instalar.sh`. Desde una sesión gráfica abre el **instalador visual**: bienvenida, vista previa del tema, componentes, aplicaciones opcionales, revisión, progreso real y primeros pasos. Si falta Qt, ofrece preparar únicamente la interfaz desde la terminal. La instalación del escritorio empieza después de revisar el plan.

Puedes seleccionar escritorio, sesión Wysun / Hyprland, terminal, Neovim, herramientas y Blue CRT; el escritorio, la sesión y Neovim incluyen lo que necesitan. Desmarcar algo conserva su instalación actual. GRUB, carga y acceso también se eligen por separado. El instalador conserva los cambios personales, muestra conflictos, guarda el registro y permite recuperar respaldos del hogar o del arranque. [Guía del instalador visual](docs/installer.md).

Una instalación nueva utiliza Severance (estilo Space Black) y las actualizaciones conservan el tema elegido (también `--theme fluent-light` o `--theme fluent-dark`). No lo ejecutes con `sudo`: la interfaz pide autorización cuando corresponde. Al terminar, cierra sesión cuando quieras y elige **Wysun / Hyprland** en el gestor de acceso. El instalador mantiene abierta tu sesión.

El instalador se valida con HOME/XDG temporales y con una sesión Wayland anidada. Consulta el alcance exacto en [Validación](docs/validation.md).

```sh
./instalar.sh --gui
./instalar.sh --cli
./instalar.sh --dry-run
./instalar.sh --components terminal,editor --plan
./instalar.sh --extras brave,discord,obsidian
./instalar.sh --profile samsung-touchscreen
```

Los argumentos de instalación mantienen el modo terminal, así como las ejecuciones sin sesión gráfica. `--cli` lo fuerza explícitamente y `--plan` muestra paquetes, versiones y comando sin aplicar cambios.

El perfil Samsung es opcional y específico del equipo con pantalla táctil defectuosa. No se aplica a otras instalaciones. Las aplicaciones opcionales se instalan desde Flathub para el usuario; también puedes instalar solo una, por ejemplo `--extras obsidian`.

## Qué incluye

- Hyprland y su configuración en Lua, monitores detectados, escritorios administrados por el compositor y agentes de D-Bus y Polkit. Al desconectar pantallas se recuperan los perfiles y las ventanas permanecen donde el compositor las coloque.
- Quickshell (runtime privado compilado por `installer/runtime_build.py`, ver [ARCHITECTURE.md](ARCHITECTURE.md)): barra con módulos de recursos, conexiones, audio, calendario y notificaciones; paneles de escritorio integrados con Wysun. La apariencia se mantiene mediante transparencias y animaciones del compositor.
- Wysun nativa en Qt: aplicaciones, ventanas, portapapeles, OCR local en español/inglés, archivos con vistas previas, reproductor multimedia, snippets, calculadora y emojis a color.
- Conexiones Wi-Fi, Bluetooth, VPN y SSH; menú de sesión; ajustes visuales de Hyprland, pantallas, barra y atajos.
- Notas Markdown, procesos y selector de color con lupa, integrado con el portal de color.
- Ghostty **1.2.3**, Neovim **0.11.5**, Node **24.19.0**, Starship **1.24.1**; versiones y SHA-256 en `manifests/artifacts.json`. Ghostty se extrae una vez, sin depender de FUSE al abrir terminales.
- NvChad con plugins fijados por `lazy-lock.json`, LSP, formato, búsqueda difusa, tareas, depuración y herramientas de JS/TS, C/C++ y Python. Las versiones de Mason están en `manifests/mason.json`.
- Zsh, autocompletado/sugerencias, resaltado, fzf y prompt Starship. Mise **2026.9.14** cambia versiones por proyecto; Node está disponible directamente y NVM se conserva bajo demanda.
- Severance: ARK-Dark, Flat-Remix-Green-Dark, cursor Breeze y el prompt actual de Starship. Tokyo: Arc-Darker, Win11-Dark, cursor Fluent y el prompt compacto.
- Ambos mantienen la barra, notificaciones, paleta de Ghostty, Neovim, FiraCode Nerd Font, Inter, Noto Color Emoji, `eza`, `bat` y FZF. Los dos fondos quedan en la biblioteca de Wysun.

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

## Actualizar y recuperar

```sh
dotifails gui
dotifails doctor
dotifails update
dotifails update --source /ruta/dotifails
dotifails update --orbit-only && orbit reload
dotifails restore
dotifails restore ID_DEL_RESPALDO
```

Para actualizar únicamente el instalador y su entrada en el menú de aplicaciones: `./instalar.sh --installer-only`. No reinstala Wysun, paquetes ni configuraciones del escritorio.

Las configuraciones se instalan como **copias** editables. Antes de reemplazarlas se guardan en `~/.local/state/dotifails/backups/ID/before/`, junto con un diario de operaciones. Si has editado un archivo administrado, una actualización lo conserva y deja la propuesta en `incoming/`; devuelve código 2 para indicar conflictos. Los cambios locales incluyen archivos borrados deliberadamente.

Para desarrollar los menús, editar `apps/wysun/` en este repositorio y ejecutar `./instalar.sh --orbit-only && orbit reload`. Así el escritorio usa el mismo código que recibirá una instalación nueva. Notas y Color son ventanas nativas independientes; sus datos privados se conservan aparte. [Flujo de desarrollo y actualización](docs/maintenance.md#cambiar-órbita-y-usar-la-misma-versión-en-tu-escritorio).

`restore` recupera el estado anterior y conserva ediciones posteriores en `changes-before-restore/`. Se deben restaurar los respaldos de más reciente a más antiguo. No desinstala paquetes APT/Flatpak ni borra datos personales de Wysun. Una instalación fallida muestra el ID recuperable y puede repetirse después de corregir la causa.

La configuración del escritorio y las fuentes viven en `~/.config` y `~/.local/share`; los comandos en `~/.local/bin`. Las herramientas conservan directorios por versión para permitir restaurar los enlaces activos. [Arquitectura y pruebas](docs/maintenance.md).

Ghostty: **Ctrl + Alt + Shift + flechas** ajusta los splits internos en pasos de 10 píxeles. Se oculta el indicador de dimensiones durante el ajuste. El redimensionado sigue siendo por pasos, sin interpolación animada.

## Versiones por proyecto con mise

Mise se instala con versión y SHA-256 fijados, y Zsh lo activa al abrir una terminal. Desde la raíz de un proyecto, `mise use node@24` o `mise use python@3.12` instala la versión elegida y la registra en `mise.toml`. Al entrar en esa carpeta se activa; al salir se recuperan las versiones del entorno anterior. `mise ls` muestra lo instalado y `mise use --global node@24` fija el valor predeterminado. Para scripts o tareas sin shell interactiva: `mise exec -- comando`.

La instalación inicial conserva el Node fijado del escritorio como alternativa cuando el proyecto no selecciona otra versión. NVM sigue disponible manualmente; evita alternar ambos gestores dentro de la misma shell. No se cambia el Python del sistema. Las instalaciones personales de lenguajes y sus preferencias globales no se copian al repositorio; comparte el `mise.toml` de cada proyecto.

## Privacidad y alcance

No incluye historial del portapapeles, notas, conexiones Wi-Fi, claves SSH, tokens, cachés ni proyectos personales. Cada usuario empieza con datos nuevos. No cambia Git global, contraseñas, particiones ni el gestor de acceso existente.

Esta versión está orientada a Wysun / Hyprland sobre Wayland y a las rutas XDG predeterminadas del usuario. No convierte otras distribuciones automáticamente. El soporte de Wi-Fi, Bluetooth, aceleración gráfica y pantallas depende de los controladores del equipo.

[Manual de Wysun](apps/wysun/README.md) · [Neovim](config/.config/nvim/README.md) · [Créditos](docs/credits.md) · [Validación](docs/validation.md)

En Ajustes → Tema (`wysun settings theme`) eliges un estilo —**Space Black** (variantes Space Black, Tokyo y Severance) o **Fluent** (claro y oscuro, tipo Windows 11)— y lo ves al instante en todas las aplicaciones, sin reinstalar el escritorio ([guía de temas](docs/themes.md)). El cambio incluye Wysun, terminal, prompt, Neovim, barra, bordes, notificaciones y animaciones del bloqueo; las configuraciones anteriores se respaldan.

### Herramientas personales

Un solo comando: `orbit-tools`, con grupos `dev`, `audit`, `share`, `cloud`, `vpn` y `resets`. Abre el panel gráfico con `orbit tools` o `orbit-tools gui`. `~/scripts` contiene únicamente el lanzador y su guía; el motor compartido vive en `apps/tools`. Actualiza la CLI con `./instalar.sh --scripts-only` y el panel con `./instalar.sh --orbit-only`. La migración respalda y reorganiza los datos privados. [Guía de uso y recuperación](docs/tools.md).

### Arranque y acceso

La selección completa incluye Blue CRT: GRUB azul clásico, carga animada e inicio de LightDM con Tux y biseles retro. Se actualizan por separado con `./instalar.sh --boot-only`; `--boot-components grub,plymouth` limita las pantallas. El instalador visual permite elegirlas y recuperar sus respaldos. [Instalación, compatibilidad y recuperación](docs/boot.md).
