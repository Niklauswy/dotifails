# Wysun PDF: espacio de estudio

Estado: propuesta de producto, pendiente de revisión visual con el usuario. No implementada.
Base comprobada: `main`, `bc7f920d`, 2026-10-25. Sin cambios de runtime, renombres o despliegue.
Decisión del usuario: consultas en un panel integrado; navegador externo para profundizar.

## 1. Propósito

Abrir la aplicación debe responder «¿qué estaba estudiando y cómo continúo?». Leer es parte de
un ciclo: retomar → comprender → anotar → consultar → explicar con palabras propias → repasar.
La primera versión completa debe cubrir ese ciclo sin cuentas ni servicios obligatorios.

Conservar Wysun PDF como nombre y `wysun pdf` como comando. «Espacio de estudio» describe su
función; no se propone renombrar el producto ni sus módulos durante la migración `wysun_pdf`.

La base técnica ya tiene lectura continua virtualizada, zoom, doble página, búsqueda, selección,
anotaciones PDF y posición recordada. La captura existente `../superpowers/specs/pdf-shots/base-light-reader.png`
muestra una cabecera llena de herramientas, miniaturas dominantes y controles contextuales solo
con iconos. El nuevo diseño prioriza el texto, explica las acciones y hace visible el trabajo de estudio.

## 2. Navegación y pantallas

### Inicio / Biblioteca

Abrir sin argumentos muestra Biblioteca. Abrir un archivo desde Files o CLI llega directamente
a la lectura. No interponer un asistente. Biblioteca reúne:

- **Continuar**: una lectura principal, capítulo/página, última pregunta pendiente y botón «Continuar lectura».
- **Recientes**: filas con portada pequeña, título, autor si existe, última apertura y página alcanzada.
  El avance significa posición, no comprensión ni porcentaje realmente leído.
- **Colecciones**: agrupaciones manuales, por ejemplo «Filosofía política». Un libro puede estar en varias.
- **Abrir PDF**, búsqueda por título/autor y acceso discreto a Ajustes.

Sin archivos: «Tu espacio para leer, entender y volver a tus ideas», Abrir PDF y pista de arrastre.
Sin resultados: conservar la consulta y ofrecer limpiar filtros. Archivo ausente: «Localizar archivo»
o «Quitar de recientes»; no borrar el cuaderno ni el archivo. No escanear el disco ni importar carpetas
sin una acción explícita. Recientes y colecciones referencian originales, no los copian.

### Lectura

Cabecera: Biblioteca · título/capítulo · Buscar · Lectura · Concentración · Cuaderno · menú.
«Lectura» agrupa zoom, ancho/página y una/dos páginas. Guardar PDF aparece como acción clara
cuando hay cambios; el estado «PDF sin guardar» permanece visible. No ocultarlo solo tras un punto.

Documento al centro. Índice y páginas se abren a la izquierda bajo demanda; el índice es la primera
opción cuando existe. Cuaderno/Consulta comparte una única columna derecha. En una ventana
estrecha solo se muestra un panel lateral a la vez; abrir otro conserva su estado. El documento
mantiene su ancla al cambiar el espacio disponible. El panel no se superpone a una selección activa.

La barra de selección ofrece **Resaltar · Subrayar · Nota · Consultar**, con texto además de iconos;
Copiar y color quedan en el menú de acciones cuando falta ancho. Consultar ofrece Traducir y Concepto.
La nota de selección abre el editor lateral, con la cita ya vinculada. La nota libre del cuaderno
también puede vincularse a la página actual. La nota colocada dentro del PDF sigue disponible.

Modo concentración oculta navegación y paneles, mantiene salida accesible, posición y estado de
guardado. No inicia un pomodoro automáticamente. Esc cierra primero el elemento transitorio activo;
si no hay editor/menú/selección, sale de concentración. Nunca descarta una nota al pulsar Esc.

### Cuaderno

Dos ámbitos explícitos: «Este libro» y «Todos mis libros». Pestañas con nombre: Notas, Preguntas,
Referencias. Filtros por capítulo, etiqueta y tipo; buscar en el cuaderno es distinto de Ctrl+F en el PDF.

Cada entrada tiene cita opcional, reflexión propia, página, etiquetas y «Volver al pasaje».
Las anotaciones PDF importadas aparecen identificadas como tales, sin duplicar el texto al guardar.
No usar el color como única clasificación: una pregunta tiene etiqueta e icono aunque cambie el wallpaper.
Acciones: editar, convertir nota en pregunta, exportar y eliminar con deshacer.

Repaso inicial: mostrar la pregunta, permitir pensar o escribir y pulsar «Ver mi respuesta»; después
«Volver a estudiar» o «Entendido». No añadir un algoritmo de repetición espaciada en esta entrega.
Exportar Markdown con citas, página del PDF y referencias; nunca inventar numeración impresa, autor
o edición. Incluir los campos bibliográficos solo si existen o el usuario los completó.

### Consulta

Se abre junto al pasaje y conserva selección/posición. Cabecera con término editable, idioma de origen
y destino (ES/EN, intercambiables); pestañas Traducción y Concepto. El resultado siempre muestra
proveedor/fuente, URL cuando proceda y acción «Guardar en cuaderno». «Abrir fuente» usa el navegador.

Traducción distingue término, alternativas y contexto disponible. Concepto presenta referencias
atribuidas, no una respuesta editorial sin procedencia. En filosofía y política, distinguir acepciones
y autores si la fuente los proporciona. No simular consenso ni generar definiciones sin un proveedor.

Contrato de proveedor pendiente de implementación: consulta asíncrona cancelable, timeout, límite
de respuesta, idioma, título, URL y texto; errores normalizados. Elegir servicios y comprobar licencias,
costes, límites y disponibilidad antes de integrarlos. No se promete un traductor offline.

No enviar una selección al marcar texto: solo al pulsar Consultar. En la primera consulta online mostrar
proveedor y contenido que se enviará; recordar la elección y permitir revocarla en Ajustes.
Enviar únicamente el término/fragmento solicitado; ampliar contexto es una acción explícita.
Estados completos: sin proveedor, cargando, sin resultados, sin red, error, cancelado y resultado.
Cambiar de término invalida la respuesta anterior. Sin red siguen funcionando lectura, notas y referencias
guardadas. No cargar HTML remoto ejecutable: texto y enlaces validados. Sin WebEngine residente.

### Sesiones de concentración

Acción «Concentración» ofrece modo de lectura y temporizador, diferenciados. Pomodoro propuesto:
25 minutos de estudio, 5 de pausa, descanso largo de 15 tras cuatro bloques; editable, sin iniciar
ninguna sesión solo por abrir un libro. Objetivo opcional: «Comprender el argumento del capítulo 2».

Durante la sesión aparece una cápsula discreta «18:42 · Pausar». Al terminar, aviso no modal con
«Descansar», «Seguir leyendo» y «Cerrar sesión». No tapar el pasaje, cerrar el archivo ni robar el foco.
Al cerrar una sesión: resumen opcional «Qué entendí / Qué queda pendiente», enlazado al libro.
El inicio de la siguiente sesión recupera esa pregunta. Sin rachas, rankings ni obligación de cumplir metas.

Máquina de estados: inactiva → estudio ↔ pausada → descanso → estudio; finalizar desde cualquier estado.
Usar tiempo transcurrido monotónico, no contar ticks de QTimer. Tras suspensión o reinicio, recuperar
como pausada/interrumpida y pedir reanudar; no acreditar tiempo no observado como estudio.
Una sesión activa por usuario mediante coordinación entre ventanas; nunca varios temporizadores
independientes escritos sobre el mismo estado. Cerrar la última ventana termina o pausa con elección
explícita. No mantener un daemon por esta función.

### Ajustes

- Lectura: ajuste inicial, una/dos páginas y paneles recordados; papel original sin recoloreado automático.
- Concentración: duraciones, avisos y sonido opcional.
- Consultas: ES/EN, proveedor, permiso de envío y borrado de caché.
- Datos: recordar recientes, limpiar recientes, exportar cuaderno, eliminar datos de estudio por separado.
- Apariencia: seguir Material You del escritorio; abrir su configuración de modo. No crear paletas
  propias. Migrar la preferencia antigua del lector con respaldo sin cambiar globalmente el modo.
- Atajos y ayuda accesibles sin documento.

## 3. Wireframes funcionales (no maquetas visuales finales)

```text
BIBLIOTECA
┌────────────────────────────────────────────────────────────────────┐
│ Wysun PDF                       Buscar en biblioteca    Abrir PDF  │
├─────────────┬──────────────────────────────────────────────────────┤
│ Biblioteca  │ Continúa donde lo dejaste                            │
│ Cuaderno    │ La república · Libro II · página 42                  │
│             │ Pendiente: ¿qué entiende aquí por justicia?          │
│ Colecciones │ [Continuar lectura]                                  │
│ + Crear     │                                                      │
│             │ Recientes                         Todos / En estudio │
│             │ portada  Título · autor         p. 42     Hace 2 h   │
│             │ portada  Título · autor         p. 18     Ayer       │
│ Ajustes     │                                                      │
└─────────────┴──────────────────────────────────────────────────────┘

LECTURA CON CUADERNO
┌────────────────────────────────────────────────────────────────────┐
│ Biblioteca  La república   Buscar  Lectura  18:42  Cuaderno  ⋮     │
├──────────────────────────────────────────┬─────────────────────────┤
│ Índice ▸                                 │ Cuaderno · Este libro   │
│          LIBRO II                         │ Notas Preguntas Fuentes │
│                                          │                         │
│          Texto del documento             │ Cita · p. 42            │
│          pasaje seleccionado             │ «Fragmento…»            │
│     [Resaltar Subrayar Nota Consultar]   │ Mi interpretación…      │
│                                          │ [Volver al pasaje]      │
│          Texto del documento             │                         │
│                                          │ + Añadir reflexión      │
│            Página 42 / 320                │ Cuaderno guardado       │
└──────────────────────────────────────────┴─────────────────────────┘

CONSULTA (sustituye el contenido del panel derecho)
┌───────────────────────────────┐
│ ← Cuaderno   Consulta     ×   │
│ justice                       │
│ Inglés → Español       ⇄     │
│ Traducción | Concepto         │
│ Resultado del proveedor       │
│ Fuente · idioma               │
│ [Guardar] [Abrir fuente]      │
│ Vinculado a página 42         │
└───────────────────────────────┘
```

El contenido de estos ejemplos es ilustrativo: no es texto extraído de un libro ni una definición.

## 4. Dirección visual y kit

Material You, superficies tonales tranquilas, una acción principal por vista. Inicio con título grande
y lista legible; lectura con poco chrome; cuaderno con separación por espacio y divisores, sin tarjetas
dentro de tarjetas. Portadas pequeñas, sin ilustraciones decorativas dominantes ni estadísticas enormes.

| Elemento | Base existente / contrato |
|---|---|
| Ventana | `FramelessResize`, `WindowMotion` |
| Navegación | `NavItem`, `Panel`; mantener nombres visibles |
| Acciones | `PillButton`, `IconButton`, `Chip`, `StateLayer` |
| Búsqueda y títulos | `SearchField`, `ElidedLabel`, `text_font` |
| Avisos | `Toast`; errores persistentes cerca de la acción que falló |
| Geometría | `metric`, `rounding.*`, `spacing.*`, `padding.*`, `border.width/focus` |
| Texto | `title.large`, `body.medium/small`, `label.small`; puntos, Google Sans Flex |
| Tiempo | `mono.*`, CaskaydiaCove; no aumentar el tamaño al iniciar |
| Colores | roles existentes `surface`, `text`, `muted`, `accent`, `on_accent`, `focus` |
| Movimiento | `anim.durations.*`, `qt_theme.easing`, preferencia de movimiento reducido |

Si falta una métrica de componente, incorporarla al kit compartido tras la consolidación de etapa 1,
no construir otro kit PDF. Las recomendaciones numéricas de skills no reemplazan los tokens del proyecto.
Los colores del papel, imágenes PDF y marcadores elegidos por el usuario son contenido y requieren
excepción documentada cuando corresponda. No usar imágenes rasterizadas de texto para implementar UI.

Diseño adaptable por mínimos calculados desde fuente, tokens y área de lectura: reducir paneles antes
que el texto. Verificar 1280×800, 1024×768 y 720×480, escala de fuente aumentada y DPI distintos.
Teclado completo, foco visible y retorno del foco al cerrar paneles. Los controles sin texto tienen nombre
accesible y tooltip. Sin animaciones de entrada repetidas al seleccionar cada palabra.

## 5. Persistencia y compatibilidad

`positions.json` conserva claves hash y se migra solo cuando se abre una ruta conocida: no se pueden
reconstruir recientes a partir de hashes. Biblioteca empieza con las aperturas nuevas y ofrece añadir
archivos. No afirmar que se recuperó un historial inexistente.

Propuesta: SQLite local versionada en `paths.data('wysun', 'pdf-reader', 'study.sqlite3')`, directorio
0700 y base 0600, con I/O integrado mediante las abstracciones de `wysun_core`. Tablas: documentos,
colecciones, pertenencias, entradas, referencias y sesiones. Documentos con UUID, ruta local, título,
huella, última apertura y estado manual de estudio. Es necesario guardar rutas para reabrir recientes;
esta es una diferencia explícita frente al almacén de posiciones. No es cifrado en reposo.

Las entradas usan UUID y ancla: documento, página, quads originales, cita y contexto corto, revisión
del archivo. `xref` puede ayudar pero no es identidad estable tras reescrituras externas. Si no se
puede reconciliar un ancla, conservar la nota como «Pasaje pendiente de localizar», sin enlazarla a
texto equivocado. Un archivo movido se vuelve a asociar por acción del usuario y verificación de huella.
Guardar copia crea identidad nueva; ofrecer copiar cuaderno, sin trasladarlo silenciosamente.

PDF nativo es fuente de verdad para sus anotaciones; SQLite para reflexiones, referencias y sesiones.
Cuaderno se guarda automáticamente, PDF mantiene guardado explícito y protección ante cambios externos.
Mostrar estados separados. No afirmar atomicidad entre ambos archivos: operaciones enlazadas llevan
identificador y estado pendiente, reconciliación tras fallo y opción de reintentar; no duplicar anotaciones.
Notas no confirmadas se conservan como borrador recuperable. Sin guardado automático sobre un PDF protegido.
En solo lectura se permite cuaderno local, pero se desactivan anotaciones PDF.

Varias ventanas: transacciones, control de revisión por entrada y notificación de cambios; nunca
sobrescribir el texto de un editor abierto por una actualización de otra ventana. Bloqueos con espera
acotada fuera del hilo UI. Cambios de esquema con respaldo, migración transaccional y recuperación.
Miniaturas solo a demanda en caché acotada, sin precargar todos los libros ni abrir un worker por fila.

## 6. Criterios de aceptación

1. Abrir sin archivo muestra recientes; Continuar restaura pasaje y pregunta, incluso tras reiniciar.
2. Seleccionar texto → nota → guardar → cerrar → reabrir → volver al pasaje conserva contenido y ancla.
3. Subrayado guardado sigue visible en otro lector; el cuaderno no depende de modificar el PDF.
4. Consultar ES/EN no pierde selección; cancelación y fallo de red no bloquean lectura.
5. Referencia guardada conserva fuente, URL, fecha, término e idioma; sin proveedor no hay resultado ficticio.
6. Pomodoro permite pausar y recuperar una interrupción sin acreditar minutos inventados ni duplicarse.
7. Repaso abre una pregunta y revela la respuesta solo a petición; exportación conserva procedencia.
8. Archivo movido, PDF protegido, estado corrupto y cierre durante fallo del motor tienen salida clara.
9. Navegación y edición funcionan con teclado; no hay controles cortados en ventana pequeña.
10. Capturas claras/oscuras y wallpapers teal/amber muestran contraste, jerarquía y foco verificables.

## 7. Límites de esta entrega de diseño

No modifica código, ni prueba nuevas pantallas inexistentes, ni despliega. Se revisaron fuente del kit,
persistencia/ventana/arranque actuales, documentación técnica y una captura anterior en claro.
Pendiente: maquetas Qt con el kit consolidado, revisión visual de esas pantallas, selección/verificación
de proveedores y ejecución de pruebas de la implementación. EPUB/reflow, OCR, IA generativa, sincronización,
WebEngine y repetición espaciada avanzada quedan fuera de la primera versión.

Plan ejecutable: [2026-10-25-pdf-study-plan.md](2026-10-25-pdf-study-plan.md).
