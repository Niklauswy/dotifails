# Estado actual — 2026-10-26, continuación en pdf-v2

Esta actualización prevalece sobre el registro histórico que sigue.

- Trabajar exclusivamente en `/home/nicolas/orca/workspaces/wysun-shell/pdf-v2`, rama `pdf-v2`.
- Base del worktree: `f2891df0`, portado a paquetes; no trabajar en el checkout principal.
- Consultas YA integradas en `window.py`/`chrome.py`, disponibles desde selección y menú Lectura.
- Se eliminó la dependencia QtNetwork: `lookup.py` usa QProcess, y `lookup_worker.py` hace una petición
  HTTPS acotada con urllib estándar. La cancelación mata el proceso y descarta respuestas por generación.
- Añadidas pruebas de transporte, límite UTF-8, parser, timeout, cancelación, consentimiento, revocación,
  referencia vinculada a la página original y comportamiento adaptable.
- Consulta real verificada por LookupClient→QProcess→HTTPS: «justice» → «justicia» en MyMemory;
  búsqueda Wikipedia ES «justicia» devolvió tres referencias. Solo se enviaron términos sintéticos.
- Permisos revocables en Ajustes. Guardar referencia conserva fuente/URL/idioma/fecha y pasaje original.
- Guardar copia invalida contexto de consulta; descartar edición restaura texto guardado del cuaderno.
- En ventanas estrechas el panel auxiliar usa el área central y al cerrarlo vuelve el PDF legible.
- Ajustes tiene scroll y fondo tokenizado, corrigiendo contraste en oscuro.
- `docs/pdf-reader.md` actualizado con lo implementado y pendientes; el plan completo aún NO está terminado.
- Sin despliegue. No instalar dependencias ni modificar el checkout principal.

Validación final de esta iteración (HOME/XDG temporales, offscreen, serial):
- 102 tests PDF OK, 14 de tema OK, 9 de tokens/I/O/nombres heredados OK (125 total).
- tests/check_manifest.py: MANIFEST_OK y TOOLS_OK. git diff --check OK.
- Capturas regeneradas en seis paletas (base/teal/amber, claro/oscuro), más lookup a 720×480.
  Inspeccionadas lookup en base claro, base oscuro estrecho, amber claro y teal oscuro;
  Ajustes oscuro y variante estrecha nueva. No es validación del compositor físico.
- Consulta real por el cliente completo: MyMemory y Wikipedia correctas (solo texto sintético).
- Commit de transporte: ba685346. La integración/UI/docs se guarda en el siguiente commit.
- Siguen pendientes las funciones de la propuesta amplia listadas en docs/pdf-reader.md; esta
  entrega completa consultas, no declara terminado todo el producto ni autoriza desplegarlo.
- No se ejecutaron suites de medios/Recorder/installed smoke, ni se modificó la instalación activa.

---

# Prompt de continuidad — Wysun PDF como espacio de estudio

Actualizado al cerrar la iteración del 2026-10-25. Lee este documento completo antes de editar.

## Encargo y autorización

Continúa en `/home/nicolas/wysun-shell`. El usuario quiere transformar el lector PDF en una app
avanzada para estudiar: biblioteca/recientes para continuar, subrayados, notas, preguntas, referencias,
traducción rápida inglés/español, sesiones pomodoro, ajustes y buena continuidad. Insiste en un diseño
Material 3 Expressive excelente, con animaciones; referencia https://m3.material.io/foundations.
Eligió expresamente panel integrado para consultas y navegador externo para profundizar; no WebEngine.
Ya aprobó el plan y autorizó comenzar. No vuelvas a pedir permiso para continuar la implementación.

Su último mensaje: «Ya estas en 10 porciento ve terminando si esposible si no aclanzas a terminar y
 desplegar escribe mejor el prompt para el suiguiente agente». Se decidió parar la expansión, validar
lo integrado y entregar este relevo, porque la app completa todavía no está terminada. No se desplegó.
La instrucción inicial reserva despliegue al coordinador y prohíbe instalar/reiniciar en este trabajo;
el último mensaje menciona desplegar si se termina. No se interpretó como obligación de desplegar una
implementación incompleta. Coordinar el despliegue final al completar lo pendiente.

## Base, archivos y reglas

- CWD `/home/nicolas/wysun-shell`, `main` en `bc7f920d` al iniciar y última consulta.
- Lee AGENTS.md, ARCHITECTURE.md, docs/pdf-reader.md y estos diseños:
  - `docs/design/2026-10-25-pdf-study-spec.md`
  - `docs/design/2026-10-25-pdf-study-plan.md`
  - `docs/superpowers/specs/2026-10-25-wysun-pdf-redesign-design.md` (§11)
  - `docs/superpowers/plans/2026-10-25-wysun-pdf-redesign.md` (plan técnico anterior, ya fusionado).
- Portado al Plan 04 (`etapa1-04-rename`, ya en main): los módulos viven en `apps/python/wysun_pdf/` sin el
  prefijo `pdf_` e importan `wysun_pdf.*`; el visor se ejecuta con `PYTHONPATH=apps/python python3 -P -m wysun_pdf`.
  Las rutas antiguas de esta nota se han actualizado a las nuevas.
- Todo lo que se hizo sigue SIN COMMIT. `git diff --stat` no incluye archivos nuevos untracked.
  No descartar los archivos nuevos ni asumir que los creó otro agente.
- `.superpowers/` ya era untracked antes de nuestra intervención; NO tocar.
- `apps/python/` fuente; NO editar `~/.local/share/wysun/app/` ni desplegar una versión sin validar.
- No deps del host, reinicio Hyprland, audio/portales ni procesos de otras apps.
- Kit único `wysun_core.ui` (widgets, panels, style, shapes, motion, toast, frameless), schema 3.
  Colores/tamaños/radios/tipo/movimiento desde tokens; fuentes en puntos, easing vía qt_theme.easing.
  No pdf_material ni kit paralelo. Se aplicó skill better-ui, priorizando tokens del proyecto.
- Suites SERIALIZADAS, HOME/XDG temporales, nada grande en /tmp (RAM); sin agentes paralelos.

## Implementado e integrado

### Biblioteca y cuaderno

`apps/python/wysun_pdf/study.py` NUEVO:
- StudyStore SQLite local `paths.data('wysun', 'pdf-reader', 'study.sqlite3')`, archivo 0600,
  directorio nuevo 0700. Esquema 1, documentos por UUID/ruta y entradas por UUID/revisión.
- Aperturas nuevas alimentan recientes (máx. 200 listadas), filtro por título, posición/página,
  conteo de notas. Desactivar/limpiar/quitar recientes no borra PDF ni notas.
- Notas/reflexiones y preguntas con cita, página, ancla JSON; conflictos optimistas impiden
  sobrescribir una edición de otra ventana. Exportación Markdown de TODAS las entradas
  (la vista lista máximo 500). Guardar copia crea otro cuaderno, no traslada el original.
- No reconstruir recientes desde hashes de positions.json: es imposible. La posición antigua
  sí se restaura al abrir una ruta conocida.

`apps/python/wysun_pdf/study_ui.py` NUEVO:
- LibraryView: biblioteca con continuación, lista, búsqueda, ajustes, composición tonal.
- BookRow pintado con tokens + StateLayer, menú contextual para quitar reciente.
- ReadingArt: forma cookie del kit con movimiento espacial FINITO al hover; no timer decorativo idle.
- navigate(): transición de salida con un snapshot del viewport, movimiento y opacidad desde tokens;
  snapshot liberado al terminar/interrumpir, no render PDF por frame, respeta reduced motion.
- Notebook: panel desplazable completo en ventana pequeña, reflexión/pregunta, cita, editor,
  guardar, nueva, volver al pasaje, eliminar con confirmación, exportar.
- En conflicto deja texto intacto y ofrece «Guardar como nota nueva».
- Guardado de notas EXPLÍCITO por ahora, NO autosave/borradores. Al navegar/cerrar con cambios
  pregunta Guardar/Descartar/Cancelar. Esta desviación del spec requiere documentación/seguimiento.
- StudySettings: recordar/limpiar recientes, explicación de almacenamiento y Material You.

`apps/python/wysun_pdf/window.py` MODIFICADO:
- Stack Biblioteca/lector. Abrir sin archivo → Biblioteca. Archivo CLI → lector.
- Alt+Home vuelve a biblioteca conservando documento y anotaciones sin guardar en memoria.
- Botón Cuaderno, Ctrl+Shift+N, selección → Nota. Un solo panel auxiliar visible.
- Cabecera agrupada: zoom/vista/nota PDF en «Lectura»; búsqueda se despliega con Ctrl+F/botón.
- Guardar PDF visible cuando dirty; cabecera adapta etiquetas en ventana estrecha.
- Anclas de cuaderno guardan rectángulos de selección y tamaño/mtime del archivo: si cambió,
  pide ir a la página aproximada; nunca afirma que el pasaje sigue exactamente allí.
- Volver al pasaje usa y de la selección; PDF solo lectura admite cuaderno independiente.
- Ctrl+C también respeta el editor QPlainTextEdit. Esc no descarta texto de una nota.

`apps/python/wysun_pdf/chrome.py`: acción contextual Nota, manteniendo subrayar/resaltar/copiar/color.
`apps/python/wysun_pdf/theme.py`: símbolos nuevos registrados y cubiertos por prueba de fuente.

### Concentración

`apps/python/wysun_pdf/focus.py` NUEVO:
- FocusClock: estudio/descanso, idle/running/paused/finished, monotónico inyectable.
- Pausa ante suspensión/salto largo entre ticks; no acredita tiempo no observado.
- FocusController compartido entre ventanas del proceso; lock fcntl en runtime impide dos propietarios
  entre procesos. Persistencia atómica `paths.state('wysun','pdf-reader','focus.json')`, cada 15 ticks
  y en transiciones; recuperación de running/paused siempre pausada.
- Cerrar última ventana pausa/persiste/libera lock. No daemon.

`apps/python/wysun_pdf/focus_ui.py` NUEVO:
- Panel concentración en lateral derecho, dial con tokens/forma del kit, objetivo opcional,
  duraciones de estudio/pausa configurables (25/5 por defecto), empezar/pausar/reanudar/terminar.
- Al completar ofrece descanso o nuevo bloque, aviso no modal. Botón «Anotar lo aprendido» abre cuaderno.
- Temporizador en cabecera durante lectura. NO hay todavía historial de sesiones, ciclo de cuatro
  bloques/descanso largo, resumen persistido ni modo foco que oculte chrome.

### Robustez del lector anterior

- `wysun_pdf/state.py`: clamp tolera tipos corruptos/NaN/inf; poda del historial tolera timestamp inválido.
- `wysun_pdf/worker.py`: un solo failed ante errorOccurred + finished; limpia cola/active una sola vez.
- `wysun_pdf/window.py`: búsqueda con errores parciales continúa y termina con toast/resumen, sin modal
  por página. Cerrar busy no-save permite interrumpir; durante save aún espera (save colgado pendiente).

## Código de consultas inicial, NO INTEGRADO / NO VALIDADO

`apps/python/wysun_pdf/lookup.py` y `apps/python/wysun_pdf/lookup_ui.py` son NUEVOS y solo tienen py_compile/lint de colores.
NO se importan desde PdfWindow; no existe botón Consultar todavía. No describirlos como función disponible.

- LookupClient QNetworkAccessManager asíncrono, cancelación por generación, timeout 15s,
  respuesta máxima 64 KiB, redirects manuales, resultados de texto sin HTML ejecutable.
- Traducción: MyMemory GET (EN/ES), validación 500 BYTES y un párrafo.
- Concepto: MediaWiki REST `https://{en|es}.wikipedia.org/w/rest.php/v1/search/page?q=...&limit=3`,
  título/snippet/URL/atribución, no resumen de IA ni consenso inventado.
- LookupPanel: término editable, modo traducción/concepto, swap idiomas, consentimiento explícito
  por proveedor, cancelar, abrir fuente, señal para guardar referencia en cuaderno.
- Nunca consulta al seleccionar texto. No se transmitieron documentos privados ni texto del usuario.
- Proveedores investigados en documentación OFICIAL pero NO se ha ejecutado una consulta real desde Qt.
- Consentimiento dice que puede revocarse en Ajustes; ESO AÚN NO ESTÁ IMPLEMENTADO. Resolver ANTES
  de conectar el panel. Añadir revocar `lookup_allowed_translation` y `lookup_allowed_concept`.
- Faltan tests de URL/parsers, errores/cuota, cancelación/respuesta obsoleta, payload malformado,
  timeout, máximo de bytes, no red y lifecycle al cerrar/cambiar documento.
- Registrar símbolos translate/travel_explore/swap_horiz/open_in_new en SYMBOLS al integrar.
- Validar respuestas malformadas y callback receive/finished durante abort para no duplicar errores.

Fuentes verificadas para continuar (2026-10-25):
- https://mymemory.translated.net/doc/spec.php : q UTF-8 máx.500 bytes; langpair; GET consulta,
  SET contribuye. Solo usar GET, nunca contribuir texto a un archivo público.
- https://mymemory.translated.net/doc/usagelimits.php : anónimo 5000 caracteres/día; no prometer ilimitado.
- https://mymemory.translated.net/terms-and-conditions : permite uso API normal, prohíbe scraping,
  abuso y traducir varios párrafos por petición; puede compartir datos con proveedores de traducción.
  El viejo enlace `/doc/en/tos.php` daba 404; usar enlace actual.
- https://www.mediawiki.org/wiki/API:REST_API/Reference/en : REST search/page devuelve pages.
- NO usar TextExtracts para nueva integración: documentación oficial recomienda Page Content Service.
- https://m3.material.io/styles/motion/overview/how-it-works : separar spatial/effects, usar tokens locales.

## Verificación al entregar

ÚLTIMA EJECUCIÓN tras los cambios integrados, en HOME/XDG temporal, offscreen, serial:
- `python -m unittest discover -s tests/pdf -v`: **90 pruebas OK**, 17.984s.
- `python -m unittest tests.test_pdf_theme`: **14 OK**.
- `python -m unittest tests.test_theme_literals`: **4 OK**.
- `python -m unittest tests.test_core_owns_io`: **3 OK**.
- Total dirigido: **111 pruebas OK**. py_compile de módulos nuevos y modificados OK.
- `git diff --check` OK.
- NO se corrieron todas las suites generales/medios/compositor/installed smoke ni se validó escritorio activo.
- Los 90 tests NO cubren LookupClient/LookupPanel: están sin integrar y sin pruebas propias.
- Hubo un fallo de test motion por usar `art.motion.Stopped`; se corrigió a `QAbstractAnimation.Stopped`
  y las suites posteriores pasaron. No es fallo pendiente.

Pruebas nuevas:
- tests/pdf/test_study.py: persistencia, privacidad, conflictos, copia/export, quitar/limpiar/desactivar recientes.
- tests/pdf/test_study_motion.py: reduced motion, interrupción/limpieza del snapshot, sin timer idle.
- tests/pdf/test_focus.py: reloj falso, suspensión, pausa/reanudar, restore, un propietario, última ventana.
- tests/pdf/test_window.py ampliado: nota desde selección, biblioteca/reapertura, cancelar navegación,
  ventana 720×480 y búsqueda, sin dirty PDF al guardar cuaderno.
- tests/pdf/test_state.py y test_worker.py ampliados para robustez.

Comando reutilizable en este entorno: `python3 /tmp/wysun-study-check.py`.
Ese script crea HOME/XDG temporales, usa `/tmp/wysun-pdf-venv/bin/python` y corre las cuatro suites una
tras otra. Si /tmp ya no existe, reconstruir el aislamiento: HOME, XDG_CONFIG_HOME, XDG_DATA_HOME,
XDG_STATE_HOME, XDG_CACHE_HOME, XDG_RUNTIME_DIR (0700), QT_QPA_PLATFORM=offscreen,
WYSUN_REDUCED_MOTION=1. No usar unittest -t en tests/pdf.

Capturas reproducibles:
`/tmp/wysun-pdf-venv/bin/python tests/pdf/shots.py docs/design/pdf-study-shots`
El script genera PDF/fondos sintéticos y HOME/XDG aislados para cada ejecución, secuencialmente.
Extensión actual genera empty/library/reader/notebook/narrow-notebook/settings/focus/search/spread.
Se generaron variantes base claro/oscuro y teal/amber claro/oscuro (aprox.12 MiB en repo, no cache en RAM).
Inspeccionadas directamente: base-light-library, base-dark-notebook, base-dark-focus,
base-light-narrow-notebook. Las últimas dos muestran ya cabecera agrupada y temporizador.
No afirmar revisión visual manual de cada PNG de la matriz: los otros se generaron pero no se inspeccionaron.
Las capturas no demuestran fluidez en compositor real; las pruebas de motion sí comprobaron finalización
sin fugas de overlay. Hay que revisar estados hover/foco/press y live wallpaper en ventana real más adelante.

## Pendientes prioritarios del siguiente agente

1. Releer código/diff y completar la integración de consultas sin romper notas pendientes:
   - botón Consultar en barra de selección y menú de lectura;
   - un solo panel lateral, cancelación al cambiar documento/cerrar;
   - guardar referencias con fuente, URL, idioma, fecha y ancla del pasaje ORIGINAL (no el que esté
     activo cuando llegue una respuesta tardía); invalidar por generación/documento;
   - abrir URL con política HTTPS/http existente, sin navegador embebido;
   - revocar consentimiento en Ajustes antes de habilitar esta función;
   - tests offline + una consulta sintética real; si sandbox impide red, pedir escalación del comando
     necesario y registrar limitación, no usar el fallo como evidencia de fallo de producto.
2. Completar brechas frente a spec: colecciones, cuaderno global, repaso pregunta/respuesta,
   búsqueda/filtros del cuaderno, borradores/autosave, recuperación real de archivo movido,
   ciclo pomodoro largo/historial/resumen y modo concentración visual. No agregar botones simulados.
3. Robustez:
   - Persistencia de posiciones sigue siendo JSON anterior; posibles errores I/O aún pueden propagarse.
   - Guardar PDF colgado sigue bloqueando cierre; revisar ruta de salida segura.
   - Notas usan ancla conservadora size/mtime, no reconciliación avanzada tras reescritura externa.
   - Quitar reciente conserva datos pero no existe todavía cuaderno global para encontrar notas sin
     reabrir el archivo. Datos permanecen en SQLite.
   - Vista máximo500 notas; export incluye todas. Diseñar paginación/virtualización para bibliotecas grandes.
   - SQLite usa transacciones breves timeout150ms en UI; medir antes de bibliotecas grandes y mover
     operaciones pesadas a worker si hace falta. No afirmar que todo I/O está fuera de GUI.
   - FocusController replica en ventanas del mismo proceso; entre procesos solo impide doble propietario,
     no sincroniza el temporizador visual en vivo. State se persiste cada15s, restaura pausado.
   - FocusController no persiste configuración de duraciones aún, solo estado/goal; no historial.
   - Revisar actual accesibilidad/contraste de QSpinBox/QCheckBox del host y colores disabled.
   - UI estrecha no recorta ventana: cuaderno tiene scroll, pero el PDF se reduce mucho; estudiar variante
     adaptable que conserve legibilidad del pasaje. No afirmar que el diseño esté finalizado.
4. Revisión visual completa y rendimiento medido: no basta con que tests pasen. No se midió RSS/fps aún.
5. Actualizar docs/pdf-reader.md (todavía describe lector anterior) y checks del plan con evidencia real.
6. Preparar commits pequeños/rebase frente a renombres; integrar con coordinador y desplegar solo cuando
   completo, siguiendo AGENTS y sin tocar datos privados. Este trabajo NO ha sido instalado.

## Cómo seguir trabajando con el usuario

Comunicar avances en español, con hallazgos y límites reales. No pedir otra confirmación del plan.
El usuario pidió diseño avanzado: mostrar capturas reales y cuidar composición/animaciones, no solo lista
funcional. El último mensaje pide relevo por contexto; este prompt es la entrega para continuar.
No reabrir memoria personal ni registrar preferencias: no se pidió modificar la memoria persistente.
