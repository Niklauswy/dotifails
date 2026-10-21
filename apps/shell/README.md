# Wysun Shell

Barra, dashboard, lanzador, menús, notificaciones, sesión y bloqueo de Wysun, escritos en QML sobre **Quickshell** con un plugin C++ propio
(`plugin/`, módulos QML `Wysun.*`). Es una adaptación modificada de un shell GPL-3.0 de terceros; los créditos, la licencia
(`LICENSE`) y la procedencia por archivo (`UPSTREAM.json`) se conservan. Detalle legal en [`THIRD_PARTY.md`](../../THIRD_PARTY.md).

## Estructura

| Ruta | Contenido |
|---|---|
| `shell.qml` | Raíz: fondo, `Drawers` (barra, paneles, popouts), selector de área, puente Wysun, demonios |
| `modules/` | `bar`, `dashboard`, `launcher`, `lock`, `nexus` (ajustes del shell), `notifications`, `osd`, `session`, `sidebar`, `utilities`, `windowinfo`, `drawers`, `background`, `areapicker` |
| `services/` | Singletons QML (audio, red, hypr, notificaciones, colores, sistema…) |
| `components/`, `utils/` | Controles, animaciones y utilidades compartidas |
| `daemons/` | `BatteryMonitor`, `IdleInhibit`, `Shortcuts` (atajos globales; no se carga todavía) |
| `plugin/` | Plugin C++/QML `Wysun.*` (Config, Services, Components, Models, Blobs, Images, I18n, Multimedia, Settings, State, Shaders) |
| `extras/` | Pequeño ejecutable `version` |
| `wysun/` | Puente con las apps Qt: `WysunBridge.qml` (IPC `wysunShell`), `backend.py`, `runtime.sh` |
| `assets/` | Fuentes (Material Symbols, Google Sans Flex), PAM y recursos |

## Runtime

El shell no usa el Qt ni el Quickshell del sistema. `installer/runtime_build.py` construye un runtime privado en
`$XDG_DATA_HOME/wysun/runtime` (Qt 6.9.3 de aqtinstall, Quickshell fijado, libcava, M3Shapes y este plugin; versiones en
`manifests/runtime.json`). `wysun/runtime.sh` lo arranca con `QML_IMPORT_PATH` apuntando a `runtime/shell/lib/qt6/qml` y
`runtime/deps/lib/qt6/qml`. Ver [`ARCHITECTURE.md`](../../ARCHITECTURE.md).

```sh
python3 installer/runtime_build.py            # idempotente; solo recompila lo que cambió
bin/wysun-shell                               # arranca el shell
bin/wysun-shell open dashboard | launcher | menu | quicksettings | notifications | windows | session
bin/wysun-shell status                        # JSON: pantallas, superficies abiertas, esquema
```

## Configuración y estado

- Configuración del usuario: `~/.config/wysun/shell/shell.json` (y `shell-tokens.json`, `monitors/<salida>/…` por pantalla).
- Esquema de color: `~/.local/state/wysun/scheme.json` (lo escribe `wysun scheme`).
- Capas de Layer Shell con espacio de nombres `wysun-*` (las reglas de Hyprland usan `^wysun-.*$`).

## Compatibilidad con Qt 6.9

`StyledSpinBox` implementa su propio `DoubleSpinBox`; `Elevation` acepta radios por esquina pero usa un único radio; el plugin
incluye `<ranges>` explícito y `QJsonObject` sin `asKeyValueRange`.
