# Fondo vivo — diseño

## Intención

El fondo de pantalla deja de ser una imagen quieta y pasa a decir, sin texto ni cifras, cómo está el escritorio: si hay agentes de IA trabajando, si hay VMs encendidas, si suena música, si estás en modo estudio o si algo urgente pide atención. No se genera un fondo nuevo: **es tu propio wallpaper, el que eliges en el carrusel, el que cobra vida**. Así se respeta la regla de Wysun de que el color sale siempre del wallpaper actual, y el resultado se ve como tu escritorio de siempre, solo que respira.

Por qué: los dos mockups anteriores (formas sobre un fondo generado y un campo de color abstracto) parecían un protector de pantalla ajeno al escritorio. Este diseño parte de la imagen que ya elegiste y la anima con efectos sutiles, del tipo que se nota cuando miras el fondo y no estorba cuando trabajas.

## Objetivos

- Que el estado se lea con un vistazo, por sensación: quieto = nada pasa; agua en movimiento = agentes trabajando; luz = VMs encendidas; pulso = música.
- Que sea bonito con cualquier wallpaper (fotos, ilustraciones, abstractos, claros y oscuros).
- Coste casi nulo: cero GPU cuando las ventanas tapan el fondo y presupuesto bajo cuando se ve (ver «Rendimiento»).
- Que se integre con lo que ya existe en el shell, sin procesos nuevos.

## No objetivos

- No genera ni sustituye wallpapers ni toca el carrusel.
- No muestra texto, números, iconos ni figuras dibujadas encima.
- No cambia el esquema Material You: los colores de Wysun siguen saliendo del archivo del wallpaper, no de lo que pinta el efecto.
- No sustituye al visualizador de audio existente (`Visualiser.qml`); conviven.

## Anti-objetivos (fracaso aunque funcione)

- Movimiento que distrae al leer o escribir con el fondo a la vista.
- Bandas de color, parpadeos o saltos al cambiar de wallpaper o de modo.
- Gastar batería o GPU con el fondo tapado.
- Que con un wallpaper concreto se vea feo (deformado, quemado, sucio).

## Las cuatro señales

Todas son efectos sobre la textura del wallpaper en un solo shader de fragmento. Ninguna dibuja formas.

1. **Flujo = agentes trabajando** (`AiUsage.visibleAgents`, los que tienen `busy`). Una refracción muy fina, como agua o aire caliente sobre la imagen: un desplazamiento de las coordenadas de la textura con ruido deformado (domain warping), de amplitud máxima de unos pocos píxeles. Con 0 agentes la imagen queda completamente quieta; con 1 la refracción apenas se percibe y es lenta; con 3 o más es visible y más rápida. Los cambios de nivel se interpolan en ~2 s.
2. **Luz = VMs encendidas** (`CloudVms.vms`). Por cada VM encendida, un resplandor suave en una zona clara de la propia imagen (no en un punto arbitrario). Se eligen las zonas más luminosas del wallpaper una vez por wallpaper, reduciéndolo a una rejilla pequeña. Cada resplandor tiene una deriva y una respiración lentas (periodo ~8 s). Con 0 VMs no hay ninguno. Máximo 6.
3. **Pulso = música** (`Audio.cava.values`, solo las bandas graves). La luminancia de toda la imagen sube y baja muy poco con el bajo (±3 %), con una leve aberración cromática en los bordes de las zonas claras durante los golpes. Sin reproducción activa no hay pulso.
4. **Clima = modo**. Un etalonado de color suave sobre la imagen, sin cambiar el esquema:
   - **Estudio** (`Study.active`): un poco más frío y menos saturado; el flujo se frena a la mitad para no distraer.
   - **Noche** (configurable por hora, por defecto de 22:00 a 6:00): más cálido y ligeramente más oscuro; el movimiento va más lento.
   - **Alerta** (hay una notificación crítica sin atender en `Notifs`): una viñeta roja que late despacio (periodo ~3 s) hasta que la notificación se atiende o se descarta.
   - **Normal**: la imagen tal cual.

Las transiciones entre modos son fundidos de ~1,5 s con las curvas `anim.curves` de los tokens.

## Cómo encaja en el shell

- **Ubicación**: una capa nueva en `apps/shell/modules/background/` entre `Wallpaper` y `Visualiser`, en el `Item` `behindClock` de `Background.qml`. Toma como fuente el visual del wallpaper (`Wallpaper.visual`, el `live`) mediante su propio `ShaderEffectSource`, siguiendo la nota que ya documenta `Wallpaper.qml` sobre no reutilizar `live.layer`.
- **Shader**: `living.frag` junto a los demás en `apps/shell/plugin/src/Wysun/Shaders/` (registrado en su `CMakeLists.txt` y compilado a `.qsb` como los de transición). Recibe como uniforms: el tiempo, el nivel de flujo, hasta 6 posiciones e intensidades de luz, el nivel de graves, los pesos de los cuatro climas y el tamaño de pantalla.
- **Durante una transición de wallpaper** la capa se desactiva (muestra la imagen tal cual) y vuelve cuando `transitionProgress` llega a 1, para no pelear con el shader de transición. Las zonas claras se recalculan para el wallpaper nuevo.
- **Fuentes de datos**: solo servicios existentes (`AiUsage`, `CloudVms`, `Audio`, `Study`, `Notifs`, `Time`). No hay procesos ni sondeos nuevos. `AiUsage` refresca cada minuto mientras hay un agente trabajando; con ese ritmo basta.
- **Ajustes**: un bloque `background.living` en la configuración del shell, con el mismo patrón que `background.visualiser`:
  - `enabled` (por defecto `true`);
  - `intensity` (0–1, por defecto 0.6);
  - un interruptor por señal (`agents`, `vms`, `music`, `modes`);
  - `night` con la franja horaria.
  
  Se expone en Ajustes → Fondo. Ese bloque se declara en el plugin C++ (`apps/shell/plugin/src/Wysun/Config/backgroundconfig.hpp`), igual que `visualiser`, así que hay que recompilar el runtime con `installer/runtime_build.py --jobs 3` (nunca en paralelo con otra compilación) y reiniciar solo el shell. La alerta lee la urgencia de `NotifData` (`NotificationUrgency.Critical`).
- **Movimiento reducido**: con `WYSUN_REDUCED_MOTION=1` (o el ajuste equivalente del sistema) se mantienen el etalonado de los modos y las luces fijas, sin flujo, pulso ni respiración.

## Rendimiento (equipo de referencia: Intel UHD 620, 2 monitores de 1920×1080)

- **Pausa total cuando no se ve**: con la misma regla que ya usa el visualizador (`autoHide`: alguna ventana no flotante en el espacio de trabajo del monitor), el shader deja de animarse y se muestra la imagen fija. También se pausa con la pantalla bloqueada o apagada.
- **Cuadros**: 30 fps como máximo mientras se ve. Si no hay ninguna señal activa (0 agentes, 0 VMs, sin música, modo normal), deja de redibujar.
- **Resolución**: el desplazamiento y las luces se calculan a resolución completa sobre la textura del wallpaper. Si las mediciones superan el presupuesto, el campo de desplazamiento se calcula en una textura auxiliar a 1/4 de resolución y se muestrea escalado (decisión del constructor, guiada por las mediciones).
- **Presupuesto de aceptación**, medido en el equipo de referencia:
  - memoria de Quickshell: +20 MB como máximo frente a hoy (hoy ~640 MB);
  - CPU de Quickshell en reposo con el fondo visible y señales activas: menos del 2 %;
  - con el fondo tapado: uso de GPU indistinguible de tener la función desactivada.

## Calidad visual

- Grano fino (±1/255) para que los degradados no hagan bandas.
- Amplitud del desplazamiento proporcional a la resolución, para que no se vean «costuras» en los bordes. Los bordes se muestrean con clamp.
- Las luces nunca superan el blanco de la imagen: se mezclan en espacio lineal y se comprimen suave, para no quemar los wallpapers claros.
- Probar con al menos 6 wallpapers distintos (claro, oscuro, foto, ilustración plana, abstracto, casi monocromo) y en los cuatro climas, siguiendo la regla de `AGENTS.md` de probar la UI en claro y oscuro con wallpapers de colores distintos.

## Lo que decide el constructor

- La forma exacta del ruido y de la refracción, y las constantes finas, dentro de los límites de amplitud y periodo de arriba.
- El algoritmo para encontrar las zonas claras (por ejemplo, reducir la imagen a 16×9 y tomar los máximos locales).
- La organización interna en QML (un componente o varios) y los nombres de las propiedades.
- Si hace falta la textura auxiliar a 1/4 de resolución, según las mediciones.

## Decisiones tomadas por mí (no consultadas)

- Animar el wallpaper del usuario en vez de generar arte, por la regla de color de `AGENTS.md`.
- Las cuatro señales y su correspondencia (flujo, luz, pulso, clima).
- Que el modo alerta lo dispare una notificación crítica sin atender.
- La franja de noche por defecto (22:00–6:00).
- El presupuesto de rendimiento y la pausa con el fondo tapado.

## Verificación

- Pruebas estáticas en `tests/shell_bridge/` (como las de LanShare y Cloud): la capa existe en `Background.qml`, respeta `enabled` y la regla de pausa, y el shader está registrado.
- Si las correspondencias del estado a los uniforms van en un archivo JS puro, prueba con `node` de esas funciones (de agentes a nivel de flujo, de VMs a luces, de graves a pulso, de modo a pesos).
- `tests/test_theme_literals.py` sin colores literales; los tonos del etalonado salen de tokens nuevos en `tokens.json`.
- Medición en vivo en el equipo de referencia antes de dar la función por terminada: memoria y CPU de Quickshell con la función activada y desactivada, con el fondo visible y tapado.
- Revisión visual con los 6 wallpapers y los 4 climas, capturando solo la salida del monitor de prueba.
