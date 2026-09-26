# Mantenimiento

`home/` contiene únicamente configuración portable. `apps/orbit/` es una copia del código de la aplicación, no del estado del usuario. `assets/` guarda fuentes e iconos; `backgrounds/` contiene exclusivamente el fondo seleccionado.

`installer/main.py` usa Python estándar. Valida la distribución, instala paquetes con APT, verifica los SHA-256 antes de extraer artefactos y despliega cada entrada con un diario escrito antes del cambio. No sigue enlaces en directorios padre del destino. Se serializa mediante `flock`. Las configuraciones nuevas no pisan ediciones locales registradas desde la instalación anterior.

`manifests/artifacts.json` fija binarios y fuentes de shell; `home/.config/nvim/lazy-lock.json` fija plugins; `manifests/mason.json` y la copia `home/.config/nvim/mason-lock.json` deben coincidir. Para cambiar versiones, verificar la fuente oficial, descargar y comprobar los artefactos antes de actualizar sus sumas. No usar sumas inventadas ni un canal `latest` para herramientas fijadas.

Los servicios de escritorio registran PID e inicio del proceso y se separan por display X. El arranque no termina todos los procesos Polybar del usuario. El historial usa almacenamiento local separado de la aplicación instalada.

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
