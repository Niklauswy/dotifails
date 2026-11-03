# Wysun Processes como app QML e integración con el shell y Hyprland — diseño

Fecha: 2026-11-02. Referencia visual aprobada: mockup interactivo
`docs/superpowers/specs/2026-11-02-wysun-processes-mockup.html` (datos simulados; ábrelo en un navegador y usa la
barra «Escenas del shell»). Es la referencia de distribución, movimiento y comportamiento: ante la duda, lo que hace
el mockup. En la copia versionada los iconos del tema se sustituyeron por letras.

## Intención

Processes es hoy un panel flotante del shell (`apps/shell/modules/processes`, componentes `qs.*`) que no se parece
a Files, Music ni Player y se queda en lo básico. Se quiere un monitor de procesos «de otro nivel» que:

- sea **una app de Wysun como Files**: ventana propia en mosaico, base `WysunM3` sobre PySide6, mismo Material You;
- se maneje entero con el teclado;
- tenga movimiento y acabado expresivos (no un clon de Windows);
- aproveche que vive dentro de Wysun y Hyprland: miniaturas reales de ventanas, localizar una ventana en pantalla,
  avisos con acciones, lanzador, app que no responde, forzar cierre de la ventana activa.

## Objetivos

1. Paquete nuevo `apps/python/wysun_processes` (app QML sobre `WysunM3`), `wysun processes [consulta]`.
2. Cinco secciones con rail de navegación: Procesos, Rendimiento, Apps, Servicios, Inicio.
3. Integraciones en el shell: miniaturas, localizar en pantalla, aviso de app que no responde, `Super+Shift+Esc`,
   avisos de consumo con acciones, lanzador con panel lateral de proceso.
4. Retirar el panel `processes` del shell.

## No objetivos

- Herramientas avanzadas de red o seguridad (puertos en escucha, «quién usa este archivo», auditoría, contenedores,
  agrupar por proyecto). Se propusieron y **el usuario las descartó**.
- Indicador en la barra, energía/batería por app, modo enfoque, historial persistente.
- Modo claro/oscuro propio: lo decide el tema de Wysun (`theme.json`), no hay botón en la app.

## Antiobjetivos (sería un fracaso aunque funcione)

- Que se vea distinta de Files/Music o con colores, radios o duraciones literales.
- Que parezca el Administrador de tareas de Windows (en particular Rendimiento).
- Indicadores circulares ondulados M3: el usuario los rechazó expresamente.
- Guardar datos de procesos en disco. Todo vive en memoria mientras la app está abierta.
- Que el monitor en segundo plano (avisos) consuma de forma apreciable o congele el escritorio.

## Restricciones

- AGENTS.md completo, en especial: tokens del tema (`tests/test_theme_literals.py`), `bin/wysun` como único punto de
  entrada, `python3 -P -m`, nada en `~/.local/share/wysun/app/`, `--wysun-only` no cambia atajos (migrar
  `hyprland.lua` activo con respaldo y sin pisar asignaciones del usuario), probar en claro/oscuro y con wallpapers
  distintos, pruebas serializadas y una sola compilación a la vez (memoria del proyecto: OOM previo).
- Textos de la interfaz en español.
- Credenciales: no aplica.

## Decisiones tomadas con el usuario

### Ventana y base
- App aparte en mosaico (sin regla `float` de Hyprland). `Super+Shift+K` y `wysun processes` la abren; si ya está
  abierta, la enfocan.
- `wysun processes firefox` abre filtrado por «firefox» y con su grupo seleccionado («abrir con contexto»).

### Procesos (sección principal) — como el mockup v4
- Buscador grande con filtros que se vuelven etiquetas quitables: `cpu>10`, `mem>500m`, `gpu>`, `user:`, `state:`,
  `pid:`, `app:` (los actuales de `process_data.matched` más `gpu` y `app`).
- Vistas por app / árbol / lista (botones segmentados), «Mis procesos / Todos los usuarios», refresco 1 s / 2 s,
  congelar actualizaciones.
- Tabla: Nombre, CPU, Memoria, GPU, Disco, Hilos, con totales en la cabecera, celdas con calor y barra fina.
  Orden por valores suavizados para que las filas no bailen; las filas se deslizan al reordenarse, entran y salen
  animadas; la selección es una píldora que se desliza con muelle.
- Panel de detalle a la derecha (se oculta con `I`): forma de estado + icono real, nombre, PID/usuario, estado;
  acciones (Terminar con botón dividido para Forzar, Pausar/Reanudar, Prioridad, Ir a la ventana, Más);
  gráfica en vivo CPU/Memoria/GPU/Disco; seis datos; pestañas Detalles / Hilos / Archivos / Red (en un grupo:
  Procesos / Detalles).
- Confirmación: terminar, forzar y prioridad piden confirmación en diálogo; pausar se hace al momento con
  «Deshacer» en el aviso inferior.
- Paleta de comandos `Ctrl+K` con acciones sobre el seleccionado, saltar a procesos y navegar.
- Atajos (ayuda con `?`): `/` o `Ctrl+F` buscar, `↑↓`/`j k`, `G`/`⇧G`, `→←` abrir/cerrar grupo, `Enter`,
  `Supr` terminar, `⇧Supr` forzar, `P` pausar, `+ −` prioridad, `W` ir a la ventana, `L` localizar, `Y` copiar PID,
  `S` ordenar, `U` usuarios, `V` vista, `Espacio` congelar, `I` panel, `[ ]` pestañas, `1`–`5` secciones.

### Rendimiento
- Tarjeta de diagnóstico arriba: frase («Todo va fluido» / «Algo está exigiendo la CPU…» con la app causante),
  espera de CPU/RAM/E/S (PSI de `/proc/pressure`) y tiempo encendido. «Respira» más rápido y se tiñe hacia el rol
  de error cuando hay presión.
- Cinco azulejos CPU, Memoria, GPU, Disco, Red: número grande que rueda y gráfica del último minuto de fondo.
  **Sin indicadores circulares.**
- Gráfica grande del recurso elegido con chips «Comparar con» otros recursos; a la derecha «Qué lo está usando»
  (apps con barras) y datos del recurso (frecuencia, temperatura, carga, swap/zram, VRAM, ocupación, IP…).
  En CPU, los hilos como puntos que crecen con su carga; en Memoria, barra de composición.

### Apps
- Ventanas agrupadas por **espacio de trabajo de Hyprland** («estás aquí» en el actual) con **miniatura real**,
  icono, título, CPU y memoria. Al pasar o seleccionar aparecen Abrir / Localizar / Cerrar.
- Fila «En segundo plano» con lo que no tiene ventana.
- Al abrir una ventana, **transformación de contenedor**: la tarjeta crece hasta una hoja con miniatura grande,
  datos que ruedan, gráfica recorrible y procesos; `Esc` la devuelve a su sitio.

### Servicios (`systemd --user`)
- Lista agrupada Con fallos / Activos / Temporizadores / Parados con filtro y búsqueda; insignia en el rail si hay
  fallos.
- Detalle: estado, explicación del fallo con Reintentar, iniciar/parar/reiniciar, interruptor «Iniciar con la
  sesión» (enable/disable), memoria/CPU/tareas/PID del cgroup, temporizadores con cuenta atrás a la próxima
  ejecución y la última, **registro en vivo** (`journalctl --user -u … -f`) con niveles coloreados.

### Inicio
- Línea de tiempo del arranque de la sesión («Tu sesión estuvo lista en X s»), una barra por programa coloreada
  por impacto; línea «lista».
- Lista con origen (sesión, `exec-once`, `systemd --user`, autostart XDG), impacto, interruptor y retraso
  (sin retraso / +5 s / +10 s). Las piezas de Wysun no se pueden quitar.
- **Decidido con el usuario:** la app **nunca escribe `hyprland.lua`**. Las entradas `exec-once` aparecen en la
  línea de tiempo y la lista **sin interruptor ni retraso** (solo lectura). Interruptor y retraso existen solo para
  el autostart XDG (anulaciones en `~/.config/autostart`: `Hidden=true` o un `Exec` con espera, sin tocar el
  `.desktop` original) y para `systemctl --user enable/disable`.

### Movimiento y aspecto (todo el punto 3 aprobado)
- **Iconos reales** de cada app (desde su `.desktop`/app_id/cgroup) en vez de letras.
- **Tinte por app** tomado del color dominante de su icono y mezclado con los roles Material You (contenedor del
  icono, vistas previas, línea de su gráfica). Excepción declarada al test de literales: el tinte se calcula en
  ejecución.
- **Formas M3 que se transforman** (M3Shapes del runtime) detrás del icono según el estado: trabajando = forma
  ondulada que gira lento; en espera = círculo; pausado = cuadrado redondeado; zombi = forma en estrella;
  grupo = forma propia.
- **Contadores que ruedan** en cifras grandes, con números tabulares de Google Sans Flex.
- **Gráficas recorribles**: guía y etiqueta al pasar el cursor («hace 23 s · 31 % · Web Content · YouTube 18 %») y
  hasta tres picos marcados con el icono de la app/proceso que los causó.
- Transiciones con los resortes expresivos de `tokens.json` (`Motion`), respetando movimiento reducido.

## Integraciones del shell y Hyprland (aprobadas)

1. **Miniaturas reales**: la app las pide al shell; Quickshell captura la ventana (toplevel) y las entrega sin
   tocar disco persistente (memoria o `$XDG_RUNTIME_DIR`, borradas al cerrar). Refresco moderado y solo de las
   visibles.
2. **Localizar en pantalla**: desde la app (`L`, botón, hoja de Apps) o el lanzador, el shell dibuja sobre la
   ventana un halo de acento que palpita y atenúa las demás; si está en otro espacio, avisa «está en el espacio N ·
   Enter ir». Reutilizar lo posible del módulo `identify`.
3. **App que no responde**: cuando Hyprland detecta una ventana colgada, el shell muestra sobre ella el aviso de Wysun
   («Firefox no responde», barra de espera, Esperar / Forzar cierre) en lugar del diálogo genérico; la ventana se
   ve en gris con un brillo que la recorre. **Decidido con el usuario:** no se cambia `misc:enable_anr_dialog`. El
   shell detecta la apertura del diálogo de Hyprland (`hyprland-dialog`, evento `openwindow` del socket), lo cierra
   y muestra el suyo con las mismas acciones (esperar = descartar; forzar = matar el cliente colgado). Si algo
   falla, el diálogo de Hyprland queda como respaldo.
4. **`Super+Shift+Esc`**: forzar cierre de la ventana activa con confirmación compacta del shell sobre ella
   (`Enter` confirma, `Esc` cancela; la ventana queda marcada con el rol de error).
5. **Avisos con acciones**: «Firefox lleva 3 min al 92 % de CPU», gráfica pequeña, Ver (abre Processes con contexto)
   / Terminar (confirma en el mismo botón) / Silenciar 1 h. **Opcionales**, con umbrales en Settings.
6. **Lanzador** (`apps/shell/modules/launcher`): al escribir el nombre de una app abierta aparece en «En ejecución»
   (con su CPU en vivo), además de en Aplicaciones. El panel lateral (`PreviewPane`) gana un tipo «proceso»:
   miniatura, forma de estado + icono, CPU/Memoria/Procesos que ruedan, gráfica en vivo y acciones con atajo:
   `Enter` ir a la ventana, `Ctrl+Enter` abrir en Processes, `Ctrl+L` localizar, `Ctrl+W` cerrar, `Ctrl+⇧+W`
   forzar. Cerrar pide segunda pulsación en la misma fila y es **ordenado** (no `pkill -x` directo).
   `kill` se mantiene como prefijo con la misma vista previa («Usando más CPU» / «Procesos que coinciden»).

## Retirada del panel actual

- Quitar `processes` de las superficies de `WysunBridge.qml` y su módulo QML; la regla `float` de
  `hyprland.lua`; actualizar `ARCHITECTURE.md`, `docs/wysun.md` y las pruebas que lo mencionan.
- `wysun processes` pasa a `MODULES` de `bin/wysun` (`('app', 'wysun_processes', [])`).

## Lo que queda al constructor

- Reparto interno del paquete (modelo Python ↔ QML, hilos de muestreo), siguiendo `wysun_files`/`wysun_player`
  y `docs/qml-base.md`; componentes nuevos de `WysunM3` (tabla virtualizada, gráfica, contador, forma de estado)
  si son reutilizables, con su entrada en la galería.
- Reutilizar `wysun_services.process_data` y la lógica de `modules/processes/backend.py` (cgroups → app, GPU por
  DRM fdinfo, acciones con señales/`setpriority`).
- Mecanismo de IPC app ↔ shell para miniaturas y localizar (el shell ya expone `wysun-shell` IPC).
- Cómo identificar qué ventana está colgada a partir del diálogo de Hyprland (argumentos del proceso, título,
  `hyprctl clients`).
- Fuente de los tiempos de arranque (inicio de procesos respecto a Hyprland, `systemd-analyze --user`).
- Dónde vive el vigilante de los avisos (shell o residente), con coste mínimo.

## Entregas

1. **App** `wysun_processes` con las cinco secciones y todo el punto de movimiento y aspecto **y**, en la misma
   entrega, retirada del panel del shell (no conviven). Incluye `wysun processes [consulta]` y el atajo.
2. **Integraciones del shell**: miniaturas, localizar, app que no responde, `Super+Shift+Esc`, avisos con acciones
   (con su página de umbrales en Settings).
3. **Lanzador**: «En ejecución», panel lateral de proceso y acciones.

Cada entrega se prueba, se despliega (`./instalar.sh --wysun-only`) y se confirma por separado.

## Llamadas mías (revisables)

- Procesos de otros usuarios: se ven y se puede intentar actuar sobre ellos, pero sin ayudante privilegiado
  (ni polkit ni pkexec). Si el kernel lo rechaza, se explica en el aviso. Subir la prioridad (nice negativo) igual.
- Umbrales de los avisos en `~/.config/wysun/processes.json`; la página va en los Ajustes del shell, junto a las
  existentes.
- Si `Super+Shift+Esc` o `Super+Shift+K` ya tienen otro uso en la configuración activa, se para y se pregunta;
  no hay atajo alternativo.

- Pausar sin diálogo y con «Deshacer»; el resto con confirmación (antes: todo con confirmación).
- CPU por proceso en «% de un núcleo»; los totales, en % de toda la CPU (se indica en la interfaz).
- Avisos desactivados por defecto.
- El lanzador conserva `kill` como prefijo.
