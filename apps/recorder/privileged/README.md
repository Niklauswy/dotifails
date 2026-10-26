# Broker temporal de botones del ratón

Fuente `wysun-pointer-helper`; la instalación del integrador lo copia como archivo
root-owned a `/usr/libexec/wysun-pointer-helper` con una acción polkit específica
sin autorización retenida. No ejecutarlo mediante pkexec desde una copia de usuario.
El propio entrypoint exige ruta fija, `python3 -I`, propietario root y padres sin
escritura de usuario. Solo importa biblioteca estándar; no importa código de apps,
HOME, PYTHONPATH ni configuración del cliente.

CLI: PID decimal canónico del worker y nonce aleatorio de64hex. El helper deriva
`/run/user/UID/wysun-pointer/PID.NONCE.sock` desde PKEXEC_UID; verifica directorios
UID0700/socketUID0600, sin symlinks, SO_PEERCRED y PID/starttime/pidfd. La autoridad
de usuario/seat/Active/LockedHint/Remote viene de logind, no de JSON cliente.

El socket admite únicamente `RUN`, `PAUSE`, `PING`, `STOP` (líneas≤128B). PAUSE,
EOF, muerte/reutilización de PID, cambio de seat/sesión, lock, heartbeat>3s y límite
4h cierran los descriptores. El broker vuelve a comprobar la autoridad antes de
emitir eventos. stdout es un pipe anónimo no bloqueante; presión o protocolo
inválido terminan el broker. No se entregan descriptores de dispositivos al cliente.

Los dispositivos se eligen desde sysfs/udev del seat, exclusivamente mouse/touchpad
sin flag teclado. Se comprueba identidad al abrir sin seguir symlinks, y después
`EVIOCGBIT(EV_KEY,96)` sobre el FD abierto: se rechazan capacidades de teclado o
ajenas a puntero, incluyendo reemplazo hotplug entre inventario y open. No hay
EVIOCGRAB, TakeControl/force, cambios de permisos, grupos ni ACL. De los eventos
leídos solo salen `{t,button,value}` para BTN_LEFT/RIGHT/MIDDLE; no scancodes,
caracteres, modifiers ni eventos de teclado.

Recorder pide autorización por grabación solamente si se seleccionan clics. Halo
/estela sin clics usan posición Hyprland IPC sin elevar privilegios. Una denegación
conserva el cursor Embedded y puede mantener halo/estela sin botones. La posición
se transforma con metadatos del monitor autorizado y el crop de región; solo se
persisten muestras dentro del área en `.cursor.jsonl`, formato histórico. Los
efectos se aplican al exportar sin dibujar una segunda flecha. Wayland conserva
forma/tamaño del cursor del compositor. El modo WINDOW y efectos en vivo no tienen
paridad aquí; el panel lo explica. No se agrega observación de teclas.

Verificación actual: funciones puras, guardas, pipes y eventos sintéticos; revisión
negativa independiente coordinada con worker3. Ninguna lectura de dispositivos
reales, autorización polkit real, instalación ni activación en host. Pruebas con
privilegios reales y medición de coste logind/IPC siguen pendientes de coordinación;
los tests unitarios no demuestran toda la frontera kernel/policy.
