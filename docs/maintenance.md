# Mantenimiento

`home/` contiene únicamente configuración portable. `apps/orbit/` es una copia del código de la aplicación, no del estado del usuario. `assets/` guarda fuentes e iconos; `backgrounds/` contiene exclusivamente los fondos azul y morado conservados. `manifests/themes.json` define sus perfiles visuales y verifica el paquete local de recursos del azul.

`installer/main.py` usa Python estándar. Valida la distribución, instala paquetes con APT, verifica los SHA-256 antes de extraer artefactos y despliega cada entrada con un diario escrito antes del cambio. No sigue enlaces en directorios padre del destino. Se serializa mediante `flock`. Las configuraciones nuevas no pisan ediciones locales registradas desde la instalación anterior.

`manifests/artifacts.json` fija binarios y fuentes de shell; `home/.config/nvim/lazy-lock.json` fija plugins; `manifests/mason.json` y la copia `home/.config/nvim/mason-lock.json` deben coincidir. Para cambiar versiones, verificar la fuente oficial, descargar y comprobar los artefactos antes de actualizar sus sumas. No usar sumas inventadas ni un canal `latest` para herramientas fijadas.

Los servicios de escritorio registran PID e inicio del proceso y se separan por display X. El arranque no termina todos los procesos Polybar del usuario. El historial usa almacenamiento local separado de la aplicación instalada.

## Cambiar Órbita y usar la misma versión en tu escritorio

La fuente de los menús es `apps/orbit/` en este repositorio. Notas vive en `notes_window.py`, Color en `color_window.py` y el almacenamiento local en `utility_data.py`. No editar la antigua copia `~/proyects/orbit-desktop` ni la copia instalada.

Después de modificar y probar el código, desde la raíz del repositorio:

```sh
./instalar.sh --orbit-only && ~/.local/bin/orbit reload
```

Esto respalda y copia Órbita a `~/.local/share/orbit/app/`, actualiza el lanzador `~/.local/bin/orbit` y el gestor dotifails. No reinstala paquetes ni modifica Neovim, BSPWM, atajos o los datos privados. `reload` conserva las notas pendientes antes de reiniciar la aplicación; si hay un conflicto con una edición externa, muestra la nota y cancela la recarga. En una sesión anterior a esta versión, cerrar sesión una vez permite arrancar el ejecutable nuevo.

Para traer una versión publicada en otro equipo ya configurado:

```sh
dotifails update --orbit-only && orbit reload
```

La instalación completa utiliza exactamente el mismo `apps/orbit/`. Los atajos versionados en `home/.config/sxhkd/sxhkdrc` abren `orbit notes` y `orbit color`. Los cambios de atajos se distribuyen mediante la actualización completa de configuración, respetando los conflictos locales; `--orbit-only` no los sobrescribe.

Notas importa una vez el antiguo `~/Documents/QuickNotes/notes.md`, conservando el archivo original. Color importa el historial antiguo de colores únicamente cuando aún no existe su almacenamiento nuevo. Esos datos permanecen en el hogar del usuario y nunca se copian al repositorio.

## Pruebas locales

```sh
python3 -m unittest discover -s tests -v
QT_QPA_PLATFORM=offscreen python3 tests/utility_ui.py
./instalar.sh --config-only --target-home /tmp/orbita-test
./instalar.sh --config-only --target-home /tmp/orbita-test
```

`--config-only` no necesita sudo ni red y no instala dependencias o sesión. `--skip-nvim-tools` permite repetir el resto del instalador sin reinstalar LSP y depuradores.

Las pruebas completas de la aplicación requieren `python3-pyside6.qttest`, además de las dependencias de escritorio:

```sh
cd apps/orbit
QT_QPA_PLATFORM=offscreen python3 -m unittest test_orbit test_v2 test_v3 test_v4 test_settings_hub test_bar_visibility
```

`tests/container-install.sh` prepara un usuario de prueba y ejecuta instalación, pruebas, repetición y verificaciones de Neovim en una imagen limpia. Se ejecuta dentro de un contenedor, nunca directamente en el equipo. No valida el arranque de un gestor gráfico, hardware Wi-Fi/Bluetooth ni GPU física; esas pruebas requieren una VM o equipo de prueba.

## Perfiles visuales conservados

- `azul`: el fondo original `macos2.jpg`, guardado como `backgrounds/azul.jpg`, GTK ARK-Dark, iconos Flat-Remix-Green-Dark, cursor Breeze, ajustes GTK 4 y el prompt actual de Starship. Sus recursos se conservan con sus licencias en `assets/appearance/azul.tar.xz`; el instalador comprueba SHA-256 y los extrae con el filtro seguro de Python.
- `morado`: `backgrounds/tokyo.png`, GTK Arc-Darker, iconos Win11-Dark, cursor Fluent y el prompt compacto anterior del repositorio.
- Ambos comparten el escritorio Órbita, la barra, notificaciones, transparencia, paleta Tokyo de Ghostty, configuración de Neovim y herramientas de terminal. Los iconos de archivos usan Eza; Bat dispone de un tema local `tokyonight_night` y el instalador construye su caché.

Una instalación nueva selecciona azul. Una instalación administrada anterior sin perfil registrado conserva morado. Para seleccionar explícitamente:

```sh
./instalar.sh --theme azul
./instalar.sh --theme morado
```

En un equipo con todas las dependencias instaladas, `--config-only --theme azul` permite aplicar solo archivos y recursos. Cierra sesión después para cargar el perfil completo. Las ediciones locales siguen protegidas: si hay conflictos, revisar `incoming/` antes de considerar aplicado todo el perfil. `--orbit-only` conserva el perfil.

La instantánea azul conserva los ajustes visuales útiles, sin rutas del usuario ni cachés. La configuración antigua de Xsettings apuntaba a `Echo`, que no existía en el equipo: se usa el ARK-Dark indicado por GTK. Se omiten módulos GTK ausentes, opciones de ejemplo ignoradas y comandos de PowerShell rotos del prompt; se conservan sus módulos funcionales, símbolos y colores. El tema declarado de Bat no estaba instalado, por lo que se incluye uno local con la paleta de la terminal.
