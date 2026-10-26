# Plan de implementación: Wysun PDF para estudiar

Estado: entrega integrada en `pdf-v2`, revisada y lista para fusionar; quedan los límites anotados. Especificación: [pdf-study-spec](2026-10-25-pdf-study-spec.md).
No ejecutar despliegue ni reiniciar el escritorio: corresponde al coordinador.

## Avance verificado — 2026-10-26

Trabajo en `pdf-v2`, paquetes en `apps/python/wysun_pdf`. El plan es más amplio que esta entrega.
Biblioteca de recientes, cuaderno local, temporizador y consultas online están integrados. Consultas
usan QProcess/urllib sin QtNetwork; traducción y referencias probadas con servicios reales y texto
sintético. Consentimiento revocable, referencia anclada a su origen y paneles adaptables implementados.
125 pruebas dirigidas y manifiesto pasan. Capturas en `docs/design/pdf-study-shots/`.
No se desplegó. Colecciones, cuaderno global, repaso, borradores recuperables, relocalización de archivos
movidos e historial/ciclo largo de sesiones continúan pendientes; no marcar las fases enteras como hechas.
Ver estado técnico actualizado en `pdf-study-handoff.md`.

Actualización 2026-10-26 (cierre): colecciones, cuaderno global, repaso, borradores con autoguardado,
relocalización, descanso largo e historial de sesiones ya están integrados, revisados y probados
(114 pruebas PDF). Las casillas siguientes reflejan ese estado; las abiertas son límites conocidos.

## Orden y puerta de integración

La rama de renombres `etapa1-04-rename` sigue siendo una dependencia externa. Este plan usa nombres
lógicos de componentes; resolver las rutas reales después de su merge. No mover ni renombrar archivos.
Antes de implementar, comprobar main, AGENTS, estado sucio e imports. Preservar `.superpowers/`
preexistente. No ejecutar el antiguo plan técnico como si sus tareas siguieran pendientes.

Cada entrega debe ser un commit pequeño y verificable. No sustituir el motor ni la virtualización.
Primera entrega usable: Biblioteca + cuaderno enlazado + guardado fiable. Segunda: consultas + pomodoro
+ repaso. La app de estudio está completa solo cuando ambas entregas cumplen la especificación.

## 0. Estabilizar los pendientes de §11

- [x] Cierre durante operación colgada: distinguir guardado de otras operaciones; cancelar/terminar
  con confirmación cuando haya trabajo pendiente, sin dejar al usuario atrapado.
- [x] Un solo fallo del worker aunque lleguen errorOccurred y finished.
- [x] Búsqueda: error agregado no modal, estado final consistente y cancelación de consultas obsoletas.
- [x] Restauración tolerante a tipos inválidos y números no finitos, incluyendo tiempos del estado.
- [ ] Verificar rotaciones, cifrado al guardar y apertura externa real con contenido sintético.
- [ ] Adoptar métricas de componentes consolidadas; no corregir literales creando constantes locales.

Validar con casos dirigidos de worker/state/window y regresiones existentes, serialmente.

## 1. Prototipo Qt revisable

- [x] Construir Biblioteca, Lectura+Cuaderno, Consulta, Repaso y Ajustes sobre el kit compartido,
  con datos sintéticos y sin proveedores ni lecturas personales.
- [ ] Estados vacío, cargando, ausente, sin red, solo lectura y error; acciones reales de navegación.
- [x] Probar prioridad de paneles y foco en 720×480; no usar solo una captura grande.
- [x] Capturar con la infraestructura de `tests/pdf/shots.py` o su ruta renombrada, secuencialmente.
  Guardar resultados pequeños en docs, sin grandes cachés en /tmp.
- [ ] Revisar claro/oscuro, teal/amber, texto aumentado, selección contextual y guardado visible.

Criterio: la jerarquía se entiende sin explicar los iconos y se puede completar un recorrido con teclado.
Las capturas de mocks no cuentan como evidencia del motor ni del guardado.

## 2. Biblioteca y repositorio de estudio

Componentes lógicos nuevos: StudyRepository, LibraryModel, LibraryView; integrar arranque/ventana/state.

- [ ] Esquema versionado, permisos, transacciones y respaldo mediante utilidades core.
- [x] Aperturas nuevas alimentan recientes; importar posición antigua cuando se conoce la ruta.
- [x] Continuar, colecciones, filtros, quitar reciente, localizar archivo y preferencia sin historial
  (una colección por libro; localizar sin verificar huella).
- [x] Sin archivo → Biblioteca; con argumento → lector. Volver a Biblioteca respeta PDF sin guardar.
- [ ] Conservar una ventana por documento, sin nuevos workers para filas de biblioteca.
- [ ] Migraciones, datos corruptos, archivo movido, aperturas simultáneas y búsqueda sin resultados.

Criterio: reabrir tras reinicio restaura posición y biblioteca sin intentar invertir hashes del historial.

## 3. Cuaderno y anotaciones

Componentes lógicos: StudyEntry, DocumentAnchor, NotebookModel/View, AnnotationReconciler.

- [ ] Cita enlazada + reflexión + etiquetas; notas libres y preguntas; distinguir PDF/cuaderno.
- [x] Guardado automático local con borradores y dos estados de guardado visibles.
- [ ] Índice de anotaciones PDF sin duplicados, invalidación por revisión y anclas huérfanas recuperables.
- [ ] Flujo Guardar copia, solo lectura y conflicto externo; no sobrescribir silenciosamente.
- [x] Exportar Markdown con procedencia y página; eliminar/deshacer.
- [ ] Probar fallos entre escritura PDF y base, reapertura, rotaciones, múltiples ventanas y PDF protegido.

Criterio: nota → reinicio → volver al pasaje; subrayado portable; fallo de una escritura no pierde la otra.

## 4. Traducción y referencias

Componentes lógicos: LookupProvider, LookupController, LookupPanel, ReferenceEntry.

- [x] Investigar proveedores concretos con documentación oficial: ES/EN, API, licencias, costes,
  límites, atribución, privacidad y disponibilidad. Registrar elección; no extraer webs arbitrariamente.
- [x] Adaptador con cancelación, identificador de consulta, timeout y tamaño máximo de respuesta.
- [x] Consentimiento inicial contextual, preferencia revocable y envío mínimo explícito.
- [x] Resultados atribuidos, guardar referencia y abrir fuente con política de URL actual.
- [x] Red ausente, respuesta vacía/malformada, término cambiado, límites y cierre durante consulta.

Criterio: una consulta real atribuida y una prueba sin red; mocks solos no prueban integración online.

## 5. Concentración y repaso

Componentes lógicos: StudySessionController/Store, FocusControls, ReviewView.

- [x] Estado de sesión independiente de los widgets; reloj inyectable y coordinación entre ventanas.
- [x] Pausa, reanudar, descanso, terminar, suspensión, reinicio y cierre de última ventana
  (al cerrar la última ventana pausa sin preguntar).
- [ ] Objetivo y reflexión opcionales; próxima sesión recupera pendiente.
- [x] Repaso pregunta/respuesta y marcas manuales; sin calificar comprensión por páginas recorridas.
- [x] Probar con reloj falso, no esperando pomodoros reales. Probar que el aviso no roba foco.

Criterio: nunca aparecen sesiones activas duplicadas ni tiempos falsos tras suspensión.

## 6. Validación final y entrega al coordinador

Con HOME/XDG temporales, contenido sintético y un proceso de pruebas a la vez:

```sh
QT_QPA_PLATFORM=offscreen /tmp/wysun-pdf-venv/bin/python -m unittest discover -s tests/pdf -v
QT_QPA_PLATFORM=offscreen /tmp/wysun-pdf-venv/bin/python -m unittest tests.test_pdf_theme
/tmp/wysun-pdf-venv/bin/python -m unittest tests.test_theme_literals
git diff --check
```

Preparar HOME/XDG aislados antes de los comandos; ajustar rutas/PYTHONPATH a la migración integrada.
No crear otro venv ni instalar paquetes del host sin necesidad/autorización. La suite usa unittest,
no asumir el comando truncado `pytests/pdf` del handoff. Ampliar comprobaciones según AGENTS y archivos
realmente tocados; no ejecutar medios/compositor en paralelo.

- [x] Extender shots para Biblioteca/Cuaderno/Consulta/Sesión/Ajustes, todas las variantes de tema.
- [~] Verificación manual real de teclado, paneles, cambios de wallpaper en vivo y múltiples ventanas,
  (2026-10-26: modos y selector probados en Hyprland con HOME temporal; wallpaper en vivo y varias ventanas no)
  sin instalar en el escritorio. Registrar por separado lo offscreen y lo verificado en sesión.
- [ ] Medir RSS con biblioteca grande sintética, PDF largo y consultas repetidas; comparar con base
  en la misma máquina. Mantener límites de raster/caché existentes; no prometer rendimiento sin medir.
- [x] Actualizar `docs/pdf-reader.md` con funcionalidades efectivamente implementadas y sus límites.
- [x] Entregar commits, pruebas, capturas y pendientes al coordinador; ningún instalar.sh ni reload.

Comprobación del diseño actual: solo documentos Markdown; no justifica ejecutar suites de runtime.
