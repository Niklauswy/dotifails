# Wysun Cloud: VMs de Google Cloud en la terminal (y motor TUI de Wysun)

Fecha: 2026-11-04. Paquetes nuevos: `apps/python/wysun_cloud` (la utilidad, `wysun cloud`) y `apps/python/wysun_core/tui` (el motor de terminal reutilizable). Indicador en la barra: `apps/shell`.
Prototipo aprobado (referencia visual y de movimiento): [`2026-11-04-wysun-cloud-prototipo.html`](2026-11-04-wysun-cloud-prototipo.html). Ábrelo en el navegador y usa el teclado.

## Para qué es

El usuario administra VMs de Compute Engine (normalmente 3 proyectos con 2 o 3 VMs cada uno, a veces 1 o 2 proyectos) y entra a la consola web de Google Cloud para cosas rápidas: **encender, apagar, reiniciar y ver cómo van de recursos**. La consola es lenta. Quiere lo mismo desde la terminal, **más rápido**, y poder **diagnosticar cambios**: ver en tiempo real CPU, RAM, disco y red para notar cuándo algo se sale de lo normal.

Hoy entra a las VMs con SSH configurado por `gcloud compute config-ssh` (alias `NOMBRE.ZONA.PROYECTO` en `~/.ssh/config`).

Por ahora **solo VMs**. Redes, Cloud SQL y Cloud Run quedan para más adelante, así que la estructura debe permitir añadir secciones sin rehacerla.

## Objetivos

1. `wysun cloud`: una TUI a pantalla completa con un **mosaico de columnas por proyecto** (variante 1 elegida): una columna por proyecto, una tarjeta en vivo por VM encendida y una línea por VM apagada.
2. **Vista de detalle** por VM con 7 pestañas (Resumen, Procesos, Disco, Red, Servicios, Registro, Historial), como en el prototipo.
3. **Acciones**: encender, apagar y reiniciar, con confirmación para apagar y reiniciar. SSH a la VM en una terminal nueva.
4. **Animaciones** como las del prototipo, celda por celda: entrada escalonada, la tarjeta que crece hasta el detalle y vuelve, pestañas que se deslizan, el diálogo que brota del centro, la tarjeta que se encoge al apagar o crece al encender y empuja a las demás. El usuario lo pidió explícitamente («que se transforme de forma bonita»).
5. **Indicador mínimo en la barra**: no aparece nada si todas las VMs están apagadas. Si hay encendidas, aparece una nube con un punto verde y cuántas son.
6. **Motor TUI propio y reutilizable** por otras utilidades de Wysun, solo con la biblioteca estándar de Python. El usuario lo eligió frente a Textual.

## No objetivos

- Redes, Cloud SQL, Cloud Run, buckets, IAM y facturación (más adelante).
- Crear, borrar o cambiar el tipo de máquina de una VM, y editar el firewall.
- Varias cuentas de gcloud a la vez: se usa la cuenta activa de `gcloud`.
- Instalar algo en las VMs (agentes, scripts residentes).
- Interfaz gráfica (QML o Qt) para esto. La barra solo muestra el indicador.
- Windows o macOS.

## Anti-objetivos (sería un fracaso aunque funcione)

- **Que sea más lento que la consola**: tiene que abrir y mostrar algo útil en menos de un segundo.
- **Apagar o reiniciar por accidente**: siempre con confirmación explícita.
- **Parpadeo** o redibujos que se vean mal en la terminal.
- **Filtrar credenciales**: tokens en registros, errores, caché o salida.
- **Verse genérica**, como un `top` cualquiera. Debe sentirse de Wysun: con el color del wallpaper y movimiento cuidado.
- **Romper la terminal al salir** (modo crudo sin restaurar o pantalla alternativa colgada), incluso si hay un error o un Ctrl+C.

## Decisiones tomadas con el usuario

- Interfaz de **terminal**, no GUI.
- Base: **mosaico, variante 1 (columnas por proyecto)**. El proyecto queda siempre en el mismo lugar.
- **Detalle** al pulsar Enter, con las pestañas del prototipo. Le gustó todo el contenido mostrado.
- **Animaciones** como en el prototipo.
- **Indicador de barra** mínimo, sin panel: no aparece con todo apagado y muestra que hay VMs encendidas cuando las hay.
- **Proyectos dinámicos**: 1, 2 o 3 según los que tenga, sin configurarlos a mano.
- **Recursos en tiempo real por SSH**, sin instalar nada en la VM: los alias de `config-ssh` para las VMs con IP externa y el túnel de Google (`gcloud compute ssh --tunnel-through-iap`) para las demás.
- **`sudo -n`** permitido solo para los comandos de las pestañas que lo necesitan.
- **Motor propio**, sin dependencias, reutilizable en otras utilidades de Wysun.

## Cómo funciona

### Fuentes de datos

| Qué | De dónde | Cuándo |
|---|---|---|
| Proyectos | `gcloud projects list --format=json`, quedándose con los que tienen VMs (un proyecto sin la API de Compute activada se omite sin error). La lista de «proyectos con VMs» se guarda en caché. La búsqueda completa se hace al abrir la TUI como mucho una vez al día, o al pedirla con una tecla. La barra y los refrescos solo consultan los proyectos de esa lista, para que no salga caro si la cuenta ve muchos proyectos | búsqueda completa: diaria o bajo demanda |
| VMs: nombre, estado, zona, tipo, IPs, spot, discos, etiquetas | `gcloud compute instances list --project P --format=json` (los proyectos en paralelo) | al abrir, cada 30 s y justo después de cada acción |
| Encender, apagar, reiniciar | `gcloud compute instances start / stop / reset NOMBRE --zone Z --project P --async`, siguiendo la operación hasta que termine | bajo demanda |
| CPU, RAM, swap, disco, red, carga, núcleos, procesos principales | **una sesión SSH persistente por VM encendida y visible** (`ssh -o BatchMode=yes -o ConnectTimeout=5 NOMBRE.ZONA.PROYECTO sh -s`) que ejecuta un bucle POSIX corto: lee `/proc/stat`, `/proc/meminfo`, `/proc/loadavg`, `/proc/net/dev`, `/proc/diskstats`, `df -P` y `ps`, y emite una línea por muestra | cada 1 s mientras la TUI está abierta |
| Servicios con fallo, contenedores, puertos, journal, lo que más ocupa | comandos por la misma conexión SSH (`systemctl --failed`, `docker ps -a` si existe, `ss -tlnp`, `journalctl -p warning --since -1h`, `du` acotado) | al abrir esa pestaña (`du` solo al pedirlo) |
| Historial de CPU de 24 h y 7 días | API REST de Cloud Monitoring (`compute.googleapis.com/instance/cpu/utilization`, gratis y sin agente), con el token de `gcloud auth print-access-token` | al abrir la pestaña Historial (luego se guarda en caché unos minutos) |
| Quién encendió, apagó o reinició | `gcloud compute operations list --filter=targetLink~NOMBRE` | pestaña Historial |
| Firewall que afecta a la VM | `gcloud compute firewall-rules list` filtrado por la red y las etiquetas de la VM | pestaña Red |
| Discos de GCP y su último snapshot | `gcloud compute disks list` y `snapshots list` filtrados | pestaña Disco |

### Cómo llega el SSH a cada VM

El usuario entra a sus VMs con los alias de `config-ssh` o con `gcloud compute ssh` directo. Solo algunas VMs tienen IP externa. Por eso hay dos caminos (decidido con el usuario):

- **Con IP externa:** el alias `NOMBRE.ZONA.PROYECTO` de `config-ssh`, pasándole además `-o HostName=<IP externa actual según gcloud>`. Así sigue funcionando después de un apagado y encendido, cuando la IP efímera ya cambió. Wysun **nunca** reescribe `~/.ssh/config` ni ejecuta `config-ssh` por su cuenta. Si no existe el alias, se usa el camino siguiente.
- **Sin IP externa** (o sin alias): el túnel de Google, `gcloud compute ssh NOMBRE --zone Z --project P --tunnel-through-iap -- <comando>`. Arranca más lento (unos segundos), pero la sesión de métricas es persistente, así que solo se paga una vez. Para no lanzar `gcloud` en cada comando de pestaña, el constructor puede obtener una vez el comando ssh equivalente (`gcloud compute ssh … --dry-run`) y reutilizarlo, o mantener abierta una conexión maestra (`ControlMaster`) por VM. Lo decide el constructor.
- **Si el túnel falla**, por ejemplo porque falta la regla de firewall de IAP (`35.235.240.0/20` al puerto 22), la tarjeta dice «sin SSH» con ese motivo en una línea.

### Permisos dentro de la VM

Las métricas en vivo (CPU, RAM, disco, red y procesos) se leen como usuario normal, **sin sudo**.

Para los comandos que lo necesitan, se usa **`sudo -n`** (decidido con el usuario), solo en esas pestañas y solo al abrirlas, nunca en el bucle de cada segundo:
- Red: `ss -tlnp`, para ver qué proceso usa cada puerto.
- Registro: `journalctl`.
- Servicios: `docker ps -a`.
- Disco: `du`.

Si `sudo -n` no está permitido en esa VM, se repite sin sudo y lo que falte se marca «necesita permisos». Nunca se pide una contraseña.

Que salga algo en menos de 1 s: el último estado conocido (proyectos y VMs) se guarda en `~/.cache/wysun/cloud/last.json` y se pinta en cuanto la TUI abre, con un indicador «actualizando». Luego se reemplaza por los datos frescos. Las sesiones SSH arrancan en paralelo y cada tarjeta muestra «conectando…» hasta su primera muestra.

Sin SSH (no hay alias, la llave fue rechazada o se agotó el tiempo): la tarjeta muestra el estado de gcloud y el mensaje «sin SSH», con el motivo en una línea («ejecuta `gcloud compute config-ssh`» si falta el alias). El resto de la TUI sigue funcionando. RAM y disco solo vienen por SSH (o con Ops Agent en Monitoring, si la VM lo tuviera; leerlo es opcional y queda a criterio del constructor).

### Credenciales

Se aplica la regla de `AGENTS.md`. Wysun no guarda ni lee archivos de credenciales: usa `gcloud` y `ssh` tal como los tiene configurados el usuario. El token de Monitoring se pide a `gcloud auth print-access-token` justo antes de cada consulta, viaja solo por HTTPS a `monitoring.googleapis.com` y **nunca se escribe, se cachea, se registra ni aparece en errores**. Lo comprueba una prueba con un token sintético. El agente que lo construya **no ejecuta** comandos que impriman tokens reales.

### Pantallas

Todo según el prototipo, que es la referencia de disposición, contenido y movimiento. El ancho del prototipo es de 120 columnas. La TUI se adapta al tamaño real de la terminal y al cambiarlo.

**Mosaico (inicio):**
- **Cabecera:** el nombre «☁ Wysun Cloud», cuántas VMs hay encendidas y apagadas, el costo aproximado por hora y la antigüedad de los datos.
- **Columnas:** una por proyecto, con el nombre del proyecto arriba.
- **Tarjetas de las VMs encendidas:** CPU de los últimos 2 min en braille (2 filas), RAM, disco `/`, red, tiempo encendida, el proceso que más consume y alertas (un servicio con fallo, disco > 85 %).
- **Líneas de las VMs apagadas:** una por VM, al final de su columna.
- **Selección:** un borde de color en la tarjeta o un fondo en la línea.
- **Pie:** los atajos.
- **Adaptación:** con 1 o 2 proyectos, las columnas se ensanchan (o un proyecto reparte sus VMs en varias columnas). Si la terminal es estrecha, las columnas se apilan. Lo decide el constructor; debe verse bien en 80 columnas y en 200.

**Detalle:**
- **Cabecera:** el camino «mosaico › proyecto › VM».
- **Línea de datos:** tipo, zona, IP externa e interna, sistema, tiempo encendida y costo.
- **Pestañas:** con insignias (● si hay un servicio con fallo, el número de errores en el journal).
- **Resumen:** CPU de 2 min (6 filas), cada núcleo, RAM con caché y swap, cada partición con lectura y escritura, red de bajada y subida, los 5 procesos principales y un bloque de Salud.
- **Procesos:** la tabla completa, ordenable por CPU o RAM. Terminar un proceso (`k`) queda fuera de la primera versión; si se hace, con confirmación.
- **Disco:** particiones con inodos y lectura y escritura, «lo que más ocupa» (`du`, bajo demanda) y los discos de GCP con su último snapshot.
- **Red:** gráficas de la interfaz, puertos abiertos (resaltando los expuestos a `0.0.0.0`), reglas de firewall (avisando de las abiertas a `0.0.0.0/0` fuera de 22, 80 y 443) y conexiones.
- **Servicios:** systemd (primero los que fallan) y contenedores docker.
- **Registro:** el journal con prioridad de advertencia o peor de la última hora. Con `l` se sigue en vivo.
- **Historial:** CPU de 24 h y 7 días (`h` alterna) desde Monitoring, con marcas de las operaciones de GCP y la lista de esas operaciones.

**Acciones:**
- `s` enciende (en una VM apagada), `x` apaga y `r` reinicia (reset).
- Apagar y reiniciar abren el diálogo de confirmación: Enter confirma y Esc cancela. El diálogo dice qué pasará (el disco se conserva, la IP efímera cambia, el reset es forzado) y, si hay datos por SSH, cuántas sesiones SSH hay abiertas.
- Mientras la operación sigue, la tarjeta muestra un giro (`◐◓◑◒`) con «apagando…», «encendiendo…» o «reiniciando…».
- Al terminar aparece un aviso breve («api-backend apagada»).
- Si la operación falla, el aviso lleva el error de gcloud resumido y la tarjeta vuelve a su estado real.
- `c` (o Enter en la línea de datos del detalle) abre `ssh ALIAS` en una terminal nueva. Se usa la misma lista de terminales que Files (`TERMINALS` en `wysun_files/quick/operations.py`; conviene moverla a `wysun_core` para compartirla).
- `/` filtra por nombre, `?` muestra la ayuda y `q` sale (en el detalle, Esc o `q` vuelve al mosaico).
- El ratón sirve para elegir (clic), abrir (doble clic) y cambiar de pestaña (clic en la pestaña).

**Costo aproximado:** una tabla incluida de precios bajo demanda por tipo de máquina y región, aproximada y marcada con «≈». Si el tipo no está en la tabla, no se muestra. Las spot y las apagadas no suman. Es una idea mía que al usuario le gustó en el prototipo; no hace falta que sea exacta.

### Animaciones

- Como en el prototipo: todo se mueve por **celdas enteras** (rectángulos interpolados y redondeados a la celda) y los desvanecidos **mezclan el color** del texto con el fondo por pasos.
- Las duraciones y curvas salen de los tokens (`anim.durations`, `anim.curves` de `tokens.json`; las curvas de varios tramos se aproximan con el primero, como hace LANShare en CSS).
- Correspondencia aproximada:
  - Tarjeta que crece o se encoge: `expressiveDefaultSpatial` / `emphasizedDecel`.
  - Desvanecidos: `expressiveFastEffects`.
  - Deslizamiento de las pestañas: `small`.
  - Diálogo: `expressiveFastSpatial`.
  - Reacomodo al encender o apagar: `normal`.
  - El constructor ajusta lo que haga falta para que se sienta como el prototipo.
- Hasta 60 cuadros por segundo mientras algo se anima. En reposo solo se redibuja cuando llegan datos (unas pocas veces por segundo como mucho).
- Mientras se anima, las teclas no se pierden: se encolan o, si una lleva a otro estado, se adelanta la animación hasta el final.
- Con `WYSUN_REDUCED_MOTION=1`, o si la terminal no da la velocidad, los cambios son instantáneos. Esta salvaguarda es una decisión mía.

### Tema

- La TUI usa **color real (24 bits)** con los roles Material del esquema actual, leídos con `wysun_core.theme` (sin Qt): `scheme.json` del wallpaper y el modo de `theme.json` (`auto`, `light` o `dark`).
- Un cambio de wallpaper o de modo se aplica **en vivo**: la TUI revisa `theme.revision()` cada segundo o dos y repinta. AGENTS.md lo exige para toda UI de Wysun.
- El fondo de la TUI es el `surface` del esquema, no el de la terminal, para que se vea igual en cualquier terminal.
- **Excepción declarada:** los colores de estado (correcto, aviso, error) son semánticos y salen de los tokens (`success` / `warning` / `error`, o de los roles más cercanos). Nunca son literales en el código.
- Sin color real (sin `COLORTERM=truecolor|24bit`), se degrada a 256 colores.

### Indicador en la barra

- **Servicio** en `apps/shell/services/` y entrada en los iconos de estado de la barra, como LANShare. No necesita reconstruir el plugin.
- **Fuente:** el estado lo publica `wysun cloud --estado`, que consulta gcloud una vez, escribe `<runtime dir>/wysun-cloud/state.json` (privado y de forma atómica) y termina.
  - La barra lo lanza cada **2 min**, y vigila el archivo para repintar en cuanto cambia.
  - La TUI abierta también escribe ese archivo cada vez que refresca la lista o termina una acción, así la barra se entera al instante.
- **Vista:** con 0 VMs encendidas (o sin datos) no aparece nada. Con 1 o más, una nube con un punto verde y el número. Al pasar el ratón, los nombres de las encendidas por proyecto.
- **Clic:** abre `wysun cloud` en una terminal nueva. Es una propuesta mía que el usuario no ha rechazado.
- **Sin gcloud o sin sesión de gcloud:** el indicador no aparece y no muestra errores.
- **Colores y medidas:** de los tokens del shell, probados en claro y oscuro.

### El motor TUI (`wysun_core.tui`)

Biblioteca pequeña, sin dependencias, pensada para reutilizarse en otras utilidades. La parte de Google Cloud no entra en el motor. Debe cubrir:

- **Terminal:** pantalla alternativa, modo crudo (`termios`/`tty`), cursor oculto, ratón SGR, pegado entre corchetes y cambio de tamaño (`SIGWINCH`). Restaura todo al salir, con error, Ctrl+C o SIGTERM (y también si el proceso termina por una excepción).
- **Entrada:** un intérprete de secuencias de teclas (flechas, Fn, Alt, Ctrl), clics, rueda y arrastre, que entregue eventos limpios.
- **Lienzo:** una cuadrícula de celdas (carácter, color de frente y fondo, negrita, etc.). Cada cuadro se compone en un búfer nuevo y se escribe **solo la diferencia** con el anterior, en una sola escritura (sin parpadeo; usa la actualización sincronizada `CSI ? 2026` donde la terminal la soporte).
- **Capas:** z-order, rectángulos con opacidad (mezcla hacia el color de fondo), recorte y desplazamiento.
- **Piezas de dibujo:** caja con borde redondeado y título, texto con estilos, gráfica braille de N filas, barra con fracciones (`▏▎▍▌▋▊▉`), barra de pestañas, tabla, diálogo, aviso y giro.
- **Animación:** interpolación con las curvas de los tokens, rectángulos redondeados a la celda, desvanecidos por pasos y un reloj de cuadros que solo corre mientras algo se anima.
- **Tema:** roles de color desde `wysun_core.theme`, recarga en vivo y degradado a 256 colores.
- **Bucle:** uno solo, con `selectors`, para la entrada, los temporizadores y los procesos hijos (las sesiones SSH y gcloud), sin hilos salvo que hagan falta.
- **Probable sin terminal:** pantalla virtual en memoria para pruebas (renderizar, mandar teclas y comparar el texto o las celdas resultantes).

Cómo se organiza por dentro (widgets o funciones de dibujo, nombres de clases) queda a criterio del constructor. Que sea pequeño y claro importa más que la generalidad. Lo de Cloud vive en `wysun_cloud` y usa el motor; no al revés.

## Restricciones

- **Solo biblioteca estándar** (decisión del usuario). Los programas externos son los que ya tiene: `gcloud` y `ssh`.
- **Estructura de una utilidad Wysun** (`docs/utilities.md`):
  - `apps/python/wysun_cloud/` con `__main__.py`.
  - La entrada `'cloud'` en `MODULES` de `bin/wysun` y una línea en su ayuda.
  - El paquete en `PACKAGES` de `tests/test_python_layout.py`.
  - Una prueba en `tests/shell_bridge/test_dispatcher.py`.
  - Una sección en `docs/utilities.md`.
- **Datos fuera del repositorio:**
  - Caché en `~/.cache/wysun/cloud/`.
  - Configuración opcional en `~/.config/wysun/cloud.json`, por ejemplo para fijar proyectos u ocultar alguno. Por defecto no hace falta.
  - Estado de la barra en el directorio de ejecución de la sesión.
- **Nombre:** solo «Wysun» (`tests/test_legacy_names.py`).
- **Colores:** sin literales (`tests/test_theme_literals.py`); las excepciones llevan `theme-exception: motivo`.
- **Despliegue:** con `wysun update`, después de probar. Si cambia `apps/shell`, se reinicia solo el shell.
- **Pruebas sin la nube real:**
  - Los comandos externos se simulan: `gcloud` y `ssh` falsos en un `PATH` temporal, con salidas grabadas en `tests/fixtures`, y HOME/XDG temporales.
  - El bucle de métricas por SSH se prueba ejecutándolo localmente con `sh` sobre un `/proc` de muestra cuando se pueda, o validando su salida con muestras grabadas.
  - El agente no apaga ni enciende VMs reales del usuario sin que el usuario lo pida.

## Lo que queda al constructor

- La API interna del motor y cómo divide los módulos.
- El formato exacto de la línea que emite el bucle SSH y el bucle mismo (que sea POSIX `sh`, que funcione en Debian y Ubuntu y que cueste poco en la VM).
- La tabla de precios y su formato.
- Cómo se reparten las columnas con 1 o 2 proyectos y en terminales estrechas.
- Los mensajes exactos de error y vacío (en español, como el resto de Wysun).
- Cómo cachear las respuestas de Monitoring y gcloud dentro de los intervalos indicados.

## Decisiones mías (revísalas)

- Nombre `wysun cloud` y paquete `wysun_cloud`, porque luego vendrán más servicios además de las VMs.
- El motor vive en `wysun_core.tui`, la base compartida.
- Refrescos: lista cada 30 s con la TUI abierta y cada 2 min para la barra; métricas SSH cada 1 s.
- El indicador abre la TUI al hacer clic.
- Costo aproximado con una tabla incluida.
- Sin la tendencia de llenado de disco (el «~3 GB/día» del prototipo): sin Ops Agent no hay historial de disco. Se avisa solo por encima del 85 %.
- Terminar procesos (`k`) queda fuera de la primera versión.
- `WYSUN_REDUCED_MOTION=1` desactiva las animaciones.
- El alias de SSH se usa con la IP actual de gcloud (`-o HostName=…`), sin tocar nunca `~/.ssh/config`.
- La lista de «proyectos con VMs» se guarda en caché y se vuelve a buscar una vez al día o al pedirlo.
