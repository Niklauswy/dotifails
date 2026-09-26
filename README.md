# Órbita Desktop · dotifails

El escritorio BSPWM actual, preparado para instalarse en **Parrot 7 o Debian 13, x86_64**: Órbita, Picom, Polybar, Ghostty, Neovim y Zsh. Mantiene los atajos, transparencias y animaciones rápidas. Conserva dos perfiles completos: **azul actual** (`backgrounds/azul.jpg`) y **morado original** (`backgrounds/tokyo.png`).

## Instalar

Desde una cuenta normal con acceso a `sudo`, conexión a Internet y varios GB libres:

```sh
sudo apt-get update && sudo apt-get install --yes git python3 ca-certificates && git clone --depth 1 https://github.com/Niklauswy/dotifails.git && cd dotifails && ./instalar.sh
```

Si ya tienes esta carpeta, basta con `./instalar.sh`. Una instalación nueva utiliza el perfil azul; para el morado usa `./instalar.sh --theme morado`. Las actualizaciones conservan el perfil elegido. No lo ejecutes con `sudo`: el instalador lo solicita únicamente para paquetes y registro de sesión. Al terminar, cierra sesión y elige **Órbita / BSPWM** en el gestor de acceso. No cierra tu sesión ni reinicia el equipo.

El instalador se valida en contenedores Debian y Parrot con una sesión X11 aislada. Consulta el alcance exacto en [Validación](docs/validation.md).

```sh
./instalar.sh --dry-run
./instalar.sh --extras brave,discord,obsidian
./instalar.sh --profile samsung-touchscreen
```

El perfil Samsung es opcional y específico del equipo con pantalla táctil defectuosa. No se aplica a otras instalaciones. Las aplicaciones opcionales se instalan desde Flathub para el usuario; también puedes instalar solo una, por ejemplo `--extras obsidian`.

## Qué incluye

- BSPWM y SXHKD, monitores detectados, diez escritorios distribuidos, sesiones con D-Bus y agente Polkit.
- Picom 12, transparencias y animaciones; Polybar flotante, módulos de recursos, conexiones, audio, calendario y notificaciones. La barra se oculta en el monitor que muestra una ventana a pantalla completa.
- Órbita nativa en Qt: aplicaciones, ventanas, portapapeles, OCR local en español/inglés, archivos con vistas previas, reproductor multimedia, snippets, calculadora y emojis a color.
- Conexiones Wi-Fi, Bluetooth, VPN y SSH; menú de sesión; ajustes visuales de BSPWM, pantallas, barra y atajos.
- Notas Markdown, procesos y selector de color con lupa. No requiere Rofi.
- Ghostty **1.2.3**, Neovim **0.11.5**, Node **24.19.0**, Starship **1.24.1**; versiones y SHA-256 en `manifests/artifacts.json`. Ghostty se extrae una vez, sin depender de FUSE al abrir terminales.
- NvChad con plugins fijados por `lazy-lock.json`, LSP, formato, búsqueda difusa, tareas, depuración y herramientas de JS/TS, C/C++ y Python. Las versiones de Mason están en `manifests/mason.json`.
- Zsh, autocompletado/sugerencias, resaltado, fzf y prompt Starship. NVM se carga al invocar `nvm`; Node está disponible directamente.
- Perfil azul: ARK-Dark, Flat-Remix-Green-Dark, cursor Breeze y el prompt actual de Starship. Perfil morado: Arc-Darker, Win11-Dark, cursor Fluent y el prompt compacto.
- Ambos mantienen la barra, notificaciones, paleta de Ghostty, Neovim, FiraCode Nerd Font, Inter, Noto Color Emoji, `eza`, `bat` y FZF. Los dos fondos quedan en la biblioteca de Órbita.

Los paquetes APT y las aplicaciones Flatpak reciben las versiones que publica cada distribución. Los binarios externos y plugins tienen versiones fijadas; los paquetes del sistema no forman una imagen inmutable.

## Atajos principales

| Teclas | Acción |
| --- | --- |
| Super + Enter | Terminal |
| Super + Espacio / D | Órbita |
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

Ver todos en [sxhkdrc](home/.config/sxhkd/sxhkdrc). Los paneles tienen navegación por teclado y Escape para cerrar.

## Actualizar y recuperar

```sh
dotifails doctor
dotifails update
dotifails update --source /ruta/dotifails
dotifails update --orbit-only && orbit reload
dotifails restore
dotifails restore ID_DEL_RESPALDO
```

Las configuraciones se instalan como **copias** editables. Antes de reemplazarlas se guardan en `~/.local/state/dotifails/backups/ID/before/`, junto con un diario de operaciones. Si has editado un archivo administrado, una actualización lo conserva y deja la propuesta en `incoming/`; devuelve código 2 para indicar conflictos. Los cambios locales incluyen archivos borrados deliberadamente.

Para desarrollar los menús, editar `apps/orbit/` en este repositorio y ejecutar `./instalar.sh --orbit-only && orbit reload`. Así el escritorio usa el mismo código que recibirá una instalación nueva. Notas y Color son ventanas nativas independientes; sus datos privados se conservan aparte. [Flujo de desarrollo y actualización](docs/maintenance.md#cambiar-órbita-y-usar-la-misma-versión-en-tu-escritorio).

`restore` recupera el estado anterior y conserva ediciones posteriores en `changes-before-restore/`. Se deben restaurar los respaldos de más reciente a más antiguo. No desinstala paquetes APT/Flatpak ni borra datos personales de Órbita. Una instalación fallida muestra el ID recuperable y puede repetirse después de corregir la causa.

La configuración del escritorio y las fuentes viven en `~/.config` y `~/.local/share`; los comandos en `~/.local/bin`. Las herramientas conservan directorios por versión para permitir restaurar los enlaces activos. [Arquitectura y pruebas](docs/maintenance.md).

## Privacidad y alcance

No incluye historial del portapapeles, notas, conexiones Wi-Fi, claves SSH, tokens, cachés ni proyectos personales. Cada usuario empieza con datos nuevos. No cambia Git global, contraseñas, particiones ni el gestor de acceso existente. Instala LightDM si no encuentra uno.

Esta versión está orientada a Linux X11 y rutas XDG predeterminadas del usuario. No migra a Wayland ni convierte otras distribuciones automáticamente. El soporte de Wi-Fi, Bluetooth, aceleración gráfica y pantallas depende de los controladores del equipo.

[Manual de Órbita](apps/orbit/README.md) · [Neovim](home/.config/nvim/README.md) · [Créditos](docs/credits.md) · [Validación](docs/validation.md)
