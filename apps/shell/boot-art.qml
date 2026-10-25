// Wysun boot art renderer (development tool, used by system/boot/render_assets.py).
// A background layer, not a window: it always receives frames (a window on a hidden workspace would
// not, and the render would wait forever), and it stays behind the user's windows while it works.
import QtQuick
import Quickshell
import Quickshell.Wayland
import "modules/lockscreen"
import "modules/bootart"

ShellRoot {
    LockPalette {
        id: colours
        path: Quickshell.env("WYSUN_BOOT_ART_SCHEME") || ""
    }

    PanelWindow {
        WlrLayershell.layer: WlrLayer.Background
        WlrLayershell.namespace: "wysun-boot-art"
        exclusionMode: ExclusionMode.Ignore
        anchors.top: true
        anchors.left: true
        implicitWidth: 960
        implicitHeight: 540
        color: colours.surface

        BootArt {
            scheme: colours
            scale: 0.5
            transformOrigin: Item.TopLeft
        }
    }
}
