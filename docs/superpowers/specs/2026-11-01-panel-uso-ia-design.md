# Panel de uso de IA, segunda versión — diseño

Fecha: 2026-11-01. Estado: pendiente de aprobación.
Maqueta interactiva de referencia (datos falsos): `docs/superpowers/specs/2026-11-01-panel-uso-ia-maqueta.html`.

## Por qué

El panel actual (`apps/shell/modules/aiusage`, servicio `services/AiUsage.qml`) funciona, pero se ve amontonado:
rejilla de tarjetas de dos columnas, pestañas por cuenta que se cortan con cinco cuentas («navarr…», «masha…»), cajas
dentro de cajas y poca información útil para decidir («¿empiezo esta tarea larga o espero al reinicio?»).
El usuario lo compara con CodexBar (github.com/steipete/CodexBar, MIT) y quiere su orden visual y su riqueza de datos y
funciones, pero como un panel más de Wysun: mismo tema Material You, mismos tokens, mismo comportamiento que los demás
paneles.

Éxito = al abrir el panel se entiende de un vistazo cuánto queda de cada límite, si al ritmo actual alcanza hasta el
reinicio, qué está corriendo ahora y cuánto cuesta; y se ve tan integrado como el resto del shell.

## Objetivos

1. Rehacer la disposición siguiendo a CodexBar: pestañas por **proveedor**, chips por **cuenta**, secciones separadas por
   líneas finas en lugar de tarjetas, subpantallas para el detalle.
2. Añadir los datos y funciones de CodexBar que aplican (lista en «Contenido»).
3. Añadir las cinco funciones extra elegidas: sesiones de agentes activas, seguir la app enfocada, refresco adaptativo,
   espacio en disco, indicador atenuado con datos viejos.
4. Ocultar cuentas: una cuenta oculta no cuenta para nada.
5. Añadir cuenta / iniciar sesión desde el panel, con el login del propio proveedor.
6. Proveedor nuevo **OpenCode** (suscripción OpenCode Go, que el usuario va a usar con DeepSeek).
7. Ajustes del panel dentro del propio panel.

## No objetivos

- Más proveedores activos: el usuario hoy solo usa Claude, Codex y (pronto) OpenCode. Gemini, Cursor y Copilot aparecen
  en Ajustes solo si se pueden soportar sin credenciales; si no, no aparecen (ver «Proveedores»).
- Lo que CodexBar tiene por ser app de macOS o multi-proveedor masivo: widgets, Homebrew/Sparkle, llavero, editor de
  diseño del icono por tokens, Admin API de organizaciones, más de cien proveedores de API, exportar CSV/imagen, CLI JSON.
- Extras de la web de Codex (requieren cookies de chatgpt.com y un navegador oculto).
- Nombres propios para cuentas (descartado; las etiquetas existentes de `ai-accounts.json` siguen funcionando).
- Borrar archivos: el panel de espacio en disco solo mide y sugiere.

## Anti-objetivos (fracaso aunque funcione)

- Colores, radios, espaciados, tipografías o duraciones literales; que no cambie en vivo con el wallpaper o el modo
  claro/oscuro/auto. `tests/test_theme_literals.py` debe seguir pasando.
- Que una credencial termine escrita, registrada, cacheada o enviada a un host que no sea el oficial; leer cookies del
  navegador.
- Que el panel se trabe o tarde en abrir: la primera pintura sigue saliendo de la instantánea en caché.
- Romper lo que ya funciona: descubrimiento automático de cuentas de Claude por el hook de statusline, cuentas de Codex
  de solo historial, reparto de tokens por cuenta, avisos por `notify-send`, atajos de teclado, apertura por la esquina.

## Restricciones

- Todo lo de `AGENTS.md`: tokens de `wysun_core/tokens.json` (esquema 3) y `Colours.palette`; excepciones solo con
  `theme-exception: motivo` (los colores semánticos de estado sí son excepción declarada si no hay token: éxito,
  aviso, error usan `m3error`, `m3success`… si existen; consultar `docs/themes.md`).
- Ancho del panel: el token actual `Tokens.sizes.aiUsage.width` (580). Alto: el que permita la pantalla, con scroll
  interno como hoy (`maxHeight`).
- El panel sigue apareciendo por la esquina superior derecha, con `wysun ai` / `wysun-shell toggle ai`, el indicador
  de la barra y la misma toma de teclado (`HyprlandFocusGrab`).
- Textos con `Tr.tr` (el shell es multilingüe); la maqueta está en español solo como referencia de contenido.
- Despliegue según `AGENTS.md` (`./instalar.sh --wysun-only`, reiniciar solo el shell, comprobar la apertura real).
- Una sola compilación/suite a la vez (equipo con poca memoria).

## Privacidad y fuentes de datos

Regla nueva (aprobada por el usuario el 2026-11-01, ya en `AGENTS.md`): la antigua «`backend.py` no lee
credenciales» se sustituye por **«lee credenciales solo cuando mejoran una función y no añaden riesgo»**, con estas
protecciones obligatorias, que también se documentan en `ARCHITECTURE.md` y en el docstring de `backend.py`:

- Se leen justo antes de la petición y solo para consultar los datos del propio usuario a su proveedor.
- Viajan solo por HTTPS al host oficial (`api.anthropic.com`, `opencode.ai`…); nunca a otro.
- Nunca se escriben, renuevan, reescriben, registran, cachean ni aparecen en la instantánea, la caché, avisos, el texto
  de «Copiar resumen», errores o salida del backend. Si un token está caducado, no se renueva: la cuenta muestra
  «abre Claude Code / OpenCode para renovar la sesión» y cae a la fuente sin credenciales.
- Prueba obligatoria: con HOME temporal y credenciales sintéticas con un valor centinela, ningún archivo escrito ni la
  salida del backend contienen el centinela; y la petición solo va al host esperado.
- Cookies del navegador: no (se mantiene fuera la función 6 de extras web de Codex).
- El agente que implemente no abre ni imprime los archivos de credenciales reales; solo usa los sintéticos.

Credenciales que se leen:

- **Claude**: `<home>/.credentials.json` de cada home de Claude (por defecto `~/.claude/.credentials.json`), token OAuth
  de Claude Code, para `GET https://api.anthropic.com/api/oauth/usage` (cabeceras `Authorization: Bearer`,
  `anthropic-beta: oauth-2025-04-20`; mapeo y reintentos según `docs/claude.md` de CodexBar). Requiere el alcance
  `user:profile`; si falta, se sigue con la statusline. La statusline queda como respaldo y para repartir sesiones.
- **OpenCode**: el login de la CLI (`~/.local/share/opencode/opencode.db`, credenciales v2, o `auth.json` antiguo) para
  la API de uso de OpenCode Go.
- **Codex**: nada nuevo; `codex app-server` ya usa su propia sesión.

Fuentes por proveedor:

| Proveedor | Límites en vivo | Historial (tokens/coste) | Notas |
|---|---|---|---|
| Claude | API OAuth de uso (nuevo, con el token); respaldo: `rate_limits` del hook de statusline | logs `projects/*.jsonl` (sin cambios) | Plan desde `oauthAccount`; uso extra, créditos en la nube, reinicios guardados y semanales por modelo desde la API OAuth. |
| Codex | `codex app-server` (`account/read`, `account/rateLimits/read`) | logs `sessions/` (sin cambios) | Reinicios guardados y, si la respuesta lo trae, saldo de créditos. |
| OpenCode | API de uso de OpenCode Go con el login de la CLI (excepción) | `opencode.db`, solo mensajes (`message`, `session_message`) | Ventanas 5 h, semanal y mensual cuando haya suscripción. |
| Estado de servicios | `status.anthropic.com`, `status.openai.com`, estado de opencode si existe: JSON público de Statuspage (`/api/v2/summary.json`) | — | Sin credenciales. |

Con el token, Claude tiene **uso extra** (gasto/tope mensual; reinicio inferido el día 1 a medianoche UTC, como
CodexBar), **créditos de sesiones en la nube** y **reinicios guardados**. La **fecha de renovación del plan** solo se
muestra si la API la devuelve. Todas estas filas se pintan solo si hay datos. Para Codex: reinicios guardados (ya hoy),
créditos si `account/rateLimits/read` los devuelve; fecha de renovación no (solo saldría de la web con cookies).

**Aviso de sesión por caducar (función 9, recuperada al permitirse credenciales; decisión de Claude, revisable).**
Con la fecha de caducidad que traen los propios archivos de credenciales (sin enviarlos a ningún sitio), la cuenta
muestra un aviso y se manda una notificación cuando su login caduca en menos de 24 h o ya caducó y Claude Code /
OpenCode no lo ha renovado, con el comando para volver a entrar. Una vez por caducidad (claves en `alerts.json`).

OpenCode sin suscripción todavía: la pestaña existe si hay historial local o login; muestra historial (lo usado con
DeepSeek y modelos gratuitos), sesiones activas y un aviso «Sin suscripción OpenCode Go» con botones para iniciar
sesión (abre `opencode auth login` en una terminal) y para ver los planes (abre la web). Las barras aparecen solas al
haber suscripción. El uso viejo de OpenAI y Copilot hecho desde OpenCode se queda en el historial de OpenCode, sin
asignarlo a cuentas de Codex/Copilot (no se sabe de cuál vino).

## Estructura del panel (decidida; ver maqueta)

Cabecera: título «Uso de IA», estado de actualización («Actualizado 17:24 · agente activo, cada 1 min», o «1 cuenta con
error» en color de aviso), botón refrescar, botón ajustes.

Pestañas (segmentadas, una fila): **Resumen** + una por **proveedor** activo con al menos una cuenta visible. Cada
pestaña: logotipo, nombre, minimedidor del límite más ajustado del proveedor (color por severidad), punto de
incidencia/agotado, número del atajo Alt+N.

Debajo, en una pestaña de proveedor con más de una cuenta visible: **chips de cuenta** (anillo con lo usado del límite
más ajustado, etiqueta, plan) y un chip «+ Añadir».

### Página de cuenta (de arriba abajo)

1. Avisos en línea cuando apliquen: incidencia del servicio (resumen + estado por componente + antigüedad), error de
   lectura de esa cuenta (texto, comando sugerido en monoespaciado y botón copiar), reinicio cercano con cuota sin
   usar (semanal a menos de 24 h con cuota libre).
2. Identidad: logotipo, proveedor, correo (o «••••@dominio» si ocultar datos personales), antigüedad del dato, chip
   de plan.
3. Un bloque por límite (Sesión, Semanal, semanales por modelo como Opus; para OpenCode 5 h / semanal / mensual):
   nombre + ventana, «N % usado» (o «libre» según ajuste), barra con marca de uso parejo, «N % libre» y «Se reinicia en
   …» / «Se reinicia jue 13:24», y línea de ritmo: píldora «X % en reserva» / «X % en déficit» / «Al ritmo» /
   «Agotado» + «Llega al reinicio» / «Se agota en …». El ritmo se oculta si ha pasado menos del 3 % de la ventana
   (regla de CodexBar). Tocar un bloque abre su **historial del límite**.
4. Filas de facturación/créditos, solo si hay datos (ver fuentes): uso extra con objetivo diario, créditos en la nube,
   saldo de créditos con acción «Comprar…» (abre la web), reinicios guardados con caducidad y acción «Canjear» (abre la
   web; canjear queda en las herramientas del proveedor, como hoy), renovación del plan.
5. Coste: hoy y últimos 30 días (tokens + $ estimado a precio de API) y minigráfica de 14 días; tocar abre **Coste**.
6. Sesiones activas de ese proveedor (ver abajo).
7. Menú: Espacio en disco ›, Panel de uso (web del proveedor), Estado del servicio (punto + texto + antigüedad),
   Copiar resumen (texto al portapapeles).

### Historial del límite (subpantalla)

Curva de lo que queda en la ventana actual a partir de **instantáneas registradas** (cada refresco guarda
`(tiempo, % usado)` por cuenta y límite), línea discontinua de uso parejo (si el ajuste está activo), proyección al
ritmo actual hasta el reinicio o hasta agotarse, punto «ahora», ejes con inicio/reinicio. Debajo, recuadro con la
conclusión («Vas 22 % por debajo del uso parejo…») y **ventanas anteriores** (actual, anterior, hace 2, hace 3): %
usado al cerrar (o «agotado el sáb 14:20») y coste de cada ventana partiendo el historial en cada reinicio.
Las instantáneas son nuevas: se guardan en `~/.local/state/wysun/ai-usage/` con tope de retención (≈ 90 días) y
mientras no hay suficientes la curva se ve parcial y lo dice.

### Coste (subpantalla)

Selector Coste/Tokens. Pestañas: **Diario** (total, media, 7/30/90 días, barras apiladas por modelo, inspector bajo la
gráfica al pasar por un día, tocar un día → mismo gráfico por horas con su zona horaria, reparto por modelo y por
proyecto), **Por ventana** (coste partido en cada reinicio semanal), **Actividad** (mapa de calor anual de tokens con
racha, día de más uso y días activos) y **Libro** (lista diaria, 14 días y «Mostrar todo»; «~» cuando un día tiene
modelos sin precio). El backend ya agrega por hora (`_iso_hour`); hace falta ampliar el rango a 365 días para
Actividad.

### Resumen

Arriba: gasto de hoy y de 30 días de las cuentas visibles. Luego **sesiones activas** de todos los proveedores. Luego,
agrupado por proveedor (cabecera con logotipo y punto de estado), una fila por cuenta visible: logotipo, etiqueta,
plan, y dos barras (sesión y semanal) con % y tiempo al reinicio; en modo compacto una sola barra, la más ajustada.
Tocar una fila abre esa cuenta. Al pie: Añadir cuenta…, Ajustes.

### Ajustes (subpantalla del panel)

- **Proveedores**: interruptor por proveedor con su fuente y punto de estado. Por proveedor, lista de sus **cuentas**
  con interruptor «Mostrar» (ocultar cuentas).
- **Indicador en la barra**: estilo (Barras: dos barras sesión/semanal por proveedor; Icono + %; Apilado S/W;
  Ritmo ±%) y qué sigue (App enfocada / Más ajustado / Seleccionado).
- **Mostrar**: lo usado o lo libre; hora exacta del reinicio o cuenta atrás; guía de uso parejo; días de trabajo para
  el ritmo (Automático, 5, 6, 7); uso extra/créditos/facturación; resumen compacto; ocultar datos personales;
  comprobar estado de servicios.
- **Avisos**: límite casi agotado (existe hoy); límite reiniciado (existe hoy, ahora desactivable); reinicio cercano sin
  usar (24 h y 1 h antes del semanal con cuota libre); confeti en el reinicio semanal.
- **Actualización**: Adaptativo (por defecto), 1, 5, 15 min, Manual.

Persistencia: `~/.config/wysun/ai-usage.json` (nuevo), leído/escrito por el servicio con `FileView` como hace
`Study.qml`. Las cuentas ocultas se guardan por id estable de cuenta. `ai-accounts.json` se mantiene para etiquetas y
carpetas extra.

## Funciones extra elegidas

1. **Sesiones de agentes activas.** Procesos `claude`, `codex` y `opencode` del usuario (desde `/proc`): carpeta de
   trabajo, rama git, desde cuándo, cuenta (Claude: por `CLAUDE_CONFIG_DIR` del proceso → home; Codex: `CODEX_HOME`;
   OpenCode: su proveedor), modelo y tokens/coste de esa sesión desde su log, y si está trabajando o esperando (log
   escrito hace pocos segundos o no). Tocar una sesión enfoca su ventana en Hyprland (subiendo por los procesos
   padre hasta el pid de un cliente de `hyprctl clients`). Si no se encuentra ventana, la fila no es tocable.
   No se guardan rutas ni identidades de sesiones: se calculan en cada refresco.
2. **Seguir la app enfocada.** Con «App enfocada», el indicador de la barra muestra el proveedor cuyo agente corre
   dentro de la ventana activa de Hyprland (mismo cruce pid → proceso); si la ventana activa no tiene agente, se queda
   con la última elección. No cambia la pestaña guardada del panel.
3. **Refresco adaptativo.** Por defecto: cada `refreshInterval` (1 min) mientras haya al menos un agente trabajando o
   el panel esté abierto; cada 15 min en reposo. Las opciones fijas sustituyen a `backgroundInterval`. Manual = solo al
   pulsar refrescar o abrir el panel. Los avisos dependen de que haya refrescos; en Manual se avisa de eso en Ajustes.
4. **Espacio en disco.** Por proveedor: tamaño total de su carpeta (`~/.claude` y homes extra, `~/.codex`,
   `~/.local/share/opencode`) y desglose por subcarpeta conocida, más ideas de limpieza (logs de más de 90 días, copias
   de archivos de sesiones cerradas) con su tamaño. Se mide como mucho una vez al día en segundo plano, se guarda en
   caché y la pantalla dice cuándo se midió. Acción «Abrir carpeta en Files». Nunca borra.
5. **Indicador atenuado con datos viejos.** Si los datos de lo que muestra el indicador tienen más de N refrescos de
   antigüedad o su última lectura falló, el indicador baja su opacidad y lleva un relojito; en el panel, la cabecera
   lo dice y la cuenta muestra su aviso de error.

## Ocultar cuentas

Una cuenta oculta no aparece en pestañas, chips, Resumen, sesiones activas, totales de coste del Resumen, indicador de
la barra ni avisos. Su historial se sigue leyendo y cacheando (para que al mostrarla otra vez esté completa). Si se
ocultan todas las cuentas de un proveedor, su pestaña desaparece. Se muestra de nuevo desde Ajustes → Proveedores.

## Añadir cuenta e iniciar sesión

«Añadir cuenta…» pregunta el proveedor y abre la terminal predeterminada del usuario con el login del propio proveedor:
- Claude: carpeta nueva (`~/.claude-<n>`), `CLAUDE_CONFIG_DIR=<carpeta> claude` con la statusline del hook ya escrita en
  su `settings.json`, para que aparezca sola tras el login (`/login`).
- Codex: carpeta nueva, `CODEX_HOME=<carpeta> codex login`, y se añade a `ai-accounts.json` como hoy documenta
  `ARCHITECTURE.md`.
- OpenCode: `opencode auth login`.
Wysun no ve ni guarda nada del login; la cuenta aparece por los mecanismos de descubrimiento existentes. Error de
lectura de una cuenta → su aviso sugiere el comando de login correspondiente.

## Avisos de escritorio

Siguen usando `notify-send` y `alerts.json`. Nuevos: reinicio cercano sin usar (claves por cuenta+límite+reinicio, no se
repiten tras reiniciar el shell) y confeti al detectar un reinicio semanal (superposición de pantalla breve, que deja
pasar los clics, con colores del tema). «Ocultar datos personales» también aplica al texto de los avisos.

## Indicador en la barra

Sustituye a `AiUsageIndicator.qml` respetando la barra vertical y `barIndicatorSize`. Un solo hueco (la barra es
estrecha), que muestra el proveedor/cuenta según «qué sigue» (app enfocada, más ajustado o seleccionado), con el estilo
elegido; el logotipo dice de qué proveedor es. Punto de incidencia superpuesto, atenuado con datos viejos. Clic abre el panel en ese proveedor.

## Qué queda al constructor

- Organización de componentes QML (se espera reutilizar `Chip`, `Segmented`, `StateLayer`, `MaterialIcon`,
  `CircularProgress`, `ProviderLogo` y la base de `components/`), y qué tokens nuevos añadir a `aiUsage` en
  `tokens.json`/`tokens.hpp`.
- Formato exacto del JSON del backend y cómo se versiona la instantánea en caché.
- Heurística de «trabajando/esperando» y umbral de «datos viejos».
- Cómo se dibujan gráficas (Canvas, Shape o el `UsageChart.qml` existente ampliado).
- Pruebas: ampliar `tests/shell_bridge/test_ai_usage.py` y `test_backend.py`; pruebas con HOME temporal para OpenCode
  (base de datos sintética), sesiones activas (procesos simulados) y espacio en disco.
- Rendimiento: el backend no debe tardar más que hoy en el refresco normal; lo caro (disco, 365 días) va cacheado.

## Decidido por Claude (revisable)

- Ancho fijo 580 y una sola columna.
- Pestañas por proveedor en vez de por cuenta.
- Ajustes dentro del panel, no en Wysun Settings.
- Gemini/Cursor/Copilot no se activan ahora; solo se listarían si hubiera fuente sin credenciales.
- Retención de instantáneas ≈ 90 días; medición de disco una vez al día.
- El historial antiguo de OpenAI/Copilot hecho desde OpenCode se queda en OpenCode.
- Indicador de la barra con un solo hueco.
- La terminal para los logins es la que ya usa Wysun para abrir terminales (la del lanzador / `hyprland.lua`).
- La API y el mapeo de OpenCode Go siguen la documentación de CodexBar (`docs/opencode.md`, `docs/opencodego.md`):
  porcentajes 0–100 de la API de uso; reinicios = ahora + `resetInSec`.
- Colores de estado (reserva/déficit/aviso) desde la paleta del tema; si falta un token de «éxito»/«aviso», se añade
  al esquema en vez de usar literales.
