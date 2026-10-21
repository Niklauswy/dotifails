pragma Singleton

import QtQuick
import Quickshell
import Wysun.Config
import Wysun.I18n
import qs.components
import qs.services
import qs.modules.nexus
import "pages/SettingsRoutes.js" as SettingsRoutes

Singleton {
    id: root

    property var routed

    function create(parent: Item, props: var): void {
        nexusComp.createObject(parent ?? dummy, props);
    }

    // Open (or reuse) the settings window on a named route, e.g. "displays" or "workspaces".
    function createRoute(route: string): bool {
        const key = SettingsRoutes.pageRoutes[route];
        const idx = PageRegistry.pages.findIndex(p => p.key === key);
        if (idx < 0)
            return false;
        if (!routed || !routed.visible)
            routed = nexusComp.createObject(dummy, {});
        routed.go(idx, SettingsRoutes.pageSubs[route] ?? -1, "");
        return true;
    }

    QtObject {
        id: dummy
    }

    Component {
        id: nexusComp

        FloatingWindow {
            id: win

            color: Colours.tPalette.m3surface
            surfaceFormat.opaque: false

            // Display trials may temporarily unmap a window while outputs change.
            // Only an explicit close ends the settings window.
            onClosed: destroy()

            implicitWidth: nexus.implicitWidth
            implicitHeight: nexus.implicitHeight

            minimumSize.width: contentItem.Tokens.sizes.nexus.minWidth
            minimumSize.height: contentItem.Tokens.sizes.nexus.minHeight

            contentItem.Config.screen: screen.name
            contentItem.Tokens.screen: screen.name

            function go(idx: int, sub: int, kind: string): void {
                nexus.go(idx, sub, kind);
            }

            title: Tr.tr("Wysun Settings — %1").arg(PageRegistry.pages[nexus.nState.currentPageIdx].label)

            Nexus {
                id: nexus

                anchors.fill: parent
                nState.screen: win.screen
                nState.isWindow: true
                onClose: win.destroy()
            }

            Behavior on color {
                CAnim {}
            }
        }
    }
}
