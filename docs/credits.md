# Créditos y licencias

- BSPWM, SXHKD, Picom, Polybar, Ghostty, Neovim, NvChad, Starship y herramientas de lenguaje mantienen sus licencias originales. Se descargan desde sus proyectos o la distribución.
- [Lucide](https://github.com/lucide-icons/lucide): iconos SVG de la aplicación; licencia ISC en el directorio de recursos.
- [Win11 icon theme](https://github.com/yeyushengfan258/Win11-icon-theme): tema Win11-Dark, GPL-3.0, `assets/icons/Win11-Dark/COPYING`. Se ajustó la herencia a temas disponibles en Debian y se eliminaron enlaces rotos.
- [Fluent icon theme](https://github.com/vinceliuice/Fluent-icon-theme): cursor Fluent, GPL-3.0, `assets/icons/Fluent/COPYING`.
- [Inter](https://github.com/rsms/inter): SIL OFL, `assets/fonts/Inter/OFL.txt`.
- [Fira Code](https://github.com/tonsky/FiraCode) y [Nerd Fonts](https://github.com/ryanoasis/nerd-fonts): licencias y atribuciones en `assets/fonts/licenses/`.
- Noto Color Emoji, Arc y Papirus se instalan mediante APT, con sus licencias en los paquetes correspondientes.
- [mpv](https://mpv.io) (libmpv, LGPL-2.1+ en la compilación de Debian) y [FFmpeg](https://ffmpeg.org) reproducen y decodifican en Wysun Player, Files y Recorder; se enlazan de forma dinámica desde la distribución, sin copiar su código. El enlace ctypes de `apps/wysun/wysun_media/mpv.py` sigue la API pública documentada en `client.h` y `render.h`. Las formas «cookie» del reproductor de audio usan la misma receta que las del shell y Music.
- `backgrounds/purple-abstract-3840x3840-27445.jpg` conserva sin cambios el archivo elegido por el usuario; no se atribuye su autoría al instalador.

El diseño y la interacción de Wysun están inspirados en lanzadores como Raycast. No incluye código, extensiones ni servicios de Raycast.

- El tema local de Bat usa los mismos valores de color que la configuración de Ghostty; se incluye como configuración del proyecto.
