# Modo estudio (pomodoro) para Wysun Shell · diseño

Fecha: 2026-10-31 · Estado: pendiente de aprobación

## Intención

El usuario estudia con papel y con **Lectio** (su lector PDF, `~/repos/pdf`, app id `app.lectio.Lectio`, clase de ventana `lectio`), normalmente en pantalla completa. Quiere sesiones de estudio activas con ritmo pomodoro que:

- **se sientan como entrar en otro estado**: una transición clara y cuidada al empezar;
- **no le provoquen ansiedad**: el tiempo que queda nunca se muestra salvo que lo pida;
- **le quiten distracciones**: durante la sesión solo funcionan las apps que haya permitido;
- **se vean aunque Lectio esté en pantalla completa**.

Las sesiones son libres: no se pide en qué va a trabajar.

## Objetivos

1. Panel de preparación, entrada a pantalla completa, píldora de progreso, descansos, aviso de distracción, salida anticipada y resumen, tal como se describen abajo.
2. Bloqueo de apps no permitidas durante la sesión, reversible y sin perder ventanas.
3. Integración en el shell existente: superficie `study` (`wysun study`), tokens del tema, Material You del wallpaper, claro y oscuro.

## No objetivos

- **No se bloquean webs.** Chrome queda libre, sin listas. No hay extensiones de navegador ni políticas en `/etc`.
- No se pide ni se guarda la tarea o el tema de estudio.
- No hay rachas, logros ni gamificación.
- No hay integración con Lectio más allá de reconocer su ventana (Lectio no cambia).
- No se toca nada del sistema: ni root, ni dependencias del host, ni login.

## Antiobjetivos (cosas que lo harían un fracaso aunque funcione)

- Mostrar una cuenta atrás visible por defecto.
- Cerrar ventanas o perder el trabajo del usuario al bloquear apps.
- Que un fallo del shell deje ventanas escondidas sin forma de recuperarlas.
- Animaciones bruscas, con saltos o "tarjetitas" que aparecen de golpe; el usuario rechazó explícitamente una tarjeta pequeña central durante la entrada y una ventana que "vuela" a la píldora.
- Colores, radios o duraciones literales fuera de los tokens del tema.

## Maquetas de referencia

En `docs/design/modo-estudio/` (HTML interactivo; abrir en un navegador):

- `flujo.html`: flujo completo en 8 escenas. **Válidas**: entrada (3), durante el foco (4), aviso de app bloqueada en la píldora (primera mitad de 5), descanso (6), salir antes (7) y resumen (8). **Ya no válidas**: el panel de preparación que aparece ahí (sustituido por `panel-preparar.html`, opción B) y la página "Esto puede esperar" de la escena 5 (ya no se bloquean webs). En la escena 4, la píldora compacta de esa maqueta usa bloques; la elegida es el anillo ondulado de `pildora.html`.
- `panel-preparar.html`: **opción B (Material 3 Expressive)**, la elegida.
- `pildora.html`: **opción B (anillo ondulado)**, la elegida.

Las maquetas usan los colores del wallpaper que había al hacerlas. En el shell todo sale de `Colours` y `Tokens`.

## Lo que decidió el usuario

### 1. Activación

- `wysun study` (superficie nueva `study` en `apps/shell/wysun/WysunBridge.qml`) y un atajo de teclado.
- Si hay una sesión en curso, `wysun study` despliega la píldora (controles) en lugar del panel.

### 2. Panel de preparación (opción B de `panel-preparar.html`)

Baja desde el borde superior, centrado, como los demás paneles del shell, y oscurece un poco el resto. Sin icono decorativo. Contenido, de arriba abajo:

- Título «Sesión de estudio» (headline small) y una línea de apoyo que **se recalcula en vivo**: «4 bloques de 25 min · descanso largo a mitad», «Bloques de 25 min hasta que pares», etc.
- **Duración**: deslizador M3 Expressive (pista gruesa con huecos junto al tirador, tirador vertical) de 30 min a 4 h en pasos de 30 min, con un último paso «Libre». El valor se muestra a la derecha de la etiqueta.
- **Ritmo**: grupo de botones conectados: 25/5 «clásico», 50/10 «largo» y 90/20 «profundo». El seleccionado se rellena con primary, se redondea del todo y se ensancha un poco con un muelle.
- **Permitido**: chips de filtro M3 (con ✓ al seleccionarlos) con las **apps** permitidas. Por defecto, Lectio y Chrome. «Añadir» permite elegir otra app.
- **Ocultar el tiempo**: interruptor M3 con ✓ en el tirador, activado por defecto.
- Botón grande «Empezar», a todo el ancho.

Se recuerda la última duración, el ritmo y las apps permitidas.

### 3. Entrada (escena 3 de `flujo.html`), unos 3 s

1. Al pulsar Empezar, el botón cambia de forma un instante.
2. **El panel crece hasta ocupar toda la pantalla**, con un muelle suave y las esquinas aplanándose. Es el mismo objeto que crece, no un fundido a otra cosa. El fondo es un degradado de `primaryContainer` hacia la superficie.
3. En pantalla completa: «Modo estudio» en grande, animando el eje de peso de Google Sans Flex de fino a normal y el espaciado de letras de amplio a normal. Debajo, el ritmo («4 bloques · 25 min de foco, 5 de descanso») y los chips de las apps permitidas, que aparecen en cascada con un muelle. Detrás giran despacio dos formas M3 tipo «galleta» (9 y 12 lóbulos) con la onda respirando.
4. Mientras la pantalla está cubierta se aplica el estado de estudio: apps no permitidas escondidas y barra lateral retirada. Lectio, si está abierto, queda delante.
5. **Toda la pantalla se contrae justo hasta la forma de la píldora** (arriba, centrada) con un muelle. Lo que hay debajo se asienta con un ligero zoom hacia atrás.
6. **Una línea de luz recorre todo el borde de la pantalla** una vez, desde arriba en el centro, y deja un **halo tenue** permanente en el borde mientras dura la sesión. Al usuario le gustó especialmente este efecto: es la firma visual del modo.

### 4. Durante el foco: la píldora (opción B de `pildora.html`)

- Arriba en el centro, **en la capa overlay de Hyprland**, para que se vea sobre las ventanas en pantalla completa. El halo también se ve sobre ellas.
- Compacta: **indicador circular ondulado** de M3 Expressive que se llena con el bloque actual (su onda se mueve despacio), el nombre de la fase («Foco», «Descanso» o «Pausa») y en qué bloque vas («1 de 4»). **Nunca minutos**, salvo al pasar el ratón por encima o con el ojo activado.
- Al pasar el ratón **se despliega como tarjeta** con un muelle: bloque actual, barra de bloques, pausa/seguir, saltar al descanso, terminar y un ojo que muestra u oculta los minutos que quedan. Al salir el ratón se recoge.
- En pausa el tiempo se congela, el indicador deja de moverse y el bloqueo sigue.
- Con «Ocultar el tiempo» desactivado, la píldora compacta muestra también los minutos.

### 5. App no permitida

- Si se abre una ventana cuya app no está permitida, **se esconde al momento** y no llega a verse.
- La píldora se alarga con un muelle, **la línea de luz da una vuelta a su contorno** y muestra «⟨App⟩ esperará al final de la sesión», con el icono de la app entrando con un pequeño giro. Unos 2,5 s después vuelve a su tamaño.
- Cada intento suma en «distracciones frenadas».
- Brave, Edge y Firefox son apps no permitidas como cualquier otra (no se tratan de forma especial). Chrome está permitido por defecto.

### 6. Fin de bloque y descanso (escena 6)

- El bloque termina de llenarse, suena un **sonido suave** (debe oírse sin mirar la pantalla) y la píldora da **dos destellos**.
- La píldora se despliega en una **tarjeta de descanso en color terciario** con una sugerencia («Bloque 1 hecho. Levántate, estira, bebe agua.»), una barra que se vacía sin números y «Saltar descanso». Lo que hay detrás se atenúa un poco.
- **El bloqueo sigue durante el descanso.**
- Al acabar el descanso, otro sonido suave y la tarjeta cambia a «¿Seguimos?» con «Empezar bloque N». **El siguiente bloque no arranca solo.** Al pulsar, la tarjeta se recoge en la píldora y la luz del borde da una vuelta más corta.
- Descanso largo a mitad de la sesión cuando hay 4 o más bloques. En modo «Libre», cada 4 bloques.

### 7. Salir antes (escena 7)

«Terminar» no corta en seco: la píldora pregunta «¿Terminar la sesión? Llevas N de M bloques. Lo que has hecho se guarda.» Para salir hay que **mantener pulsado** un botón que se llena de izquierda a derecha (unos 2,5 s); si se suelta, se vacía. «Seguir» cierra la pregunta.

### 8. Final y resumen (escena 8)

- Al acabar el último bloque (o al salir), **la píldora baja y se abre como panel** de resumen: es la entrada al revés. El halo se apaga, la barra vuelve con un muelle y las apps escondidas regresan a su sitio, en cascada.
- Resumen: «Sesión terminada», la fecha, tres datos (bloques completados, tiempo estudiado y distracciones frenadas) y una tira de **esta semana** (tiempo por día, de lunes a domingo). Aquí sí se muestra tiempo, porque es pasado. Botones «Otra sesión» y «Cerrar».

### 9. Movimiento

Muelles de Material 3 Expressive para lo espacial (crecer, contraer, desplegar) y curvas *emphasized* para los efectos: lo que se va acelera y lo que llega frena. Ningún elemento aparece o desaparece de golpe; cada cosa se transforma en la siguiente (panel → pantalla completa → píldora → tarjeta → panel). Las duraciones aproximadas están en las maquetas y deben corresponder a los tokens `anim.*` del esquema 3.

## Restricciones del proyecto (de `AGENTS.md`)

- Todo color, radio, espaciado, tipografía y duración sale de los tokens (`apps/python/wysun_core/tokens.json`, `Colours`, `Tokens`). `tests/test_theme_literals.py` debe seguir pasando. Las excepciones se declaran con `theme-exception: motivo`.
- Hay que probarlo en claro y oscuro y con wallpapers de colores distintos. Un cambio de modo o de wallpaper durante la sesión se aplica en vivo.
- La superficie se añade solo en la lista de `WysunBridge.qml`. No se añaden lanzadores sueltos.
- El atajo se añade en `config/.config/wysun/hyprland.lua` y se migra con cuidado a la configuración activa (`~/.config/wysun/hyprland.lua`), con respaldo, preservando las otras asignaciones y comprobando conflictos. **`SUPER + N` está libre en ambas** (comprobado el 2026-10-31).
- Los datos privados (historial y preferencias) se guardan fuera del repositorio y de `app/`.
- No se reinicia Hyprland ni se cierran apps del usuario para probar. Se despliega con `./instalar.sh --wysun-only`, y si cambió `apps/shell`, se reinicia solo el shell.

## Lo que hay en el código y conviene reutilizar

- **Paneles superiores**: `modules/aiusage/Wrapper.qml` es un cajón que baja desde arriba, abierto por un flag de `components/ScreenState.qml` y montado en `modules/drawers/Panels.qml`. Es el patrón del panel de preparación (en el centro en lugar de a la derecha).
- **Capa overlay**: `components/OverlayWindow.qml` (`WlrLayer.Overlay`) ya se usa para dibujar sobre pantalla completa. La píldora, el halo y la pantalla completa de entrada viven en esa capa. La píldora solo debe capturar el ratón en su propia forma (máscara de entrada), sin bloquear clics al resto.
- **Hyprland**: `services/Hypr.qml` (`dispatch`, Lua o clásico, eventos `onRawEvent`) sirve para detectar ventanas nuevas y moverlas.
- **Persistencia de temporizadores**: `services/Timers.qml` guarda instantes de fin en `${Paths.state}/timers.json` y sobrevive a reinicios del shell. La sesión de estudio debe hacer lo mismo.
- **Sonido**: el shell ya usa `QtMultimedia` (`MediaPlayer` en `modules/launcher/PreviewPane.qml`).

## Decisiones mías (del diseñador; revisables)

- **Dónde se esconden las apps**: en un workspace especial propio (`special:wysun-study`), en silencio. Antes se anota el workspace original de cada ventana para devolverla allí al terminar. No se cierra ninguna ventana.
- **Recuperación ante fallos**: el estado de la sesión (fases, instantes, ventanas escondidas y su origen) se guarda en `${Paths.state}/study.json`. Si el shell se reinicia con una sesión viva, la retoma. Si arranca sin sesión viva y quedan ventanas en `special:wysun-study`, las devuelve. Existe `wysun study stop` (sin pulsación larga) como vía de escape por terminal.
- **Qué nunca se bloquea**: las superficies del propio shell, las apps de Wysun (Music, Files, Settings, Recorder…), los diálogos del sistema (portales, polkit) y las apps permitidas. Una app se identifica por la clase de ventana.
- **Qué ventanas se esconden al empezar**: todas las de apps no permitidas en los workspaces normales de todas las pantallas. Las que el usuario ya tenga en sus propios workspaces especiales no se tocan. `special:wysun-study` no aparece en el ciclo de workspaces especiales del shell (`services/Hypr.qml`) ni en la vista general: durante la sesión no se puede ir a mirarlas.
- **Cómo se impide que se vean**: preferentemente con una regla de ventana añadida en tiempo de ejecución a Hyprland (manda a `special:wysun-study` en silencio todo lo que no esté permitido), que se retira al terminar y desaparece sola si Hyprland se recarga. El shell vuelve a ponerla si la sesión sigue. Si la API Lua de Hyprland 0.55 no lo permite de forma limpia, se reacciona al evento `openwindow` y se acepta un parpadeo de un fotograma.
- **Terminal**: no es una excepción. Se bloquea como cualquier otra app salvo que el usuario la añada a «Permitido». La salida de emergencia sin terminal es la pulsación larga de la píldora. Si el shell muere, `SUPER + Escape` (`wysun recover`, ya existe) lo relanza y el arranque retoma la sesión o devuelve las ventanas. `wysun study stop` sirve desde una TTY o desde una terminal permitida.
- **Cálculo de bloques**: la duración es un objetivo, no un límite exacto. Bloques = máx(1, redondeo(duración ÷ (foco + descanso))). Los bloques nunca se acortan y no hay descanso después del último. Con 4 o más bloques, el descanso tras el bloque ⌈n/2⌉ es largo y sustituye al normal.
- **Descansos largos**: 15 min con 25/5, 20 min con 50/10 y 30 min con 90/20.
- **Modo «Libre»**: sin total. La píldora muestra «Bloque N», la pregunta de salida dice «Llevas N bloques» y como ahí no hay un «antes», **Terminar pide confirmación sin pulsación larga**. El historial guarda los bloques planificados como `null`. El descanso largo llega cada 4 bloques.
- **Entrada y resumen con varias pantallas**: la pantalla completa de entrada cubre todas las pantallas a la vez. En la pantalla con foco se contrae hasta la píldora; en las demás se desvanece y deja el halo. El resumen se abre en la pantalla de la píldora.
- **Sonido**: un tono corto y suave empaquetado con el shell, con licencia libre registrada en `THIRD_PARTY.md`, o generado por nosotros. Volumen moderado, sin bucles.
- **Varias pantallas**: la píldora va en la pantalla con foco al empezar. El halo, en todas.
- **Historial**: una línea por sesión en `~/.local/state/wysun/study/sessions.jsonl` (inicio, fin, ritmo, bloques completados y planificados, minutos de foco y distracciones). Preferencias del panel en `~/.config/wysun/study.json`.
- **«Añadir» app**: abre una lista de las apps de escritorio instaladas (las mismas que conoce el lanzador). Se guarda la clase de ventana de cada una.
- **Ajustes rápidos**: un botón para abrir el modo estudio en el panel de utilidades, si encaja sin rediseñarlo.

## Lo que queda al constructor

- La arquitectura interna (servicio singleton de sesión, módulos QML y reparto entre ventanas overlay), siguiendo las convenciones del shell.
- La forma de dibujar el indicador ondulado y las formas «galleta» (Canvas, Shape o el plugin `M3Shapes` del runtime, que ya existe).
- Las curvas concretas: los tokens `anim.*` más cercanos a las de las maquetas.
- Las pruebas: lógica de sesión (cálculo de bloques y descansos, transiciones de fase, pausa y reanudación, recuperación tras reinicio) con pruebas automáticas; superficie nueva en `tests/shell_bridge`; comprobación visual en claro y oscuro.
