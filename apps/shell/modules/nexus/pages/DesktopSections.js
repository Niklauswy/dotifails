.pragma library

// These routes belong to the existing settings IPC. Keep the functional
// tools until their native controls have equivalent safety and behaviour.
var sections = [
    {route: "home", title: "Resumen", description: "Preferencias y herramientas del escritorio", icon: "settings"},
    {route: "displays", title: "Pantallas", description: "Distribución, escala y prueba con reversión", icon: "monitor"},
    {route: "workspaces", title: "Escritorios", description: "Nombres, orden y salidas", icon: "view_carousel"},
    {route: "wallpaper", title: "Fondo y estilo", description: "Fondos, temas y color dinámico", icon: "palette"},
    {route: "shell", title: "Paneles", description: "Preferencias del riel, marco y salidas", icon: "dock_to_left"},
    {route: "shortcuts", title: "Atajos", description: "Consultar y editar combinaciones", icon: "keyboard"},
    {route: "rules", title: "Reglas de ventanas", description: "Comportamiento por aplicación", icon: "rule"},
    {route: "effects", title: "Efectos y animaciones", description: "Sombras, desenfoque y movimiento", icon: "animation"},
    {route: "terminal", title: "Terminal", description: "Fuente y preferencias de Ghostty", icon: "terminal"},
    {route: "startup", title: "Inicio y aplicaciones", description: "Aplicaciones al iniciar la sesión", icon: "play_circle"},
    {route: "files", title: "Archivos y copias", description: "Consultar y restaurar respaldos de ajustes", icon: "restore"}
];

function command(route) {
    if (!sections.some(function(section) { return section.route === route; }))
        return [];
    return ["wysun", "settings", route];
}
