.pragma library

// Native desktop sections. `sub` is the index of the sub-page in the Escritorio
// StackPage (see PageCompRegistry); `kind` selects the form shown by ComponentPage.
var sections = [
    {route: "displays", title: "Pantallas", description: "Distribución, escala y prueba con reversión", icon: "monitor", sub: 1},
    {route: "workspaces", title: "Escritorios", description: "Números fijos por pantalla", icon: "view_carousel", sub: 2},
    {route: "shortcuts", title: "Atajos", description: "Consultar, grabar y editar combinaciones", icon: "keyboard", sub: 3},
    {route: "rules", title: "Ventanas y reglas", description: "Espacios, bordes y comportamiento por aplicación", icon: "rule", sub: 5},
    {route: "effects", title: "Efectos y animaciones", description: "Sombras, desenfoque y movimiento", icon: "animation", sub: 7, kind: "effects"},
    {route: "terminal", title: "Terminal", description: "Fuente, colores y espacio de Ghostty", icon: "terminal", sub: 7, kind: "terminal"},
    {route: "notifications", title: "Notificaciones", description: "Posición, tamaño y duración de los avisos", icon: "notifications", sub: 7, kind: "notifications"},
    {route: "startup", title: "Inicio y aplicaciones", description: "Aplicaciones al iniciar la sesión", icon: "play_circle", sub: 8},
    {route: "files", title: "Archivos y copias", description: "Configuración y restauración de respaldos", icon: "restore", sub: 9}
];

// Routes handled by other Nexus pages: route -> page key in PageRegistry.
var pageRoutes = {
    wallpaper: "wallpaper",
    theme: "wallpaper",
    shell: "panels",
    network: "network",
    wifi: "network",
    vpn: "network",
    connections: "network",
    bluetooth: "bluetooth",
    audio: "audio",
    ssh: "ssh",
    processes: "processes",
    home: "desktop",
    desktop: "desktop"
};

// Routes that open a sub-page of their page.
var pageSubs = {theme: 3};

function section(route) {
    return sections.find(function(s) { return s.route === route; }) || null;
}
