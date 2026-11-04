# Mantenimiento

`config/` contiene únicamente configuración portable. `apps/python/` es la fuente de la aplicación, separada del estado del usuario. `assets/` guarda iconos, cursores y el wallpaper por defecto (`assets/backgrounds/`); las fuentes van con `wysun_core/fonts` y el shell. No hay temas fijos: ver [themes.md](themes.md).

`installer/` concentra el motor de instalación, las herramientas de arranque y el registro de la sesión. `manifests/packages.json` agrupa los paquetes por componente sin duplicar una lista monolítica de instalación completa. Consulta la [organización y el funcionamiento del instalador](installer.md).

`installer/main.py` usa Python estándar. Valida la distribución, instala paquetes con APT, verifica los SHA-256 antes de extraer artefactos y despliega cada entrada con un diario escrito antes del cambio. No sigue enlaces en directorios padre del destino. Se serializa mediante `flock`. Las configuraciones nuevas no pisan ediciones locales registradas desde la instalación anterior.

`manifests/artifacts.json` fija binarios y fuentes de shell; `config/.config/nvim/lazy-lock.json` fija plugins; `manifests/mason.json` y la copia `config/.config/nvim/mason-lock.json` deben coincidir. Para cambiar versiones, verificar la fuente oficial, descargar y comprobar los artefactos antes de actualizar sus sumas. No usar sumas inventadas ni un canal `latest` para herramientas fijadas.

El historial usa almacenamiento local separado de la aplicación instalada.

## Cambiar Wysun y usar la misma versión en tu escritorio

La fuente de las apps Qt es `apps/python/` en este repositorio. Color es un panel del shell (`apps/shell/modules/colors/`) y su almacenamiento local vive en `wysun_services/utility_data.py`. No editar la copia instalada.

Después de modificar y probar el código, haz commit y `git push` desde la raíz del repositorio, y despliega con:

```sh
wysun update
```

`wysun update` hace `git pull --ff-only` en la copia fuente registrada y vuelve a aplicar código, aplicaciones, configuración, atajos y lanzador; ejecuta `wysun reload` y reinicia solo el shell si cambió `apps/shell`. No pide `sudo` salvo que hayan cambiado los paquetes, el runtime, las herramientas de Neovim, el arranque o el registro de la sesión. `reload` conserva las notas pendientes antes de reiniciar la aplicación; si hay un conflicto con una edición externa, muestra la nota y cancela la recarga. En una sesión anterior a esta versión, cerrar sesión una vez permite arrancar el ejecutable nuevo.

Para traer una versión publicada en otro equipo ya configurado, ejecuta `wysun update` (o usa el aviso de la barra).

La instalación completa utiliza exactamente el mismo `apps/python/`. Los atajos versionados en `config/.config/wysun/hyprland.lua` usan las órdenes de `wysun` (`wysun --help`). `wysun update` aplica los cambios de atajos respetando los conflictos locales.

Los datos de Notas y Colores permanecen en el hogar del usuario y nunca se copian al repositorio.

## Pruebas locales

```sh
python3 -m unittest discover -s tests -v
QT_QPA_PLATFORM=offscreen python3 tests/utility_ui.py
```

Las pruebas completas de la aplicación requieren `python3-pyside6.qttest`, además de las dependencias de escritorio:

```sh
cd apps/python
QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests/wysun_app -t tests
```

`tests/container-install.sh` prepara un usuario de prueba y ejecuta instalación, pruebas, repetición y verificaciones de Neovim en una imagen limpia. Se ejecuta dentro de un contenedor, nunca directamente en el equipo. No valida el arranque de un gestor gráfico, hardware Wi-Fi/Bluetooth ni GPU física; esas pruebas requieren una VM o equipo de prueba.

## Perfil visual

Hay un solo perfil, Material You: fondo `backgrounds/purple-abstract-3840x3840-27445.jpg`, GTK Arc-Darker, iconos Win11-Dark y cursor Fluent (`manifests/themes.json`). Los colores salen del wallpaper y coordinan los paneles, bordes, terminal, prompt, Neovim, barra y notificaciones mediante el motor de temas. Eza aporta los iconos de archivos y Bat mantiene su tema local y su caché.

Una instalación nueva queda en modo automático. Las actualizaciones conservan el modo y el wallpaper del usuario, y leen el modo de cualquier `theme.json` antiguo. Ya no existe `--theme`. En un equipo con todas las dependencias instaladas, `wysun update` aplica solo los archivos y recursos que cambiaron. Cierra sesión después para cargar el perfil completo. Las ediciones locales siguen protegidas: si hay conflictos, revisar `incoming/` antes de considerar aplicado todo el perfil. `wysun update` conserva el perfil.

La instantánea visual conserva los ajustes útiles, sin rutas del usuario ni cachés. La configuración antigua de Xsettings apuntaba a `Echo`, que no existía en el equipo: se usa el tema GTK indicado. Se omiten módulos GTK ausentes, opciones de ejemplo ignoradas y comandos de PowerShell rotos del prompt; se conservan sus módulos funcionales, símbolos y colores. El tema declarado de Bat no estaba instalado, por lo que se incluye uno local con la paleta de la terminal.
