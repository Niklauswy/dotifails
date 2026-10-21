# Mantenimiento

`home/` contiene únicamente configuración portable. `apps/wysun/` es la fuente de la aplicación, separada del estado del usuario. `assets/` guarda fuentes e iconos; `backgrounds/` contiene los fondos de Severance, Tokyo y Space Black. `manifests/themes.json` define sus perfiles visuales y verifica el paquete local de recursos de Severance.

`installer/` concentra la interfaz nativa y el motor de instalación. La selección, las dependencias y el plan se comparten entre interfaz y CLI; `manifests/packages.json` agrupa los paquetes por componente sin duplicar una lista monolítica de instalación completa. Consulta la [organización y el funcionamiento del instalador](installer.md). Usa `./instalar.sh --installer-only` para desplegar únicamente esta parte con respaldo.

`installer/main.py` usa Python estándar. Valida la distribución, instala paquetes con APT, verifica los SHA-256 antes de extraer artefactos y despliega cada entrada con un diario escrito antes del cambio. No sigue enlaces en directorios padre del destino. Se serializa mediante `flock`. Las configuraciones nuevas no pisan ediciones locales registradas desde la instalación anterior.

`manifests/artifacts.json` fija binarios y fuentes de shell; `config/.config/nvim/lazy-lock.json` fija plugins; `manifests/mason.json` y la copia `config/.config/nvim/mason-lock.json` deben coincidir. Para cambiar versiones, verificar la fuente oficial, descargar y comprobar los artefactos antes de actualizar sus sumas. No usar sumas inventadas ni un canal `latest` para herramientas fijadas.

Los servicios de escritorio registran PID e inicio del proceso y se separan por display X. El arranque no termina todos los procesos Polybar del usuario. El historial usa almacenamiento local separado de la aplicación instalada.

## Cambiar Wysun y usar la misma versión en tu escritorio

La fuente de los menús es `apps/wysun/` en este repositorio. Notas vive en `notes_window.py`, Color en `color_window.py` y el almacenamiento local en `utility_data.py`. No editar la antigua copia `~/proyects/orbit-desktop` ni la copia instalada.

Después de modificar y probar el código, desde la raíz del repositorio:

```sh
./instalar.sh --orbit-only && ~/.local/bin/orbit reload
```

Esto respalda y copia Wysun a `~/.local/share/orbit/app/`, actualiza el lanzador `~/.local/bin/orbit` y el gestor dotifails. No reinstala paquetes ni modifica Neovim, BSPWM, atajos o los datos privados. `reload` conserva las notas pendientes antes de reiniciar la aplicación; si hay un conflicto con una edición externa, muestra la nota y cancela la recarga. En una sesión anterior a esta versión, cerrar sesión una vez permite arrancar el ejecutable nuevo.

Para traer una versión publicada en otro equipo ya configurado:

```sh
dotifails update --orbit-only && orbit reload
```

La instalación completa utiliza exactamente el mismo `apps/wysun/`. Los atajos versionados en `config/.config/wysun/hyprland.lua` abren `wysun notes` y `wysun color`. Los cambios de atajos se distribuyen mediante la actualización completa de configuración, respetando los conflictos locales; `--orbit-only` no los sobrescribe.

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
cd apps/wysun
QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests/wysun_app -t tests
```

`tests/container-install.sh` prepara un usuario de prueba y ejecuta instalación, pruebas, repetición y verificaciones de Neovim en una imagen limpia. Se ejecuta dentro de un contenedor, nunca directamente en el equipo. No valida el arranque de un gestor gráfico, hardware Wi-Fi/Bluetooth ni GPU física; esas pruebas requieren una VM o equipo de prueba.

## Perfiles visuales

- `severance`: `backgrounds/azul.jpg`, GTK ARK-Dark, iconos Flat-Remix-Green-Dark y cursor Breeze. Los recursos se conservan con sus licencias en `assets/appearance/azul.tar.xz`; el instalador comprueba SHA-256 antes de extraerlos.
- `tokyo`: `backgrounds/tokyo.png`, GTK Arc-Darker, iconos Win11-Dark y cursor Fluent.
- `space-black`: `backgrounds/space-black.png`, GTK Arc-Darker, iconos Win11-Dark y cursor Fluent.
- Los tres coordinan los paneles, bordes, terminal, prompt, Neovim, barra y notificaciones mediante el motor de temas. Eza aporta los iconos de archivos y Bat mantiene su tema local y su caché.

Una instalación nueva selecciona Severance. Las actualizaciones conservan el tema de Ajustes; una instalación antigua sin perfil registrado conserva Tokyo. `azul` y `morado` siguen siendo alias de compatibilidad. Para seleccionar explícitamente:

```sh
./instalar.sh --theme severance
./instalar.sh --theme tokyo
./instalar.sh --theme space-black
```

En un equipo con todas las dependencias instaladas, `--config-only --theme severance` permite aplicar solo archivos y recursos. Cierra sesión después para cargar el perfil completo. Las ediciones locales siguen protegidas: si hay conflictos, revisar `incoming/` antes de considerar aplicado todo el perfil. `--orbit-only` conserva el perfil.

La instantánea azul conserva los ajustes visuales útiles, sin rutas del usuario ni cachés. La configuración antigua de Xsettings apuntaba a `Echo`, que no existía en el equipo: se usa el ARK-Dark indicado por GTK. Se omiten módulos GTK ausentes, opciones de ejemplo ignoradas y comandos de PowerShell rotos del prompt; se conservan sus módulos funcionales, símbolos y colores. El tema declarado de Bat no estaba instalado, por lo que se incluye uno local con la paleta de la terminal.
