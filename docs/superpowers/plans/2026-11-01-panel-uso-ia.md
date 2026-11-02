# Panel de uso de IA v2 — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rehacer el panel de uso de IA del shell al estilo CodexBar (pestañas por proveedor, chips por cuenta, ritmo,
historial del límite, coste detallado, estado de servicios, sesiones activas, espacio en disco, ajustes, ocultar
cuentas, OpenCode) dentro del tema de Wysun.

**Architecture:** El backend Python (`modules/aiusage/backend.py`) sigue siendo el único productor del JSON que lee
`services/AiUsage.qml`; se le añaden módulos hermanos de una sola responsabilidad (credenciales, API de Claude,
OpenCode, historial de límites, estado, agentes, disco) cargados por ruta porque el backend corre con `python3 -I`.
La lógica pura del panel (ritmo, visibilidad, intervalos, avisos, formato) va en `AiUsageLogic.js` (`.pragma library`)
probada con node como `StudyPlan.js`. La UI QML se reescribe en `modules/aiusage/` con componentes pequeños.

**Tech Stack:** Python 3 (stdlib: `urllib.request`, `sqlite3`, `json`), QML/Quickshell (Qt 6.9), plugin `Wysun.Config`
(tokens), node para pruebas de JS.

**Spec:** `docs/superpowers/specs/2026-11-01-panel-uso-ia-design.md` (maqueta: `…-panel-uso-ia-maqueta.html`).

## Global Constraints

- Colores solo de `Colours.palette`/`Colours.tPalette`; radios, espaciado, padding, fuentes y animaciones de `Tokens.*`.
  Reserva = `m3success`, déficit/agotado = `m3error`, aviso (≥70 % usado, incidencia, datos viejos) = `m3tertiary`
  (convención de Wysun: `tertiary` es «warning», ver `wysun_core/theme.py`). `tests/test_theme_literals.py` debe pasar.
- Tamaños nuevos van como propiedades de `AiUsageTokens` en `apps/shell/plugin/src/Wysun/Config/tokens.hpp` (ahí viven
  hoy los de `aiUsage`; `tokens.json` no tiene `sizes`). Tocar `plugin/` ⇒ `installer/runtime_build.py` (una sola
  compilación, `--jobs 3`).
- Ancho del panel: `Tokens.sizes.aiUsage.width` (580). Una columna.
- Textos visibles con `Tr.tr(...)` en inglés como fuente (convención del shell); la maqueta es solo referencia.
- Credenciales (regla de `AGENTS.md`): se leen justo antes de usarlas, solo HTTPS a host permitido, nunca se escriben,
  renuevan, registran, cachean ni salen en JSON/avisos/errores. **El implementador nunca abre archivos de credenciales
  reales** (`~/.claude/.credentials.json`, `~/.codex/auth.json`, `~/.local/share/opencode/*`): solo sintéticos en HOME
  temporal.
- Sin cookies del navegador.
- `XDG_*` y escrituras atómicas (`os.replace`) solo en `backend.py` (está en `PENDING` de `tests/test_core_owns_io.py`);
  los módulos hermanos reciben rutas y devuelven datos, no escriben archivos.
- Pruebas y compilaciones de una en una (memoria): nada en paralelo.
- Despliegue final según `AGENTS.md`: `./instalar.sh --wysun-only`, `wysun reload`, `pkill -x quickshell; setsid wysun-shell &`,
  y comprobar la apertura real del panel.

## Review Focus

1. **Token de Claude caducado, sin alcance `user:profile`, 401/429 o sin red** → la cuenta usa la statusline como hoy,
   sin error ruidoso; caducado sale como aviso de sesión, no como fallo. (Task 2: `test_expired_token_falls_back_to_statusline`, `test_http_errors_fall_back`.)
2. **Red lenta o caída** → el refresco no tarda más de ~10 s en total: cada petición con `timeout=5`, en paralelo con
   el resto de cuentas, y estado de servicios con caché de 120 s. (Task 2/5: `test_timeout_is_bounded`.)
3. **La cuenta oculta es la más ajustada / todas ocultas** → el indicador elige entre visibles; si no hay visibles se
   oculta y el panel muestra el estado vacío con «Ajustes». (Task 8: `hiddenTightest`, `allHidden`.)
4. **OpenCode instalado sin suscripción ni login, o `opencode.db` bloqueada por WAL** → pestaña con historial, sin
   límites, sin excepción; la base se abre en solo lectura (`mode=ro`). (Task 3: `test_no_login_keeps_history`, `test_db_opened_read_only`.)
5. **Agente sin ventana de Hyprland (tmux, ssh, terminal cerrada) o dos agentes en una misma ventana** → la fila no es
   tocable o enfoca esa misma ventana; nunca enfoca otra. (Task 6: `test_session_without_terminal_has_no_window_pids`; Task 11: `windowForSession` en JS.)

---

## Formato del JSON (contrato backend → QML)

Se amplía el documento actual; nada existente cambia de nombre. Campos nuevos:

```text
snapshot.version = 2
account.provider ∈ {"claude","codex","opencode"}
account.limits[i] += { label?: str }                     # p. ej. "Opus" para weekly_opus; OpenCode: "5 h"/"Weekly"/"Monthly"
account.limits[i].history = [[t, usedPercent], …]        # ventana actual, ordenado (Task 4)
account.limits[i].windows = [{endedAt, usedPercent, exhaustedAt?, cost}, …]   # hasta 4 anteriores (Task 4)
account.extra   = {spent, cap, currency, resetsAt} | null      # Claude uso extra (Task 2)
account.cloud   = {remaining, expiresAt} | null                 # Claude créditos en la nube (Task 2)
account.resetCredits (existente) también para Claude (Task 2)
account.renewsAt = epoch | null
account.session = {expiresAt, expired: bool} | null             # caducidad del login; sin token (Task 2/3)
account.source  ∈ existentes + "api" (Claude OAuth) + "opencode-api" + "local"
account.error   = {kind: "auth"|"network"|"scope"|"cli", command?: str} | null
account.disk    = {root, total, parts:[{name,size}], tips:[{kind,size}], measuredAt} | null   (Task 7)
usage[range] y account.usage[range]: ranges += "365d" (diario) y "hours90" (horario, 90 días) (Task 4)
snapshot.status = {claude|codex|opencode: {indicator:"none"|"minor"|"major"|"critical"|"unknown",
                   description, components:[{name,status}], url, checkedAt}}   (Task 5)
snapshot.agents = [{pid, provider, accountId|null, cwd, branch|null, startedAt, model|null,
                    tokens, cost, busy: bool, windowPids: [int]}]   (Task 6)
```

## Estructura de archivos

Backend (`apps/shell/modules/aiusage/`):
- Modify `backend.py`: orquesta; carga hermanos con `_sibling(name)`; rutas XDG; escribe caché/estado; proveedor `opencode`.
- Create `credentials.py`: lectura de secretos y GET HTTPS con lista de hosts.
- Create `claude_api.py`: uso por OAuth de Claude y mapeo.
- Create `opencode.py`: historial desde `opencode.db` y cuota de OpenCode Go.
- Create `limit_history.py`: instantáneas de límites, ventanas anteriores.
- Create `service_status.py`: Statuspage.
- Create `agents.py`: procesos de agentes desde `/proc`.
- Create `disk.py`: tamaños por carpeta.

Servicio y lógica (`apps/shell/services/`):
- Modify `AiUsage.qml`: ajustes (`~/.config/wysun/ai-usage.json`), cuentas visibles, intervalos adaptativos, avisos nuevos, foco.
- Create `AiUsageLogic.js`: funciones puras (lista en Task 8).

UI (`apps/shell/modules/aiusage/`): reescribir `Content.qml`, `AccountPage.qml`, `OverviewPage.qml`, `LimitCard.qml`
(→ `LimitBlock.qml`), `UsageSection.qml` (→ `CostPage.qml`), `UsageChart.qml` (se amplía); crear `ProviderTabs.qml`,
`AccountChips.qml`, `Banner.qml`, `SessionRows.qml`, `LimitHistoryPage.qml`, `DiskPage.qml`, `SettingsPage.qml`,
`Confetti.qml`; borrar `Card.qml` y `LimitCard.qml` cuando queden sin uso. Barra: reescribir
`modules/bar/components/AiUsageIndicator.qml`.

Pruebas: `tests/shell_bridge/test_ai_usage.py` (amplía), `tests/shell_bridge/test_ai_usage_sources.py` (nuevo: credenciales,
Claude API, OpenCode, estado, agentes, disco), `tests/shell_bridge/test_ai_usage_logic.py` (nuevo, node),
`tests/shell_bridge/test_ai_usage_panel.py` (nuevo, comprobaciones estáticas de QML).

---

### Task 1: Credenciales seguras y carga de módulos hermanos

**Files:**
- Create: `apps/shell/modules/aiusage/credentials.py`
- Modify: `apps/shell/modules/aiusage/backend.py` (docstring del módulo y `_sibling`)
- Test: `tests/shell_bridge/test_ai_usage_sources.py`

**Interfaces:**
- Produces:
  - `credentials.read_json(path: Path) -> dict | None` — lee y parsea; ante cualquier error devuelve `None` sin
    incluir contenido en excepciones ni logs.
  - `credentials.get_json(url: str, headers: dict, allowed: frozenset[str], timeout: float = 5.0, opener=None) -> tuple[int, dict | None]`
    — exige `https` y `urlparse(url).hostname in allowed`, si no `ValueError("host not allowed")`; devuelve
    `(status, body)`; `(0, None)` en error de red; nunca relanza con cabeceras en el mensaje. `opener` (para pruebas)
    es un callable `(request, timeout) -> response` (por defecto `urllib.request.urlopen`).
  - `backend._sibling(name: str) -> module` — `importlib.util.spec_from_file_location` sobre `Path(__file__).with_name(name + '.py')`, cacheado.

- [ ] **Step 1: Escribir las pruebas que fallan**

```python
class CredentialsTests(unittest.TestCase):
    SENTINEL = 'sk-ant-oat01-SENTINEL-do-not-leak'
    def test_rejects_other_hosts_and_plain_http(self):
        with self.assertRaises(ValueError): credentials.get_json('https://evil.example/x', {}, frozenset({'api.anthropic.com'}))
        with self.assertRaises(ValueError): credentials.get_json('http://api.anthropic.com/x', {}, frozenset({'api.anthropic.com'}))
    def test_network_error_returns_zero_without_secret(self):
        def opener(request, timeout): raise OSError('boom ' + request.headers.get('Authorization', ''))
        status, body = credentials.get_json('https://api.anthropic.com/x', {'Authorization': 'Bearer ' + self.SENTINEL},
                                            frozenset({'api.anthropic.com'}), opener=opener)
        self.assertEqual((status, body), (0, None))
    def test_unreadable_file_is_none(self):
        self.assertIsNone(credentials.read_json(Path('/nonexistent/creds.json')))
```

- [ ] **Step 2:** `python3 -m unittest tests.shell_bridge.test_ai_usage_sources -v` → FAIL (módulo no existe).
- [ ] **Step 3:** Implementar `credentials.py` y `_sibling` en `backend.py`; cambiar el docstring de `backend.py`
  («Nothing here reads credentials» → la regla nueva y qué credenciales se leen).
- [ ] **Step 4:** Repetir el comando → PASS; y `python3 -m unittest tests.shell_bridge.test_ai_usage -v` → PASS.
- [ ] **Step 5:** Commit `feat(ai-usage): lectura segura de credenciales con hosts permitidos`.

### Task 2: Claude por la API OAuth (límites, uso extra, créditos, reinicios, caducidad)

**Files:**
- Create: `apps/shell/modules/aiusage/claude_api.py`
- Modify: `apps/shell/modules/aiusage/backend.py` (`claude_account`, `describe`, `collect` acepta `opener=None`)
- Test: `tests/shell_bridge/test_ai_usage_sources.py`

**Interfaces:**
- Consumes: `credentials.read_json`, `credentials.get_json`.
- Produces:
  - `claude_api.session(home: Path, now: float) -> dict | None` → `{'expiresAt': epoch|None, 'expired': bool}` desde
    `<home>/.credentials.json` → `claudeAiOauth.expiresAt` (ms). Nunca devuelve el token.
  - `claude_api.usage(home: Path, now: float, opener=None) -> dict | None` → `{'limits': [...], 'extra': …, 'cloud': …,
    'resetCredits': …, 'renewsAt': …}` o `None` si no hay token, está caducado (no se renueva) o la respuesta falla
    (`'error': {'kind': 'auth'|'scope'|'network'}` en un dict aparte vía `usage_error`).
  - Petición: `GET https://api.anthropic.com/api/oauth/usage` con `Authorization: Bearer <accessToken>`,
    `anthropic-beta: oauth-2025-04-20`; hosts permitidos `{'api.anthropic.com'}`.
  - Mapeo (CodexBar `docs/claude.md`): `five_hour`→`session` (300 min), `seven_day`→`weekly` (10080),
    `seven_day_opus`/`seven_day_sonnet`→`weekly_opus`/`weekly_sonnet` con `label`; `utilization` 0–100; `resets_at`
    ISO→epoch. Uso extra: bloque de gasto mensual (`used`, `limit`) con `resetsAt` = 1.º del mes siguiente 00:00 UTC.
    Créditos en la nube: `iguana_necktie` (`remaining_dollars`, o `limit_dollars - used_dollars`; `resets_at` = caducidad).
    Campos ausentes ⇒ `None`, sin fallar.
  - `claude_account`: si `usage()` devuelve límites ⇒ `source='api'`; si no ⇒ statusline (código actual); siempre
    añade `session` y `error`.

- [ ] **Step 1: Pruebas que fallan** (HOME temporal, `.credentials.json` sintético con `SENTINEL`, `opener` falso que
  devuelve JSON de ejemplo y registra la URL):
  - `test_api_limits_win_over_statusline` — límites de la API (`session` 12.0, `weekly` 40.0, `weekly_opus` con `label` "Opus").
  - `test_extra_usage_and_cloud_credits_are_mapped` — `extra == {'spent': 4.2, 'cap': 50.0, 'currency': 'USD', 'resetsAt': <1.º mes siguiente UTC>}`, `cloud['remaining'] == 18.5`.
  - `test_expired_token_falls_back_to_statusline` — `expiresAt` en el pasado ⇒ no se llama al opener, `source == 'statusline'`, `session['expired'] is True`.
  - `test_http_errors_fall_back` — 401 ⇒ `error.kind == 'auth'`; 403 con mensaje de alcance ⇒ `'scope'`; 0 ⇒ `'network'`; límites de statusline intactos.
  - `test_token_never_leaves_the_process` — tras `collect(opener=…)`: `SENTINEL` no está en `json.dumps(snapshot)` ni en ningún archivo bajo `state/`, `cache/`, `config/`.
  - `test_only_anthropic_is_contacted` — todas las URLs registradas tienen host `api.anthropic.com`.
  - `test_timeout_is_bounded` — el opener recibe `timeout <= 5`.
- [ ] **Step 2:** Ejecutar → FAIL.
- [ ] **Step 3:** Implementar `claude_api.py` e integrarlo.
- [ ] **Step 4:** `python3 -m unittest tests.shell_bridge.test_ai_usage_sources tests.shell_bridge.test_ai_usage -v` → PASS.
- [ ] **Step 5:** Commit `feat(ai-usage): Claude por su API de uso con respaldo en la statusline`.

### Task 3: Proveedor OpenCode

**Files:**
- Create: `apps/shell/modules/aiusage/opencode.py`
- Modify: `backend.py` (`NAMES['opencode']='OpenCode'`, cuenta por defecto si existe `~/.local/share/opencode/opencode.db`,
  escaneo de historial hacia los mismos `buckets` horarios, `describe`)
- Modify: `apps/shell/modules/aiusage/pricing.json` (DeepSeek y modelos gratuitos de OpenCode a 0)
- Test: `tests/shell_bridge/test_ai_usage_sources.py`

**Interfaces:**
- Produces:
  - `opencode.history(db: Path, since: float) -> list[dict]` — filas `{'time': epoch, 'session': str, 'project': str,
    'provider': str, 'model': str, 'input','cacheRead','cacheWrite','output': int}` leyendo solo `message` y
    `session_message` (sin duplicar mensajes migrados) con `sqlite3.connect(f'file:{db}?mode=ro', uri=True)`.
  - `opencode.session(data_dir: Path, now: float) -> dict | None` — caducidad del login de la CLI (credenciales v2 de la
    base o `auth.json`), sin devolver el token.
  - `opencode.usage(data_dir: Path, now: float, opener=None) -> dict | None` — `GET https://opencode.ai/zen/go/v1/usage`
    con el login de la CLI; hosts `{'opencode.ai'}`; mapea `rolling`→`session` (300), `weekly`→`weekly` (10080),
    `monthly`→`monthly` (43200) con `usedPercent` 0–100 y `resetsAt = now + resetInSec`. Sin suscripción/login ⇒
    `None` y la cuenta queda con `reason='subscription'`.
  - Modelos en el historial: `f'{provider}/{model}'` para que el reparto por modelo distinga DeepSeek, OpenAI y Copilot.
  - Cuenta: `id = account_id('opencode', data_dir)`, `label` del login si existe; `available` según haya límites.

- [ ] **Step 1: Pruebas que fallan** con una `opencode.db` sintética (crear tablas `message` y `session_message` con el
  JSON mínimo: `providerID`, `modelID`, `tokens{input,output,cache{read,write}}`, `time{created}`, `sessionID`, `path{cwd}`):
  - `test_history_counts_each_message_once` (mismo id en ambas tablas ⇒ una vez).
  - `test_models_are_prefixed_by_provider` (`deepseek/deepseek-v4`, `openai/gpt-5.4`).
  - `test_no_login_keeps_history` (sin credenciales ⇒ cuenta presente, `limits == []`, `reason == 'subscription'`, `usage['30d']` con tokens).
  - `test_go_quota_is_mapped` (opener con `rolling.percent=12, resetInSec=3600` ⇒ `session.usedPercent == 12`, `resetsAt == now+3600`).
  - `test_db_opened_read_only` (base con `chmod 0o444` y directorio de solo lectura ⇒ funciona).
  - `test_opencode_token_never_leaves_the_process` (centinela en la credencial sintética; mismo chequeo que Task 2).
- [ ] **Step 2:** Ejecutar → FAIL.
- [ ] **Step 3:** Implementar.
- [ ] **Step 4:** Ejecutar ambos módulos de prueba → PASS.
- [ ] **Step 5:** Commit `feat(ai-usage): OpenCode con historial local y cuota de OpenCode Go`.

### Task 4: Historial de límites, ventanas anteriores y rangos nuevos

**Files:**
- Create: `apps/shell/modules/aiusage/limit_history.py`
- Modify: `backend.py` (`ranges()` añade `365d` diario y `hours90` horario; `collect` registra y adjunta historial;
  guarda en `STATE/limits.jsonl` con escritura atómica; `KEEP` pasa a 366 días para el mapa anual)
- Test: `tests/shell_bridge/test_ai_usage.py`

**Interfaces:**
- Produces:
  - `limit_history.append(lines: list[str], accounts: list[dict], now: float) -> list[str]` — añade
    `{"t", "account", "limit", "used", "resetsAt"}` por límite si cambió el valor o pasaron ≥15 min; descarta >90 días.
  - `limit_history.attach(lines: list[str], account: dict, records_cost: Callable[[float, float], float]) -> None` —
    rellena `limit.history` (puntos de la ventana actual) y `limit.windows` (hasta 4 anteriores, separadas por cambios
    de `resetsAt`; `exhaustedAt` = primer punto con `used >= 100`; `cost` = coste del intervalo).

- [ ] **Step 1: Pruebas que fallan:** `test_history_keeps_points_of_the_current_window`,
  `test_previous_windows_split_at_each_reset` (dos `resetsAt` distintos ⇒ una ventana anterior con su `usedPercent` final),
  `test_exhausted_time_is_recorded`, `test_points_older_than_90_days_are_dropped`, `test_year_and_hourly_ranges_exist`
  (`usage['365d']['points'] == 365`, `usage['hours90']['points'] == 2160`), `test_daily_unpriced_flag`
  (cada rango diario lleva `series[key]['unpriced']: [bool]` para la «~» del Libro).
- [ ] **Step 2:** FAIL. **Step 3:** Implementar. **Step 4:** PASS (`tests.shell_bridge.test_ai_usage`).
- [ ] **Step 5:** Commit `feat(ai-usage): historial de cada límite y rangos anual y horario`.

### Task 5: Estado de los servicios

**Files:**
- Create: `apps/shell/modules/aiusage/service_status.py`
- Modify: `backend.py` (`snapshot['status']`, caché 120 s en `CACHE/status.json`, opción `--no-status`)
- Test: `tests/shell_bridge/test_ai_usage_sources.py`

**Interfaces:**
- Produces: `service_status.fetch(provider: str, opener=None) -> dict` usando `https://status.anthropic.com/api/v2/summary.json`
  (claude) y `https://status.openai.com/api/v2/summary.json` (codex); opencode ⇒ `{'indicator': 'unknown'}` salvo que
  exista página Statuspage (comprobarlo; si no, solo enlace). Componentes: solo los de nivel superior relevantes
  (Claude: claude.ai, Claude Code, Claude API, Console; Codex: ChatGPT, Codex, API) con `status` de Statuspage.
  Sin credenciales; `credentials.get_json` con hosts `{'status.anthropic.com','status.openai.com'}`.

- [ ] **Step 1:** Pruebas: `test_incident_is_summarised` (indicador `minor`, descripción, componentes degradados),
  `test_status_is_cached_for_two_minutes`, `test_offline_status_is_unknown`.
- [ ] **Step 2–4:** FAIL → implementar → PASS.
- [ ] **Step 5:** Commit `feat(ai-usage): estado de Anthropic y OpenAI`.

### Task 6: Sesiones de agentes activas

**Files:**
- Create: `apps/shell/modules/aiusage/agents.py`
- Modify: `backend.py` (`snapshot['agents']`)
- Test: `tests/shell_bridge/test_ai_usage_sources.py`

**Interfaces:**
- Produces: `agents.scan(proc: Path, homes: dict, now: float, logs: Callable) -> list[dict]` (formato del contrato).
  - Detección por `comm`/`cmdline[0]` basename ∈ {`claude`, `codex`, `opencode`} (también `node …/claude` y
    `…/codex/codex`); solo procesos del usuario; un agente por árbol (descartar hijos de otro agente).
  - De `environ` se extraen **solo** `CLAUDE_CONFIG_DIR` y `CODEX_HOME`, nada más se conserva; con ellos se mapea a
    `accountId` (`homes`: `{(provider, resolved home): account id}`).
  - `cwd` desde `/proc/<pid>/cwd`, `branch` leyendo `<repo>/.git/HEAD` (sin ejecutar git).
  - `startedAt` desde `stat` campo 22 y `btime`.
  - `logs(provider, accountId, cwd, startedAt)` (lo da backend) devuelve el log más reciente de esa sesión ⇒ modelo,
    tokens, coste y `busy = now - mtime < 15`.
  - `windowPids`: cadena de antecesores (`PPid`) del agente, para que QML la cruce con los pid de los toplevels.

- [ ] **Step 1:** Pruebas con un `proc` sintético (directorios `<pid>/{comm,cmdline,environ,status,stat}` y symlink `cwd`):
  `test_agents_are_found_with_their_folder_and_branch`, `test_only_home_variables_are_kept` (otra variable con
  `SENTINEL` en `environ` ⇒ no aparece en la salida), `test_child_processes_are_not_counted_twice`,
  `test_session_without_terminal_has_no_window_pids` (padre pid 1 ⇒ `windowPids == []`), `test_busy_follows_log_age`.
- [ ] **Step 2–4:** FAIL → implementar → PASS.
- [ ] **Step 5:** Commit `feat(ai-usage): sesiones de agentes activas`.

### Task 7: Espacio en disco

**Files:**
- Create: `apps/shell/modules/aiusage/disk.py`
- Modify: `backend.py` (`account.disk` por home, medido como mucho cada 24 h, caché en `CACHE/disk.json`)
- Test: `tests/shell_bridge/test_ai_usage_sources.py`

**Interfaces:**
- Produces: `disk.measure(root: Path, provider: str, now: float) -> dict` → `{root, total, parts:[{name,size}], tips:[{kind,size}], measuredAt}`.
  Partes conocidas: Claude `projects/`, `shell-snapshots/`, `todos/`, `plans/`, `file-history/`; Codex `sessions/`,
  `archived_sessions/`, `log/`; OpenCode `opencode.db*`, `storage/`, `snapshot/`, `tool-output/`. Tips: `old-logs`
  (logs con mtime > 90 días) y `file-history` (Claude). No sigue symlinks fuera de `root`. Nunca borra.

- [ ] **Step 1:** Pruebas: `test_sizes_by_part`, `test_old_logs_tip_counts_only_files_older_than_90_days`,
  `test_symlinks_outside_root_are_not_followed`, `test_measured_at_most_once_a_day`.
- [ ] **Step 2–4:** FAIL → implementar → PASS.
- [ ] **Step 5:** Commit `feat(ai-usage): espacio en disco por proveedor`.

### Task 8: Lógica pura del panel (JS) y servicio

**Files:**
- Create: `apps/shell/services/AiUsageLogic.js` (`.pragma library`)
- Modify: `apps/shell/services/AiUsage.qml`
- Test: `tests/shell_bridge/test_ai_usage_logic.py` (patrón de `test_study_plan.py`: concatenar el JS y ejecutar con node)

**Interfaces:**
- Produces (JS, todas puras, `now` en segundos):
  - `pace(limit, now, workDays) -> null | {early: true} | {expected, delta, lasts, runsOutIn}` — oculto si ha pasado
    < 3 % de la ventana; `workDays` 5/6/7 reparte el esperado solo en esos días (`"auto"` = 7 mientras no haya historial).
  - `severity(usedPercent) -> "ok"|"warn"|"error"` (≥90 error, ≥70 warn).
  - `visibleAccounts(accounts, hidden: string[], enabledProviders: string[]) -> accounts`.
  - `tightest(accounts) -> {account, limit, remaining} | null` (ignora `source === "history"`).
  - `indicatorTarget(accounts, mode: "focused"|"tightest"|"selected", focusedProvider, selectedId) -> {account, limit} | null`.
  - `refreshInterval(setting, anyBusy, panelOpen, tokens) -> ms` — `"adaptive"`: `tokens.refreshInterval` si `anyBusy || panelOpen`, si no `tokens.idleInterval` (900000); fijo: el valor; `"manual"`: 0.
  - `isStale(account, now, intervalMs) -> bool` — `error` presente o `now - updatedAt > max(3 * interval, 900)` s.
  - `alerts(prev, next, settings, seen, now, threshold) -> {notify: [{key,title,body,urgency}], seen}` — low (existente),
    restored (si `notifyReset`), upcoming (semanal con `resetsAt - now` ≤ 24 h y luego ≤ 1 h, usado < 100), expiry
    (`session.expiresAt - now` ≤ 24 h o `expired`), weeklyReset (para confeti). Textos con nombres enmascarados si
    `hidePersonal`.
  - `mask(account, hidePersonal, index) -> {label, email}`.
  - `windowForSession(agent, toplevels: [{pid, address}]) -> address | null` — primer pid de `agent.windowPids` presente.
- `AiUsage.qml`: propiedad `settings` (defaults de la spec: `showUsed:true, absoluteResets:false, paceGuide:true,
  workDays:"auto", billing:true, compact:false, hidePersonal:false, status:true, notifyLow:true, notifyReset:true,
  upcoming:true, confetti:true, refresh:"adaptive", indicatorStyle:"meters", indicatorFollows:"focused",
  providers:{claude:true,codex:true,opencode:true}, hidden:[]`), `setSetting(key, value)` que escribe
  `${Paths.config}/ai-usage.json` con `FileView`, `visibleAccounts`, `tightest` sobre visibles, un solo `Timer` con
  `refreshInterval(...)`, `focusedProvider` (de `Hypr.activeToplevel?.lastIpcObject.pid` cruzado con
  `snapshot.agents[].windowPids`), señal `weeklyReset()` para el confeti, `openTerminal(argv: list)` y `focusSession(agent)`
  (`Hypr.dispatch` a `focuswindow address:<addr>`, con la sintaxis Lua si `Hypr.usingLua`, como `focusWorkspace`).

- [ ] **Step 1:** Pruebas node: `test_pace_hidden_before_three_percent`, `test_pace_reserve_and_deficit` (usado 23 % al
  45 % de 7 d ⇒ `delta == -22`, `lasts`), `test_runs_out_estimate`, `test_work_days_five_skip_weekend`,
  `hiddenTightest` (la cuenta oculta con 95 % no gana), `allHidden` (⇒ `null`), `test_adaptive_interval`,
  `test_stale_after_three_intervals`, `test_upcoming_alert_once_per_stage`, `test_expiry_alert_once`,
  `test_masked_names_in_alerts`, `test_window_for_session`.
- [ ] **Step 2–4:** FAIL → implementar JS → PASS (`python3 -m unittest tests.shell_bridge.test_ai_usage_logic -v`).
- [ ] **Step 5:** Integrar en `AiUsage.qml`; añadir `idleInterval` (900000) a `AiUsageTokens` en `tokens.hpp`.
- [ ] **Step 6:** Commit `feat(ai-usage): ajustes, cuentas ocultas, refresco adaptativo y avisos nuevos`.

### Task 9: Panel principal (pestañas, chips, página de cuenta, resumen)

**Files:**
- Modify: `Content.qml`, `AccountPage.qml`, `OverviewPage.qml`, `Wrapper.qml`
- Create: `ProviderTabs.qml`, `AccountChips.qml`, `LimitBlock.qml`, `Banner.qml`, `SessionRows.qml`
- Delete: `Card.qml`, `LimitCard.qml` (cuando no tengan usos)
- Test: `tests/shell_bridge/test_ai_usage_panel.py`

**Interfaces:**
- Consumes: `AiUsage.visibleAccounts`, `AiUsage.settings`, `AiUsageLogic.pace/severity/mask`, `snapshot.status`, `snapshot.agents`.
- Produces: `Content` con estado `page: "main"|"limit"|"cost"|"disk"|"settings"`, `provider` (`"overview"` o id de
  proveedor), `limitIndex`; Esc vuelve de una subpágina antes de cerrar. Atajos: Alt+1…9 sobre pestañas de
  proveedor, Ctrl+Tab cuentas del proveedor, Ctrl+R refrescar.

Incluye: avisos en línea (`Banner`: incidencia con componentes, error con `account.error.command` y copiar, reinicio
cercano, sesión por caducar), identidad, `LimitBlock` por límite (toque ⇒ página `limit`), filas de facturación solo si
hay datos (`extra`, `cloud`, `credits` con «Buy…», `resetCredits` con «Redeem» que abre la web, `renewsAt`), resumen de
coste con minigráfica (toque ⇒ `cost`), `SessionRows` del proveedor, menú (Disk ›, Usage dashboard, Service status,
Copy summary ⇒ `Quickshell.clipboardText` con texto enmascarado si `hidePersonal`). Resumen: totales de hoy/30 d
**sumando solo `account.usage` de cuentas visibles** (no `snapshot.usage`), sesiones de todos, filas por proveedor
(compacto = una barra), «Add account…» y «Settings».

Disposición exacta: la de la spec («Estructura del panel») y la maqueta; secciones separadas por líneas de 1 px
(`Colours.palette.m3outlineVariant`), sin tarjetas. Componentes base del shell: `StyledRect`, `StyledText`,
`MaterialIcon`, `StateLayer`, `Chip`, `controls/Segmented`, `ProviderLogo`.

- [ ] **Step 1:** Pruebas estáticas que fallan: `test_panel_has_no_card_grid` (no queda `Card {` ni `GridLayout` en
  `modules/aiusage`), `test_tabs_are_per_provider` (`ProviderTabs.qml` usa `provider` y no `account.id` como clave),
  `test_hidden_accounts_are_filtered` (las páginas usan `AiUsage.visibleAccounts`, nunca `AiUsage.accounts`),
  `test_overview_totals_use_visible_accounts` (`OverviewPage.qml` no lee `AiUsage.usage`),
  `test_no_literal_sizes` (ningún número literal > 4 en `width/height/radius/spacing/margins` de los QML nuevos;
  todo de `Tokens`).
- [ ] **Step 2:** FAIL. **Step 3:** Implementar la UI.
- [ ] **Step 4:** PASS + `python3 -m unittest tests.test_theme_literals -v`.
- [ ] **Step 5:** Prueba real en sesión gráfica: copiar a un shell de prueba no es posible, así que tras compilar el
  runtime si cambió `plugin/`, reiniciar solo el shell desde el repo instalado en Task 12; aquí basta con
  `qmllint` si está disponible en el runtime (`~/.local/share/wysun/runtime/bin/qmllint modules/aiusage/*.qml`) sin errores nuevos.
- [ ] **Step 6:** Commit `feat(ai-usage): panel por proveedor con chips de cuenta y secciones`.

### Task 10: Subpáginas (historial del límite, coste, disco, ajustes)

**Files:**
- Create: `LimitHistoryPage.qml`, `CostPage.qml` (Diario/Por ventana/Actividad/Libro), `DiskPage.qml`, `SettingsPage.qml`
- Modify: `UsageChart.qml` (barras apiladas por modelo, selección de día, modo horario), `UsageSection.qml` (se reparte en `CostPage`)
- Test: `tests/shell_bridge/test_ai_usage_panel.py`

**Interfaces:**
- Consumes: `limit.history`, `limit.windows`, `usage['7d'|'30d'|'90d'|'365d'|'hours90']`, `account.disk`,
  `AiUsage.setSetting`, `AiUsage.openTerminal`.
- Ajustes: secciones Proveedores (interruptor por proveedor y, debajo, una fila por cuenta con interruptor
  «Show», que escribe `hidden`), Indicador (estilo: `meters`/`percent`/`stacked`/`pace`; sigue: `focused`/`tightest`/`selected`),
  Mostrar, Avisos, Actualización (`adaptive`/`60000`/`300000`/`900000`/`manual`). Controles: `StyledSwitch`/`SwitchRow`, `Segmented`.
- Coste: gráfica dibujada con `Shape`/`Canvas` existente de `UsageChart.qml`; inspector fijo bajo la gráfica (no
  tooltip flotante); tocar un día cambia a horario con su botón «volver»; «Libro» muestra 14 días y «Show all» 90.

- [ ] **Step 1:** Pruebas estáticas: `test_settings_write_through_service` (SettingsPage solo llama `AiUsage.setSetting`),
  `test_disk_page_never_deletes` (ningún `rm`, `unlink`, `remove` en `DiskPage.qml`), `test_cost_page_has_four_tabs`.
- [ ] **Step 2–4:** FAIL → implementar → PASS + `tests.test_theme_literals`.
- [ ] **Step 5:** Commit `feat(ai-usage): historial del límite, coste detallado, disco y ajustes`.

### Task 11: Indicador de la barra, foco, datos viejos, confeti y añadir cuenta

**Files:**
- Modify: `apps/shell/modules/bar/components/AiUsageIndicator.qml`
- Create: `apps/shell/modules/aiusage/Confetti.qml` (superposición sin entrada, colores de `Colours.palette`, ~4.5 s)
- Modify: `AiUsage.qml` (`openTerminal`: `sh -c 'if command -v ghostty >/dev/null; then exec ghostty -e "$@"; else exec foot "$@"; fi' sh <argv…>`,
  mismo orden que `wysun-terminal`)
- Test: `tests/shell_bridge/test_ai_usage_panel.py`, `tests/shell_bridge/test_ai_usage_logic.py`

**Interfaces:**
- Indicador: un hueco, `AiUsageLogic.indicatorTarget(...)`; estilos `meters` (dos barras verticales sesión/semanal),
  `percent`, `stacked` (S/W), `pace` (±%); `opacity` reducida y icono `schedule` si `isStale`; punto `m3tertiary` si
  incidencia del proveedor; clic abre el panel en ese proveedor; oculto si no hay cuentas visibles.
- Añadir cuenta (menú y chip «+»): Claude ⇒ crea `~/.claude-<n>` con `settings.json` que llama al hook
  (comando exacto del docstring de `statusline-hook.py`) y abre `CLAUDE_CONFIG_DIR=<dir> claude`; Codex ⇒ crea
  `~/.codex-<n>`, añade `{"provider":"codex","home":…}` a `ai-accounts.json` y abre `CODEX_HOME=<dir> codex login`;
  OpenCode ⇒ `opencode auth login`. La escritura de esos archivos la hace un subcomando nuevo
  `backend.py --prepare-account <provider>` (rutas XDG y escritura atómica viven en backend) que imprime la carpeta.

- [ ] **Step 1:** Pruebas: `test_prepare_claude_account_writes_hook_settings` (HOME temporal ⇒ `~/.claude-2/settings.json`
  con `statusLine.command` que contiene `statusline-hook.py`), `test_prepare_codex_account_registers_home`,
  `test_indicator_uses_indicator_target` (estática), JS `test_indicator_follows_focused_provider`.
- [ ] **Step 2–4:** FAIL → implementar → PASS.
- [ ] **Step 5:** Commit `feat(ai-usage): indicador que sigue la app enfocada, datos viejos, confeti y añadir cuenta`.

### Task 12: Documentación, comprobación completa y despliegue

**Files:**
- Modify: `ARCHITECTURE.md` (sección «Uso de IA»: fuentes, credenciales y protecciones, OpenCode, ajustes en
  `ai-usage.json`, historial en `limits.jsonl`, estado, agentes, disco), `docs/wysun.md` si lista el panel, `THIRD_PARTY.md`
  (mención a CodexBar, MIT, como referencia de mapeos)

- [ ] **Step 1:** Ejecutar una a una: `python3 -m unittest discover -s tests -v`,
  `python3 -m unittest discover -s tests/shell_bridge -t tests`, `python3 tests/check_manifest.py` → todo PASS
  (bloqueos del sandbox por sockets no cuentan como fallo; anotarlos).
- [ ] **Step 2:** Si cambió `plugin/`: `python3 installer/runtime_build.py` (sola). Luego `./instalar.sh --wysun-only` sin conflictos.
- [ ] **Step 3:** `wysun reload`; `pkill -x quickshell; setsid wysun-shell &`.
- [ ] **Step 4:** Comprobación real: `wysun ai` abre el panel; recorrer Resumen, Claude, Codex, OpenCode, un historial de
  límite, Coste (4 pestañas), Disco y Ajustes; cambiar a modo claro y oscuro (`~/.config/wysun/theme.json`) y ver que
  cambia en vivo; ocultar una cuenta y ver que desaparece del indicador. Capturas con `grim` para el usuario.
- [ ] **Step 5:** Commit `docs(ai-usage): arquitectura del panel v2 y regla de credenciales`.
