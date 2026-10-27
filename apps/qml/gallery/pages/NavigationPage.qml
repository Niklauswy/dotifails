// Navigation pieces on their own: tabs, a rail, a drawer and single items. The window itself is the
// AdaptiveNavigation demo: resize it across 600 and 840 px.
import QtQuick
import WysunM3
import ".."

Page {
    id: page

    readonly property var demo: [{header: "Biblioteca"}, {id: "songs", icon: "music_note", label: "Canciones"}, {id: "albums", icon: "album", label: "Álbumes", badge: 3}, {id: "artists", icon: "person", label: "Artistas"}, {divider: true}, {header: "Playlists", action: "add", actionId: "new"}, {id: "lists", icon: "queue_music", label: "Listas", rail: false, trailingIcon: "graphic_eq"}]
    property string current: "albums"

    Section {
        title: "Pestañas"

        TabBar {
            width: Math.min(parent.width, Metrics.textFieldMinWidth * 2.5)
            tabs: [{id: "songs", text: "Canciones", icon: "music_note"}, {id: "albums", text: "Álbumes", icon: "album"}, {id: "artists", text: "Artistas", icon: "person"}]
            currentId: "albums"
        }
        TabBar {
            width: Math.min(parent.width, Metrics.textFieldMinWidth * 2.5)
            variant: "secondary"
            tabs: [{id: "a", text: "Todo"}, {id: "b", text: "Favoritos"}, {id: "c", text: "Recientes"}]
            currentId: "a"
        }
    }

    Section {
        title: "Rail y drawer"
        note: "AdaptiveNavigation elige uno según el ancho de la ventana: < 600 modal, 600-839 rail, ≥ 840 drawer."

        Rectangle {
            width: Metrics.railWidth
            height: Metrics.drawerItemHeight * 6
            color: Theme.m3surface
            border.width: Metrics.outlineWidth
            border.color: Theme.m3outlineVariant
            radius: Theme.rounding.large ?? 0

            NavigationRail {
                height: parent.height
                menuButton: true
                destinations: page.demo
                currentId: page.current
                onSelected: id => page.current = id
            }
        }

        NavigationDrawer {
            height: Metrics.drawerItemHeight * 6
            destinations: page.demo
            currentId: page.current
            onSelected: id => page.current = id
        }

        Column {
            width: Metrics.drawerWidth

            NavigationItem {
                width: parent.width
                destination: ({id: "x", icon: "inbox", label: "NavigationItem activo", trailing: "8"})
                active: true
            }
            NavigationItem {
                width: parent.width
                destination: ({id: "y", icon: "send", label: "NavigationItem"})
            }
        }
    }
}
