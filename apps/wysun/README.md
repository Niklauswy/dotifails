# Wysun

Lanzador nativo y local para BSPWM, inspirado en la interacción de Raycast.
No es Raycast ni incluye su tienda de extensiones, IA de pago o integración con calendarios.

## Uso

- **Super + Espacio / Super + D**: buscar aplicaciones, acciones y calcular.
- **Super + V**: historial del portapapeles con texto, imágenes, colores y enlaces.
- **Super + C**: calculadora con historial y conversiones (por ejemplo `10 km a mi`, `15% de 80`).
- **Super + Alt + F**: archivos y vistas previas de imágenes, texto, PDF y vídeo.
- **Super + Alt + S**: snippets. Crear con Ctrl + N y editar desde Ctrl + K.
- **Super + L**: emoji.
- **Alt + 1 … 5**: cambiar de sección dentro del lanzador.
- **Enter**: abrir o copiar; **Ctrl + Enter**: copiar y pegar en la ventana anterior si sigue enfocada.
- **Alt + K / Ctrl + K**: acciones contextuales del elemento.
- **Ctrl + Espacio**: vista ampliada de archivos e imágenes del historial; reproductor para vídeo y audio.
- **Escape**: limpiar búsqueda, volver al inicio, cerrar.

Los snippets se buscan por nombre o abreviatura. Admiten `{date}`, `{time}` y `{datetime}`.
No expanden texto globalmente mientras escribes en otras aplicaciones.

## Datos y privacidad

El historial comienza con las nuevas copias; no importa el historial de otras herramientas.
Se almacena localmente en `~/.local/share/orbit/orbit.sqlite3` con permisos 600, directorio 700.
Retención: 7 días y 200 elementos recientes. Hasta 50 elementos fijados quedan fuera de la caducidad. Las imágenes no fijadas se purgan cuando el conjunto supera 64 MB. Texto máximo 64 KB, imagen comprimida máximo 4 MB.
No hay telemetría, cuentas ni sincronización. Las búsquedas web solo salen a Internet al seleccionarlas. Para mostrar iconos de enlaces HTTPS, Wysun puede consultar `/favicon.ico` directamente en el dominio público del enlace, sin enviar su ruta ni parámetros. No consulta servicios externos de favicons.
Se excluyen formatos de gestores de contraseñas y patrones reconocibles de claves; no es un detector infalible.
Pausa el historial con el botón inferior antes de copiar información sensible. Clic derecho en «Historial activo» o el comando «Opciones del historial» permite administrar y borrar el historial.

La búsqueda de archivos usa nombres, rutas y texto reconocido en imágenes mediante OCR local. Omite carpetas ocultas y dependencias, con un límite de 100.000 archivos. El catálogo se actualiza en segundo plano al volver a archivos después de 5 minutos. No indexa el contenido de documentos de texto, PDF ni audio.
El índice OCR empieza al abrir Archivos, procesa primero las imágenes más recientes y continúa en segundo plano, una imagen a la vez. El botón «OCR» muestra el progreso y permite pausar/reanudar; esta preferencia se conserva. Los resultados por contenido aumentan conforme avanza el índice. Las miniaturas y el texto se guardan con permisos privados en `~/.local/share/orbit/file-media.sqlite3`; se invalidan si cambia o desaparece el archivo. No se envían imágenes a servicios externos. Se omiten SVG, imágenes excesivamente grandes, formatos no decodificables y texto con patrones reconocibles de secretos.
Las vistas previas de documentos leen únicamente el archivo seleccionado. PDF y vídeo usan Poppler y FFmpeg locales; la reproducción integrada utiliza mpv y comienza en pausa.

## Operación

`~/.local/bin/orbit` activa el proceso residente por un socket privado. No arranca otro intérprete Qt en cada atajo.
`~/.local/bin/orbit daemon` inicia el residente sin mostrarlo. La sesión de Wysun lo inicia al entrar.
Registro: `~/.local/state/orbit.log`.
Código instalado: `~/.local/share/orbit/app/`. Dependencias: Python 3, PySide6 Core/Gui/Widgets, Gio, Hyprland; Poppler/FFmpeg para vistas previas, mpv para reproducción y Tesseract para OCR.

La barra muestra espacios de trabajo, red, volumen, batería, fecha y notificaciones.
**Super + F** alterna pantalla completa y el estado anterior de la ventana.
Polybar se oculta en el monitor con una ventana a pantalla completa, incluso si es
transparente. Vuelve al salir o cambiar a un escritorio sin pantalla completa;
las barras de los otros monitores siguen visibles. Funciona también con F11 en aplicaciones.
`desktop-bar` inicia el controlador `bar_visibility.py` una sola vez por sesión gráfica.
Icono inicial: abre Wysun; clic derecho: historial. Campana: última notificación; clic derecho: pausa/reanuda.
Los cambios del instalador tienen respaldo en `~/.local/state/dotifails/backups/`.
Usa `dotifails restore` para listar respaldos y `dotifails restore ID` para recuperar uno.

## Validación

`python3 -m unittest tests.wysun_app.test_launcher_core` ejecuta las pruebas de cálculo seguro, retención, snippets, búsqueda, navegación, copiado de texto e imágenes y vista previa de archivos. Usa datos temporales y el backend offscreen.

## Versión 2 · medios y controles

- Emoji a color con Noto Color Emoji, cuadrícula, categorías y favoritos (Ctrl + P).
- Colores con o sin `#`, RGB y HSL; vista de muestra y copia en distintos formatos.
- Calculadora: `12x5`, `12 x 5`, `12×5`, `1,5x2`.
- Miniaturas de imágenes del portapapeles y favicons de enlaces con caché local.
- Metadatos: aplicación de origen para las nuevas copias, dimensiones, tamaño y fecha. Los orígenes anteriores no se inventan.
- OCR local Tesseract 5.5, español e inglés, un trabajo a la vez. El texto reconocido se incluye en la búsqueda. Imágenes sin texto o ilegibles pueden no producir resultados. Las capturas anteriores se procesan automáticamente.
- Acciones contextuales compactas: copiar, pegar, fijar, guardar imágenes, abrir con otra aplicación y eliminar. OCR se utiliza en la búsqueda; no ocupa el menú de imágenes. La administración general del historial tiene su propio menú.
- Los snippets conservan formato enriquecido, icono, contador de usos y fecha de último uso. Variables adicionales: `{clipboard}`, `{date+4}` y `{week}`.
- **Super + N**: panel nativo de Wi-Fi, interfaces y conexiones VPN. La contraseña, cuando se necesita, se solicita en un campo oculto y no se guarda en el historial de Wysun.
- **Super + X**: panel compacto de sesión y energía, con hora local, fecha en español y tiempo encendido del equipo (días, horas y minutos). Se actualiza mientras está abierto. Flechas o Tab seleccionan; Enter (también numérico) o Espacio activan la opción enfocada. Reiniciar, apagar, suspender y cerrar sesión requieren confirmación en la interfaz. Esc cancela o cierra.

El botón **Bloquear** usa `i3lock`, incluido en las dependencias del instalador. El fondo de Wysun se genera para los monitores conectados, sin capturar contenido del escritorio. El instalador compila una variante nativa de i3lock 2.15 para Wysun: fondo sin rótulos, entrada suave, pulso por tecla, señal ámbar al borrar, reacción al error y salida con un visto bueno y fundido de 280 ms. La salida se activa después de autenticar y mantiene el teclado y ratón bloqueados hasta el último fotograma. Respeta la preferencia de reducir movimiento. Escribe la contraseña de tu cuenta y pulsa Enter para desbloquear; la autenticación y el bloqueo de teclado y ratón los realiza i3lock. El panel solo se cierra cuando el bloqueador confirma que adquirió la sesión. Si falta el ejecutable o falla el inicio, muestra el error y permanece abierto. Las dependencias de compilación están en el manifiesto del instalador. La actualización `--orbit-only` compila con las dependencias ya instaladas, pero no instala paquetes: en un escritorio existente que aún no tenga el bloqueador, instala `sudo apt install i3lock` antes de usarlo.
- Alt + Tab usa el selector de ventanas de Wysun.
- Barra flotante en tres secciones. Recursos abre información de sistema; red abre conexiones; clic derecho en volumen abre las salidas de audio; fecha abre calendario; campana abre notificaciones y clic derecho pausa los avisos.

`python3 -m unittest tests.wysun_app.test_launcher_enhanced` valida además migración, colores sin prefijo, OCR real, cuadrícula de emojis a color, filtros, acciones, snippets enriquecidos y cancelación de apagado. Las pruebas de red son de consulta; no desconectan el equipo. Las conexiones nuevas y el bloqueo/suspensión dependen de NetworkManager, Polkit y el bloqueador del sistema.

Los archivos de imagen que abres desde el historial se materializan en `~/.cache/orbit/opened/`, con permisos privados; los temporales de más de un día se limpian al volver a abrir una imagen.


## Versión 3 · aplicaciones del escritorio

### Accesos

| Teclas | Ventana |
| --- | --- |
| Super + N | Wysun Conexiones |
| Super + X | Sesión, en un panel compacto e independiente |
| Super + Alt + coma | Wysun Ajustes |
| Alt + K o Ctrl + K | Acciones del elemento seleccionado |
| Ctrl + E | Editar en Vim un archivo de texto o una copia de texto/snippet |

También puedes buscar «Ajustes del escritorio» y «Centro de conexiones» en Wysun. Ajustes tiene su propio proceso ligero; Conexiones comparte el proceso del lanzador. Esc cierra sus ventanas.

### Iconos y menús

Iconos de acciones [Lucide](https://lucide.dev), pequeños y consistentes, con acentos discretos por sección. SVG y licencia incluidos en `assets/lucide/`. Las aplicaciones usan los iconos reales del tema Win11-Dark y el respaldo MATE, con las rutas Qt corregidas; Fluent era un tema de cursores en este equipo. No se cambió el tema global de otras aplicaciones.

Los menús muestran acciones del elemento actual. Imágenes: copiar, pegar, guardar, abrir con, fijar y eliminar. Colores: HEX, RGB y HSL. Las funciones generales del historial están en clic derecho sobre «Historial activo» y en «Opciones del historial». Se conserva Ctrl + Shift + Enter para pegar y volver aunque no ocupe una fila del menú.

### Conexiones

- Wi-Fi y Ethernet: activar/desactivar Wi-Fi, actualizar redes, conectar/desconectar, red oculta y detalles de la conexión activa.
- Bluetooth: estado del adaptador, dispositivos guardados/cercanos, búsqueda limitada a 12 segundos, emparejar, conectar, desconectar, confiar y olvidar. Los PIN y confirmaciones se solicitan en la interfaz; las contraseñas no se pasan como argumentos ni se registran en Wysun.
- VPN y Guardadas: conectar/desconectar perfiles, activar conexión automática, olvidar y abrir el editor de NetworkManager para IP, DNS, seguridad y nuevas VPN.
- SSH: importar alias de `~/.ssh/config` y archivos Include, crear/editar/eliminar perfiles propios y abrir una terminal OpenSSH. Los perfiles propios se guardan en `~/.config/orbit/ssh.json` con permisos 600. No guarda contraseñas ni claves privadas. SSH usa su configuración y verificación de servidor habituales. La vista de alias no evalúa `Match exec`; la conexión real la realiza OpenSSH.

Las operaciones se ejecutan únicamente al activarlas desde la interfaz. Las pruebas automatizadas consultan servicios y validan la construcción de comandos; no conectan a servidores ni cambian la red o el emparejamiento de dispositivos.

### Vim

Archivos de texto y código seleccionados en Wysun se abren con Neovim (Vim como alternativa) en Ghostty. «Abrir con la aplicación predeterminada» sigue disponible en Acciones. Las rutas se pasan como argumentos separados, incluyendo espacios y caracteres especiales. El texto del historial o un snippet se abre como copia privada en `~/.cache/orbit/editor/`; editar esa copia no modifica el historial ni el snippet original. Estos archivos de trabajo se conservan hasta que los elimines.

### Ajustes del escritorio

- Apariencia: separación, grosor de bordes y colores de Hyprland.
- Comportamiento: proporción/división, enfoque y puntero.
- Atajos: búsqueda sobre las combinaciones activas de Hyprland, alta/edición/eliminación, captura real de combinación y detección de conflictos. Guarda sin alterar los demás bloques; avisa si el archivo cambió externamente.
- Ventanas: crear, editar y quitar reglas por clase, estado, escritorio, centrado y borde. Se aplican a ventanas nuevas.
- Copias y archivos: abrir la configuración de Hyprland y sus ajustes en Vim; restaurar copias de atajos o ajustes.

Los cambios de Hyprland requieren «Aplicar cambios» y se aplican en vivo mediante `hyprctl`. Se conservan copias en `~/.local/share/orbit/settings-backups/`. Los ajustes persisten en `~/.config/orbit/hypr-desktop.json` y `hypr-settings.lua`; los atajos en `hypr-shortcuts.json` y `hypr-shortcuts.lua`. Un error al aplicar revierte los valores modificados en esa operación. «Recargar» descarta lo no aplicado y lee los archivos actuales.

### Verificación v3

`QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests/wysun_app -t tests`

52 pruebas: cálculos, medios, OCR, historial, menús contextuales, archivos con espacios, perfiles SSH, conflictos, guardado y reversión de ajustes, paneles independientes e iconos reales. Verificación adicional de Neovim leyendo un archivo temporal en modo headless y revisión visual de las ventanas en la sesión Wysun / Hyprland.

## Versión 4 · archivos y conexiones

### Archivos

- Filtros para imágenes, vídeos, audio, documentos, código y otros archivos; miniaturas de imágenes y coincidencias de OCR identificadas como «Texto en imagen».
- Acciones agrupadas por tipo y operaciones de archivo. «Copiar imagen» conserva la resolución decodificada; «Copiar archivo» coloca una referencia de archivo para pegarla en un gestor. «Guardar una copia» conserva el original.
- Botones visibles de vista ampliada y «Abrir con…», también para imágenes del historial. El OCR trabaja en la búsqueda y los metadatos, sin añadir una acción redundante al menú.
- Vista ampliada con zoom de imágenes, páginas de PDF y texto/código. Vídeo y audio tienen reproducción/pausa, posición, duración y silencio. Espacio reproduce o pausa; cerrar la vista detiene el reproductor.
- Metadatos según el formato: tamaño, dimensiones, duración, códec, páginas, modificación y disponibilidad de búsqueda por texto. Los archivos de código, incluido TypeScript `.ts`, conservan la apertura en Vim.

### Conexiones

Super + N abre una lista a la izquierda y un inspector a la derecha. Seleccionar una conexión muestra sus datos y controles sin abrir un menú de detalles. Wi-Fi incluye señal, seguridad, banda, interfaz, IP y DNS de la conexión activa; Bluetooth muestra emparejamiento, confianza y batería cuando el dispositivo la informa. VPN, SSH y perfiles guardados tienen sus controles visibles en el mismo lugar.

Alt + 1…5 cambia de sección; Ctrl + Tab / Ctrl + Shift + Tab recorre las secciones; arriba/abajo cambia de elemento desde la búsqueda; Ctrl + L enfoca la búsqueda y Ctrl + R actualiza. Cada sección conserva su búsqueda y selección. Los datos se actualizan en segundo plano sin devolver el foco al primer elemento.

Conectar/desconectar, editar, confiar, olvidar, configurar IP/DNS y conexión automática aparecen según el elemento seleccionado. Las contraseñas y claves privadas no se incluyen en el inspector ni en «Copiar datos».

### Verificación y copia

`QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests/wysun_app -t tests`

45 pruebas. La ampliación cubre OCR real de archivos e invalidación de caché, búsqueda literal, fotograma y metadatos de vídeo, acciones por tipo, copia de imágenes/archivos, vista ampliada y navegación/selección persistente en conexiones. Reproducción, pausa, salto temporal y cierre de mpv comprobados adicionalmente en la sesión Wysun / Hyprland con un vídeo de prueba.

Con un catálogo real de 43.045 archivos, la preparación de la lista pasó de 1,68–1,71 s a 17–30 ms al construir solo los 200 resultados visibles. Esta medición corresponde al render de la lista, no a la indexación inicial ni al reconocimiento OCR.

Copia anterior a esta versión: `~/.local/share/orbit-v4-backup-20260925-032042/source/`.

## Gestor del entorno · Wysun Ajustes

**Super + Alt + coma** abre el gestor. También está en el menú de aplicaciones como **Wysun Ajustes**, y se puede abrir con `wysun settings`. Usa `wysun settings shortcuts`, `wysun settings displays` o `wysun settings wallpaper` para entrar directamente en una sección. Ctrl + F busca una sección; Ctrl + Enter aplica sus cambios.

Las diez secciones reúnen:

- Resumen con accesos a conexiones, sonido y sesión.
- Pantallas: posición mediante arrastre o coordenadas, resolución, frecuencia, rotación y pantalla preferida. La prueba requiere confirmación en 15 segundos; un proceso independiente recupera la disposición anterior si Ajustes se cierra o deja de responder. Se guardan perfiles según las pantallas conectadas.
- Escritorios: nombre y número de ventanas de cada espacio de trabajo de Hyprland, creación, traslado y eliminación de escritorios vacíos. Nunca elimina un escritorio ocupado ni el último de una pantalla.
- Tema: Tokyo, Severance y Space Black con paleta, fondos y respaldo previo. Incluye la barra de Quickshell: pantallas donde aparece, altura, separación, esquinas, opacidad, colores y orden de módulos.
- Atajos: combinaciones activas de Hyprland, alta/edición/eliminación, captura real del teclado, detección de conflictos y edición individual. Las combinaciones de Ghostty, Wysun, Conexiones y Neovim se muestran con su contexto y acceso a la configuración en Vim.
- Reglas de ventanas: clase, estado, monitor, centrado y borde, aplicadas a ventanas nuevas.
- Efectos y animaciones: opacidad, reducción de movimiento y animaciones del compositor.
- Terminal: fuente, tamaño, colores, márgenes, opacidad e historial de Ghostty. En terminales abiertas, Ctrl + Shift + coma recarga la configuración.
- Inicio y aplicaciones: aplicaciones disponibles, activación explícita para esta sesión, aplicaciones propias y estado de los servicios. La activación se aplica al siguiente inicio de sesión; no abre aplicaciones al marcar una fila.
- Archivos y copias: configuración en Neovim, inspección de versiones anteriores y restauración de atajos o ajustes.

Los cambios se aplican con el botón correspondiente. Los atajos se guardan desde su diálogo; las aplicaciones de inicio y carpetas del fondo se guardan al editarlas. `Recargar` descarta las ediciones pendientes. Las preferencias adicionales están en `~/.config/orbit/environment.json`; Quickshell las recarga con `wysun shell reload-preferences`. Las aplicaciones de inicio activadas desde el gestor se ejecutan una vez por sesión, sin activar automáticamente todas las entradas XDG del sistema.

Copias: `~/.local/share/orbit/settings-backups/`. Copia previa a esta ampliación: `~/.local/share/orbit/settings-upgrade-backups/20260925-131042/`. Las capturas de pantalla usadas para las pruebas no forman parte de la configuración.

Verificación: `QT_QPA_PLATFORM=offscreen python3 -m unittest tests.wysun_app.test_native_settings tests.wysun_app.test_desktop_utilities`. Las pruebas de configuración usan directorios temporales; comprueban reversión de pantallas, confirmación, desconexión, persistencia, conflictos, conservación de archivos y fondos por monitor. Además se comprueba la captura de teclado y se revisan las secciones en la sesión Wysun / Hyprland real.


## Utilidades nativas

- **Super + Shift + N**: notas Markdown con búsqueda, guardado automático, favoritos, papelera recuperable e importación explícita de archivos. Ctrl N crea; Ctrl S guarda; Ctrl E abre en Vim. Los conflictos externos conservan tu borrador y permiten guardar una copia.
- **Super + Shift + K**: gestor de procesos con gráficas de CPU, memoria e intercambio, tabla ordenable y vista de árbol. Filtros por usuario, estado y consumo; inspector de comando, rutas, hilos, antigüedad y archivos abiertos. Selección múltiple para pausar, reanudar o terminar procesos propios; cierre forzado desde Acciones. Pausar y cerrar piden confirmación y comprueban la identidad del proceso antes de enviar señales. Los procesos de la sesión están protegidos.
- **Super + Shift + C**: colores, captura con lupa, HEX/RGB/HSL, recientes y favoritos. Ctrl P captura; flechas ajustan el píxel; Enter confirma; Escape cancela.

Estos paneles también aparecen al buscar en el lanzador. No importan datos personales de la máquina de origen.

En Procesos, **Ctrl F** busca y **↓** pasa a los resultados. **Ctrl/Shift + clic** selecciona varias filas; **Alt K** abre acciones; **F5** actualiza; **Espacio** con foco en la tabla congela/reanuda la vista. Congelar no detiene procesos. Muestreo ajustable a 1, 2 o 5 segundos; se detiene al ocultar la ventana. La selección se mantiene al ordenar o actualizar, pero se descarta si el PID pertenece a un proceso nuevo.

La CPU del equipo usa la capacidad total; la CPU por proceso cuenta núcleos y puede superar el 100%. Las gráficas conservan las últimas 48 muestras y ajustan su escala. Lectura/escritura son bytes de E/S física por segundo según `/proc`, no tráfico de red; «—» indica que falta una muestra previa o permiso de lectura. Los archivos abiertos muestran hasta 60 descriptores. Los comandos se muestran con patrones habituales de credenciales ocultos; no se leen variables de entorno ni se registran comandos.

## Cristal y actividad · revisión 2026-10

Los paneles comparten cristal oscuro con fondo al 80%, borde de luz y texto opaco. El compositor aplica el desenfoque de fondo a las superficies ARGB según sus reglas de decoración. Qt anima las entradas (240 ms / 12 px) y salidas (140 ms / 6 px). Las pulsaciones usan escala 0.96; cambiar de sección desvanece el contenido durante 140 ms. Las acciones que entregan el foco, como pegar, se ocultan inmediatamente.

En **Ajustes → Efectos y animaciones** puedes cambiar la opacidad (65–100%) y reducir movimiento. Se guardan aparte del código, en `~/.config/orbit/appearance.json`. `ORBIT_REDUCED_MOTION=1` también desactiva el movimiento. El blur requiere el compositor activo; las pruebas offscreen verifican el canal alfa, no el desenfoque real del compositor.

**Super + X** muestra reloj, batería circular, autonomía estimada, consumo, salud y ciclos cuando el kernel los expone. La estimación usa energía y potencia instantáneas; los datos ausentes se indican como no disponibles. Conserva las cinco acciones, flechas, Enter y Escape.

**Super + Shift + K** abre Monitor de actividad: selección estable entre muestras, medidores de consumo, presión PSI de CPU/RAM/E/S, carga del sistema, hilos con tiempo acumulado y punto de espera, grupos de control y cambios de contexto. Combina filtros como `cpu>5 mem>256m user:demo`, `pid:123`, `ppid:123` o `state:R`. Congelar detiene las muestras, F5 actualiza una vez. Las señales siguen verificando identidad con pidfd y protegen procesos de la sesión.

Validación adicional: `QT_QPA_PLATFORM=offscreen python3 -m unittest tests.wysun_app.test_refinement -v`. Las capturas de revisión usan datos de ejemplo. No contienen notas, historial ni comandos privados.

## Temas

En **Ajustes → Tema** se elige Tokyo, Severance o Space Black. Tokyo combina negro ciruela, violeta y movimiento suave; Severance (antes Azul), azul petróleo y cian; Space Black, grafito y plata con movimiento sutil. Cada perfil aplica el fondo, la paleta ANSI y el cursor/selección de Ghostty, el prompt de Starship, Neovim, Wysun y sus paneles, la barra de Quickshell, los bordes de Hyprland, Dunst, colores GTK y el bloqueo animado. Las preferencias de opacidad y reducción de movimiento se conservan. Las ventanas abiertas detectan los cambios de tema y actualizan estilos e iconos. Neovim toma su paleta al volver a abrirlo.

Antes de escribir se guarda un respaldo en `~/.local/state/orbit/theme-backups/`. Si falla la validación de Ghostty o la aplicación principal, se restauran los archivos anteriores. No se reemplazan fuentes, tamaños, atajos, conexiones, notas o historial. Los antiguos nombres de instalación `azul` y `morado` siguen siendo alias de `severance` y `tokyo`.

Las notificaciones mantienen una apariencia neutra en todos los temas: grafito translúcido, texto claro y borde gris. Sus colores no cambian con el tema. Ajustes conserva Pantallas, Escritorios, Tema y barra, Atajos, Reglas, Efectos, Terminal, Inicio y Archivos.

## Música local

Abre el mini reproductor con **Super + Shift + M**. La app completa se llama **Wysun Music**, aparece en **Super + D** y se ejecuta con `wysun music`. Los alias `musika` y `musica` siguen funcionando. Ambos comparten canción, posición, cola y favoritos en una sola instancia nativa (PySide6 + mpv). Cerrar cualquiera de las ventanas mantiene el audio. Volver a abrir presenta la misma instancia. Una nueva sesión restaura canción, posición, volumen y cola en pausa.

La biblioteca agrupa álbumes, selecciones y rankings con portadas y mosaicos. Solo aparecen archivos disponibles. La búsqueda es global, admite acentos y encuentra canciones, artistas y playlists. Clic en artista muestra sus canciones locales, incluidas colaboraciones; clic en corazón guarda Favoritos. Doble clic o Enter reproduce; clic en la barra o arrastrar cambia la posición. Anterior/siguiente recorren una cola estable incluso en aleatorio, independiente de la vista abierta.

Pulsa `F1` en cualquier ventana para consultar los atajos. `Ctrl+F` enfoca la búsqueda global; `↑/↓` eligen resultados y `Enter` reproduce la selección. `Tab/Shift+Tab` recorren los controles, con foco visible; `Enter/Espacio` activan botones. `Esc` limpia la búsqueda primero, después cierra la letra y finalmente esconde la ventana.

`Ctrl+Espacio` reproduce/pausa, `Ctrl+←/→` cambia de canción, `Ctrl+↑/↓` cambia el volumen y `Ctrl+Shift+F` marca la canción actual como favorita. `Ctrl+L` abre y enfoca la letra; las flechas recorren sus líneas y `Enter` salta al momento seleccionado sin que la sincronización robe la selección. Las flechas de la barra de tiempo avanzan o retroceden cinco segundos.

En la app completa, `Alt+1…5` abren biblioteca, favoritos, artistas, descargas y añadir música; `Ctrl+J` enfoca el contenido y `Ctrl+O` importa archivos. En la tabla, `F` marca la fila como favorita y `Ctrl+Enter` abre su artista. En los resultados de descarga, `Ctrl+Enter` guarda la selección. En el mini reproductor, `Ctrl+Enter` abre la app completa.

Portadas: Spotify oEmbed. Letras: LRCLIB, sincronizadas solo si coinciden título, artista y duración del archivo (tolerancia de dos segundos). Las letras incompatibles se muestran sin sincronizar; no se inventan tiempos. Las líneas sincronizadas permiten saltar y ajustar un desfase local. Fotos de artistas: MusicBrainz → Wikidata → Wikimedia Commons, con enlace de créditos; identidades ambiguas usan iniciales. Consultas en dos trabajadores, imágenes hasta 512 px y caché local; MusicBrainz máximo una consulta por segundo. No hay navegador integrado ni cuentas nuevas.

Descargas permite continuar, pausar la cola y reintentar errores, con detalles opcionales. El botón de descarga de la cabecera admite nombres, enlaces de YouTube y enlaces públicos de playlists, álbumes o canciones de Spotify. Se lee la metadata publicada por Spotify y se busca audio en YouTube; Spotify no suministra el archivo de audio. Una vista pública puede limitar la lista o no exponer listas privadas; la interfaz indica cuántas canciones se publicaron. Se reutilizan IDs de Spotify, enlaces de YouTube y grabaciones con título, artista y duración coincidentes (hasta dos segundos). Las importaciones de Spotify y variantes de audio exigen esa misma tolerancia antes y después de la descarga; las incompatibles quedan para revisar. Las pistas compartidas reutilizan archivos. Versiones de audio se añaden por separado, conservando originales y validando duración; la reproducción activa no cambia de archivo a mitad de canción.

Audio en `~/Music/Orbita`; biblioteca y cola en `~/.local/share/orbit/music/library.json`; favoritos, sesión, referencias y variantes en `player.sqlite3`; portadas, fotos y letras en `metadata/`. Estos datos privados están separados del código instalado. `reference-manifest.json` conserva las duraciones originales de Spotify para distinguirlas de las de un videoclip.

La instalación completa incluye mpv/ffmpeg/PySide6 y yt-dlp con versión y SHA-256 fijadas. `--orbit-only` actualiza la app, los ejecutables de acceso y su icono sin reinstalar el sistema. El atajo de la configuración distribuida abre el mini reproductor.

## Wayland nativo

`wysun daemon` inicia el residente sin abrir ventana. El backend usa Hyprland 0.55
como único compositor y enumera ventanas mediante su IPC; no hay camino X11 propio.
El clipboard global utiliza wl-clipboard/data-control, con límites y timeouts; si el
protocolo no existe, Qt solo puede leer con foco. No se promete lectura/inyección
global genérica. Hyprland pega con foco y dirección de destino comprobados. PNG,
texto, HTML y URI se guardan acotados; las ofertas privadas/sensitive se excluyen.
Un archivo de historial siempre se vuelve a copiar, nunca se reproduce un corte
destructivo obsoleto. OCR/Tesseract y SQLite se conservan.

Settings escribe fragmentos propios hypr-settings.lua/hypr-theme.lua/
hypr-effects.lua/hypr-shortcuts.lua bajo el config de Wysun y respeta hooks de
sesión. No reescribe archivos Hyprland del usuario. Displays usa hl.monitor y el
watchdog de reversión, conserva escala y posiciones negativas. Quickshell es el
dueño del wallpaper: Python guarda preferencias y solicita `wysun shell
reload-preferences`. Color usa `wysun recorder --pick-color`. El bloqueo y la
suspensión llaman a wysun-lock, que espera la adquisición del bloqueo.

Files y Recorder conservan vídeo embebido con libmpv SW/QImage/QWidget y sockets
IPC; Music conserva su motor mpv de audio y persistencia. El render por software
puede consumir más CPU; las pruebas unitarias/offscreen y el vídeo sintético no
constituyen validación física del compositor.

La barra se configura mediante `${XDG_CONFIG_HOME:-$HOME/.config}/orbit/hypr-bar.json`;
Quickshell la observa y Python solicita `wysun shell reload-preferences`. El tema
actualiza los colores de ese archivo preservando geometría, módulos y monitores.
El observador de tema Python usa eventos de archivo/directorio y contempla reemplazo
atómico y creación tardía. Guardar reglas no sobrescribe colores o gaps que el
usuario no cambió. El FileChooser externo se enruta al portal configurado; Files
mantiene sus datos independientes. Cada diálogo conserva su propia apariencia, sin
prometer una interfaz idéntica.
