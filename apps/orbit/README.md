# Órbita

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
No hay telemetría, cuentas ni sincronización. Las búsquedas web solo salen a Internet al seleccionarlas. Para mostrar iconos de enlaces HTTPS, Órbita puede consultar `/favicon.ico` directamente en el dominio público del enlace, sin enviar su ruta ni parámetros. No consulta servicios externos de favicons.
Se excluyen formatos de gestores de contraseñas y patrones reconocibles de claves; no es un detector infalible.
Pausa el historial con el botón inferior antes de copiar información sensible. Clic derecho en «Historial activo» o el comando «Opciones del historial» permite administrar y borrar el historial.

La búsqueda de archivos usa nombres, rutas y texto reconocido en imágenes mediante OCR local. Omite carpetas ocultas y dependencias, con un límite de 100.000 archivos. El catálogo se actualiza en segundo plano al volver a archivos después de 5 minutos. No indexa el contenido de documentos de texto, PDF ni audio.
El índice OCR empieza al abrir Archivos, procesa primero las imágenes más recientes y continúa en segundo plano, una imagen a la vez. El botón «OCR» muestra el progreso y permite pausar/reanudar; esta preferencia se conserva. Los resultados por contenido aumentan conforme avanza el índice. Las miniaturas y el texto se guardan con permisos privados en `~/.local/share/orbit/file-media.sqlite3`; se invalidan si cambia o desaparece el archivo. No se envían imágenes a servicios externos. Se omiten SVG, imágenes excesivamente grandes, formatos no decodificables y texto con patrones reconocibles de secretos.
Las vistas previas de documentos leen únicamente el archivo seleccionado. PDF y vídeo usan Poppler y FFmpeg locales; la reproducción integrada utiliza mpv y comienza en pausa.

## Operación

`~/.local/bin/orbit` activa el proceso residente por un socket privado. No arranca otro intérprete Qt en cada atajo.
`~/.local/bin/orbit daemon` inicia el residente sin mostrarlo. BSPWM lo inicia al entrar en sesión.
Registro: `~/.local/state/orbit.log`.
Código instalado: `~/.local/share/orbit/app/`. Dependencias: Python 3, PySide6 Core/Gui/Widgets, Gio, BSPWM; Poppler/FFmpeg para vistas previas, mpv para reproducción y Tesseract para OCR.

La barra muestra espacios de trabajo, red, volumen, batería, fecha y notificaciones.
**Super + F** alterna pantalla completa y el estado anterior de la ventana.
Polybar se oculta en el monitor con una ventana a pantalla completa, incluso si es
transparente. Vuelve al salir o cambiar a un escritorio sin pantalla completa;
las barras de los otros monitores siguen visibles. Funciona también con F11 en aplicaciones.
`desktop-bar` inicia el controlador `bar_visibility.py` una sola vez por sesión gráfica.
Icono inicial: abre Órbita; clic derecho: historial. Campana: última notificación; clic derecho: pausa/reanuda.
Los cambios del instalador tienen respaldo en `~/.local/state/dotifails/backups/`.
Usa `dotifails restore` para listar respaldos y `dotifails restore ID` para recuperar uno.

## Validación

`python3 test_orbit.py` ejecuta las pruebas de cálculo seguro, retención, snippets, búsqueda, navegación, copiado de texto e imágenes y vista previa de archivos. Usa datos temporales y el backend offscreen.

## Versión 2 · medios y controles

- Emoji a color con Noto Color Emoji, cuadrícula, categorías y favoritos (Ctrl + P).
- Colores con o sin `#`, RGB y HSL; vista de muestra y copia en distintos formatos.
- Calculadora: `12x5`, `12 x 5`, `12×5`, `1,5x2`.
- Miniaturas de imágenes del portapapeles y favicons de enlaces con caché local.
- Metadatos: aplicación de origen para las nuevas copias, dimensiones, tamaño y fecha. Los orígenes anteriores no se inventan.
- OCR local Tesseract 5.5, español e inglés, un trabajo a la vez. El texto reconocido se incluye en la búsqueda. Imágenes sin texto o ilegibles pueden no producir resultados. Las capturas anteriores se procesan automáticamente.
- Acciones contextuales compactas: copiar, pegar, fijar, guardar imágenes, abrir con otra aplicación y eliminar. OCR se utiliza en la búsqueda; no ocupa el menú de imágenes. La administración general del historial tiene su propio menú.
- Los snippets conservan formato enriquecido, icono, contador de usos y fecha de último uso. Variables adicionales: `{clipboard}`, `{date+4}` y `{week}`.
- **Super + N**: panel nativo de Wi-Fi, interfaces y conexiones VPN. La contraseña, cuando se necesita, se solicita en un campo oculto y no se guarda en el historial de Órbita.
- **Super + X**: panel nativo de sesión y energía. Reiniciar, apagar, suspender y cerrar sesión requieren confirmación en la interfaz.
- Alt + Tab usa el selector de ventanas de Órbita.
- Barra flotante en tres secciones. Recursos abre información de sistema; red abre conexiones; clic derecho en volumen abre las salidas de audio; fecha abre calendario; campana abre notificaciones y clic derecho pausa los avisos.

`python3 test_v2.py` valida además migración, colores sin prefijo, OCR real, cuadrícula de emojis a color, filtros, acciones, snippets enriquecidos y cancelación de apagado. Las pruebas de red son de consulta; no desconectan el equipo. Las conexiones nuevas y el bloqueo/suspensión dependen de NetworkManager, Polkit y el bloqueador del sistema.

Los archivos de imagen que abres desde el historial se materializan en `~/.cache/orbit/opened/`, con permisos privados; los temporales de más de un día se limpian al volver a abrir una imagen.


## Versión 3 · aplicaciones del escritorio

### Accesos

| Teclas | Ventana |
| --- | --- |
| Super + N | Órbita Conexiones |
| Super + X | Sesión, en un panel compacto e independiente |
| Super + Alt + coma | Órbita Ajustes |
| Alt + K o Ctrl + K | Acciones del elemento seleccionado |
| Ctrl + E | Editar en Vim un archivo de texto o una copia de texto/snippet |

También puedes buscar «Ajustes del escritorio» y «Centro de conexiones» en Órbita. Ajustes tiene su propio proceso ligero; Conexiones comparte el proceso del lanzador. Esc cierra sus ventanas.

### Iconos y menús

Iconos de acciones [Lucide](https://lucide.dev), pequeños y consistentes, con acentos discretos por sección. SVG y licencia incluidos en `assets/lucide/`. Las aplicaciones usan los iconos reales del tema Win11-Dark y el respaldo MATE, con las rutas Qt corregidas; Fluent era un tema de cursores en este equipo. No se cambió el tema global de otras aplicaciones.

Los menús muestran acciones del elemento actual. Imágenes: copiar, pegar, guardar, abrir con, fijar y eliminar. Colores: HEX, RGB y HSL. Las funciones generales del historial están en clic derecho sobre «Historial activo» y en «Opciones del historial». Se conserva Ctrl + Shift + Enter para pegar y volver aunque no ocupe una fila del menú.

### Conexiones

- Wi-Fi y Ethernet: activar/desactivar Wi-Fi, actualizar redes, conectar/desconectar, red oculta y detalles de la conexión activa.
- Bluetooth: estado del adaptador, dispositivos guardados/cercanos, búsqueda limitada a 12 segundos, emparejar, conectar, desconectar, confiar y olvidar. Los PIN y confirmaciones se solicitan en la interfaz; las contraseñas no se pasan como argumentos ni se registran en Órbita.
- VPN y Guardadas: conectar/desconectar perfiles, activar conexión automática, olvidar y abrir el editor de NetworkManager para IP, DNS, seguridad y nuevas VPN.
- SSH: importar alias de `~/.ssh/config` y archivos Include, crear/editar/eliminar perfiles propios y abrir una terminal OpenSSH. Los perfiles propios se guardan en `~/.config/orbit/ssh.json` con permisos 600. No guarda contraseñas ni claves privadas. SSH usa su configuración y verificación de servidor habituales. La vista de alias no evalúa `Match exec`; la conexión real la realiza OpenSSH.

Las operaciones se ejecutan únicamente al activarlas desde la interfaz. Las pruebas automatizadas consultan servicios y validan la construcción de comandos; no conectan a servidores ni cambian la red o el emparejamiento de dispositivos.

### Vim

Archivos de texto y código seleccionados en Órbita se abren con Neovim (Vim como alternativa) en Ghostty. «Abrir con la aplicación predeterminada» sigue disponible en Acciones. Las rutas se pasan como argumentos separados, incluyendo espacios y caracteres especiales. El texto del historial o un snippet se abre como copia privada en `~/.cache/orbit/editor/`; editar esa copia no modifica el historial ni el snippet original. Estos archivos de trabajo se conservan hasta que los elimines.

### Ajustes del escritorio

- Apariencia: separación, grosor de bordes, márgenes y colores.
- Comportamiento: proporción/división, enfoque, puntero y monóculo.
- Atajos: búsqueda sobre el sxhkdrc real, alta/edición/eliminación, captura de combinación y detección de conflictos después de expandir grupos. Guarda sin alterar los demás bloques; avisa si el archivo cambió externamente. Las tres colisiones previas se muestran sin reasignarlas automáticamente.
- Ventanas: crear, editar y quitar reglas por clase, estado, escritorio, centrado y borde. Se aplican a ventanas nuevas.
- Copias y archivos: abrir BSPWM, sxhkd, Picom y Polybar en Vim; restaurar copias de atajos o ajustes.

Los cambios de BSPWM requieren «Aplicar cambios» y se aplican en vivo. Los atajos se guardan y recargan desde su diálogo. Se conservan copias en `~/.local/share/orbit/settings-backups/`. Los ajustes persisten en `~/.config/orbit/desktop.json` y `bspwm-settings.sh`, que bspwmrc carga al final del inicio. Un error al aplicar revierte los valores de BSPWM modificados en esa operación. «Recargar» descarta lo no aplicado y lee los archivos actuales.

La copia anterior a esta versión está en `~/.local/share/orbit-v3-backup-20260925-024713/`.

### Verificación v3

`QT_QPA_PLATFORM=offscreen python3 -m unittest test_orbit test_v2 test_v3`

35 pruebas: cálculos, medios, OCR, historial, menús contextuales, archivos con espacios, perfiles SSH, preservación/validación de atajos, conflictos, guardado y reversión de ajustes, paneles independientes e iconos reales. Verificación adicional de Neovim leyendo un archivo temporal en modo headless y revisión visual de las ventanas con Picom activo.

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

`QT_QPA_PLATFORM=offscreen python3 -m unittest test_orbit test_v2 test_v3 test_v4`

45 pruebas. La ampliación cubre OCR real de archivos e invalidación de caché, búsqueda literal, fotograma y metadatos de vídeo, acciones por tipo, copia de imágenes/archivos, vista ampliada y navegación/selección persistente en conexiones. Reproducción, pausa, salto temporal y cierre de mpv comprobados adicionalmente en X11 con un vídeo de prueba.

Con un catálogo real de 43.045 archivos, la preparación de la lista pasó de 1,68–1,71 s a 17–30 ms al construir solo los 200 resultados visibles. Esta medición corresponde al render de la lista, no a la indexación inicial ni al reconocimiento OCR.

Copia anterior a esta versión: `~/.local/share/orbit-v4-backup-20260925-032042/source/`.

## Gestor del entorno · Órbita Ajustes

**Super + Alt + coma** abre el gestor. También está en el menú de aplicaciones como **Órbita Ajustes**, y se puede abrir con `orbit settings`. Usa `orbit settings shortcuts`, `orbit settings displays` o `orbit settings wallpaper` para entrar directamente en una sección. Ctrl + F busca una sección; Ctrl + Enter aplica sus cambios.

Las 14 secciones reúnen:

- Resumen con accesos a conexiones, sonido y sesión.
- Pantallas: posición mediante arrastre o coordenadas, resolución, frecuencia, rotación, pantalla principal y duplicación. La prueba requiere confirmación en 15 segundos. Un proceso independiente recupera la disposición anterior si Ajustes se cierra o deja de responder. Se guardan perfiles según las pantallas conectadas.
- Escritorios: nombre, número de ventanas, monitor, creación, traslado y eliminación de escritorios vacíos. Nunca elimina un escritorio ocupado ni el último de una pantalla.
- Fondos: biblioteca local con miniaturas progresivas, carpetas propias y un fondo distinto por monitor. Rellenar, ajustar, estirar o centrar. Compone una imagen para la superficie X11 completa y conserva los originales.
- Polybar: pantallas donde aparece, monitor de la bandeja, altura, separación, esquinas, opacidad, colores y orden de módulos. Respeta el control de visibilidad al entrar en pantalla completa.
- Ventanas y comportamiento: márgenes, bordes, mosaico, monóculo, foco, puntero y reglas de aplicaciones.
- Atajos: cada combinación de sxhkd en su propia fila, incluso grupos con llaves. Grabación real del teclado X11, cancelación y tiempo límite, validación de conflictos y edición individual o del grupo original. El filtro «Conflictos» muestra las combinaciones repetidas. Las combinaciones de Ghostty, Órbita, Conexiones y Neovim se muestran con su contexto y acceso a la configuración en Vim. Neovim enumera los mapas cargados con descripción; los mapas que un plugin registra solo al activarse pueden aparecer después en el propio editor.
- Efectos: duración de animaciones, sombras, desenfoque, esquinas y sincronización de Picom.
- Terminal: fuente, tamaño, colores, márgenes, opacidad e historial de Ghostty. En terminales abiertas, Ctrl + Shift + coma recarga la configuración.
- Notificaciones: posición, fuente, transparencia, esquinas, márgenes, cantidad y duración; botón para probar un aviso.
- Inicio: aplicaciones disponibles, activación explícita para esta sesión BSPWM, aplicaciones propias, estado de los servicios y acceso al inicio del escritorio. La activación se aplica al siguiente inicio de sesión; no abre aplicaciones al marcar una fila.
- Archivos y copias: configuración en Neovim, inspección de versiones anteriores y restauración de atajos o ajustes BSPWM.

Los cambios se aplican con el botón correspondiente. Los atajos se guardan desde su diálogo; las aplicaciones de inicio y carpetas del fondo se guardan al editarlas. `Recargar` descarta las ediciones pendientes. Las preferencias adicionales están en `~/.config/orbit/environment.json`; el inicio de BSPWM llama a `settings_runtime.py restore`. Las aplicaciones de inicio activadas desde el gestor se ejecutan una vez por sesión, sin activar automáticamente todas las entradas XDG del sistema.

Copias: `~/.local/share/orbit/settings-backups/`. Copia previa a esta ampliación: `~/.local/share/orbit/settings-upgrade-backups/20260925-131042/`. Las capturas de pantalla usadas para las pruebas no forman parte de la configuración.

Verificación: `QT_QPA_PLATFORM=offscreen python3 -m unittest test_settings_hub test_v3`. Las pruebas de configuración usan directorios temporales; comprueban reversión de pantallas, confirmación, desconexión, persistencia, conflictos, conservación de archivos y fondos por monitor. Además se comprueba la captura de teclado y se revisan las secciones en la sesión X11 real.


## Utilidades nativas

- **Super + Shift + N**: notas Markdown con búsqueda, guardado automático, favoritos, papelera recuperable e importación explícita de archivos. Ctrl N crea; Ctrl S guarda; Ctrl E abre en Vim. Los conflictos externos conservan tu borrador y permiten guardar una copia.
- **Super + Shift + K**: procesos, búsqueda por nombre/PID, consumo de CPU y memoria, inspector y señales de cierre. Solo se pueden terminar procesos propios y el cierre forzado pide confirmación.
- **Super + Shift + C**: colores, captura con lupa, HEX/RGB/HSL, recientes y favoritos. Ctrl P captura; flechas ajustan el píxel; Enter confirma; Escape cancela.

Estos paneles también aparecen al buscar en el lanzador. No importan datos personales de la máquina de origen.
