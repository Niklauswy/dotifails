# Créditos y licencias

- Hyprland, Ghostty, Neovim, NvChad, Starship y herramientas de lenguaje mantienen sus licencias originales. Se descargan desde sus proyectos o la distribución.
- [Lucide](https://github.com/lucide-icons/lucide): iconos SVG de la aplicación; licencia ISC en el directorio de recursos.
- [Win11 icon theme](https://github.com/yeyushengfan258/Win11-icon-theme): tema Win11-Dark, GPL-3.0, `assets/icons/Win11-Dark/COPYING`. Se ajustó la herencia a temas disponibles en Debian y se eliminaron enlaces rotos.
- [Fluent icon theme](https://github.com/vinceliuice/Fluent-icon-theme): cursor Fluent, GPL-3.0, `assets/icons/Fluent/COPYING`.
- [Google Sans Flex](https://fonts.google.com/specimen/Google+Sans+Flex) (interfaz) y [CaskaydiaCove Nerd Font](https://github.com/ryanoasis/nerd-fonts) (monoespaciada; Cascadia Code con los glifos de Nerd Fonts): SIL OFL 1.1 y MIT, textos en `LICENSES/` y detalles en `THIRD_PARTY.md`. El instalador las copia con sus licencias en `~/.local/share/fonts/wysun`.
- Noto Color Emoji, Arc y Papirus se instalan mediante APT, con sus licencias en los paquetes correspondientes.
- [mpv](https://mpv.io) (libmpv, LGPL-2.1+ en la compilación de Debian) y [FFmpeg](https://ffmpeg.org) reproducen y decodifican en Wysun Player y Files, y FFmpeg graba y codifica en Recorder; se enlazan de forma dinámica desde la distribución, sin copiar su código. El enlace ctypes de `apps/python/wysun_media/mpv.py` sigue la API pública documentada en `client.h` y `render.h`. Las formas «cookie» del reproductor de audio usan la misma receta que las del shell y Music.
- `assets/backgrounds/purple-abstract-3840x3840-27445.jpg` conserva sin cambios el archivo elegido por el usuario; no se atribuye su autoría al instalador.

El diseño y la interacción de Wysun están inspirados en lanzadores como Raycast. No incluye código, extensiones ni servicios de Raycast.

- El tema local de Bat usa los mismos valores de color que la configuración de Ghostty; se incluye como configuración del proyecto.
