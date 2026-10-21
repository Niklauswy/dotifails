.pragma library

// Existing Wysun modes remain accessible from the native launcher's > search.
// These are argv arrays, never shell strings, and never replace user actions.
function utilities() {
    return [
        ["Portapapeles aquí", "Historial en el lanzador: > clip, filtra por texto, imagen, color o enlace", "content_paste_search", ["autocomplete", "clip"]],
        ["Archivos aquí", "Buscar archivos por nombre o ruta en el lanzador", "folder_open", ["autocomplete", "files"]],
        ["Snippets aquí", "Fragmentos de texto y abreviaturas en el lanzador", "data_object", ["autocomplete", "snip"]],
        ["Ventanas aquí", "Cambiar de ventana desde el lanzador", "select_window", ["autocomplete", "win"]],
        ["Emoji aquí", "Buscar y copiar un emoji desde el lanzador", "add_reaction", ["autocomplete", "emoji"]],
        ["Historial de cálculos", "Resultados anteriores de la calculadora", "history", ["autocomplete", "hist"]],
        ["Ejecutar comando", "Ejecutar un comando en la terminal: > run <comando>", "terminal", ["autocomplete", "run"]],
        ["Portapapeles", "Historial, favoritos, OCR y opciones del historial", "content_paste", ["wysun", "clipboard"]],
        ["Archivos", "Carpetas, pestañas y búsqueda de archivos", "folder", ["wysun", "files"]],
        ["Snippets", "Fragmentos de texto y abreviaturas", "code", ["wysun", "snippets"]],
        ["Calculadora", "Operaciones y conversiones de Wysun", "calculate", ["wysun", "calculator"]],
        ["Emoji", "Buscar, copiar y pegar símbolos", "emoji_emotions", ["wysun", "emoji"]],
        ["Ventanas", "Buscar y enfocar ventanas abiertas", "view_carousel", ["wysun", "windows"]],
        ["Wysun Music", "Biblioteca, reproducción y descargas", "music_note", ["wysun", "music"]],
        ["Wysun Music Mini", "Controles compactos de reproducción", "album", ["wysun", "music-mini"]],
        ["Wysun Notes", "Notas locales y edición", "notes", ["wysun", "notes"]],
        ["Wysun Colors", "Capturar, convertir y guardar colores", "colorize", ["wysun", "colors"]],
        ["Wysun Processes", "Procesos y recursos del sistema", "memory", ["wysun", "processes"]],
        ["Wysun Tools", "Proyectos, diagnósticos y archivos", "terminal", ["wysun", "tools"]],
        ["Conexiones", "Wi-Fi, Ethernet, Bluetooth, VPN y SSH", "wifi", ["wysun", "connections"]],
        ["Sonido", "Volumen y dispositivos de audio", "volume_up", ["wysun", "audio"]],
        ["Notificaciones", "Historial y modo concentración", "notifications", ["wysun", "notifications"]],
        ["Calendario", "Consultar fechas", "calendar_month", ["wysun", "calendar"]],
        ["Sistema", "Memoria, carga y batería", "monitoring", ["wysun", "system"]],
        ["Sesión", "Bloqueo, suspensión y opciones de energía", "power_settings_new", ["wysun", "power"]],
        ["Wysun Recorder", "Biblioteca y controles de grabación", "videocam", ["wysun", "recorder"]],
        ["Wysun Screenshot", "Biblioteca y captura de pantalla", "screenshot", ["wysun", "screenshot"]],
        ["Wysun Settings", "Pantallas, atajos, reglas, inicio y copias", "settings", ["wysun", "settings"]],
        ["Fondo y estilo", "Cambiar el fondo y las preferencias de color", "wallpaper", ["wysun", "settings", "wallpaper"]],
        ["Efectos y animaciones", "Sombras, desenfoque y velocidad", "animation", ["wysun", "settings", "effects"]],
        ["Terminal", "Abrir la terminal configurada", "terminal", ["wysun-terminal"]],
        ["Sesión (lateral)", "Salir, apagar, suspender o reiniciar", "power_settings_new", ["wysun", "shell", "session"]]
    ].map(function(item) {
        return {name: item[0], description: item[1], icon: item[2], command: item[3], enabled: true, dangerous: false};
    });
}

function entries(configured, enableDangerous) {
    var configuredCommands = configured.map(function(action) { return JSON.stringify(action.command); });
    var added = utilities().filter(function(action) {
        return configuredCommands.indexOf(JSON.stringify(action.command)) < 0;
    });
    return configured.concat(added).filter(function(action) {
        // This inherited argv is invalid: wallpaper_main only accepts `set`.
        if (JSON.stringify(action.command) === '["wysun","wallpaper","-r"]')
            return false;
        if (!action.enabled || (action.dangerous && !enableDangerous))
            return false;
        return true;
    });
}
