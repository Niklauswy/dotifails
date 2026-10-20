pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import "services" as Services
import "modules/rail" as RailModule
import "modules/popouts" as PopoutModule
import "components" as Components

ShellRoot {
    id: root
    readonly property var sampleWorkspaces: [
        { id: 1, name: "1", active: false, activate: function() {} },
        { id: 2, name: "2", active: true, activate: function() {} },
        { id: 3, name: "3", active: false, activate: function() {} },
        { id: 4, name: "4", active: false, activate: function() {} },
        { id: 5, name: "5", active: false, activate: function() {} }
    ]
    Preferences { id: prefs }
    Services.Colours { id: colours }
    Motion { id: motion; reducedMotion: prefs.appearance.reducedMotion }
    SystemClock { id: clock; precision: SystemClock.Minutes }
    FontLoader {
        source: Quickshell.shellPath("assets/fonts/Rubik-Variable.ttf")
        onStatusChanged: if (status === FontLoader.Ready) Appearance.refreshFonts()
    }

    Connections {
        target: colours
        function onNameChanged() {
            if (colours.dynamic) console.info("WYSUN_SCHEME_APPLIED", colours.name, colours.mode, colours.roles.primary)
        }
    }

    Connections {
        target: Appearance
        function onVariantChanged() {
            console.info("WYSUN_THEME_APPLIED", Appearance.style, Appearance.variant)
        }
    }
    FontLoader {
        source: Quickshell.shellPath("assets/fonts/MaterialSymbolsRounded.ttf")
        onStatusChanged: if (status === FontLoader.Ready) Appearance.refreshFonts()
    }

    QtObject {
        id: previewController
        function toggle(kind, name, x, y) {}
        function launch(command) {}
        function close() {}
    }

    Item {
        id: motionProbe
        property real progress: 0
        Behavior on progress {
            Components.Anim { motion: motion; type: Components.Anim.Emphasized }
        }
        Timer { interval: 100; running: true; repeat: false; onTriggered: motionProbe.progress = 1 }
    }

    FloatingWindow {
        id: preview
        visible: true
        title: "Vista previa de Wysun"
        implicitWidth: 1280
        implicitHeight: 800
        color: Appearance.canvas

        Item {
            id: scene
            anchors.fill: parent

            Rectangle {
                anchors.fill: parent
                anchors.margins: Appearance.frameInset
                color: "transparent"
                radius: Appearance.frameRadius
                border.width: Appearance.frameThickness
                border.color: Appearance.materialEdge
                antialiasing: true
            }

            RailModule.RailContent {
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                width: Appearance.railWidth
                controller: previewController
                clock: clock
                motion: motion
                screenName: "Vista previa"
                activeTitle: "Informe de laboratorio · Wysun"
                workspaces: root.sampleWorkspaces
                trayOwner: true
                trayItems: []
                volumePercent: 42
                hasBattery: true
                batteryPercentage: 0.81
            }

            PopoutModule.PopoutCard {
                x: (parent.width - width) / 2
                y: (parent.height - height) / 2
                width: 560
                height: 340
                controller: previewController
                motion: motion
                monitorName: "Pantalla de vista previa"
                contentOpacity: 1
            }

            Timer {
                interval: 1800
                running: true
                repeat: false
                onTriggered: {
                    var output = Quickshell.env("WYSUN_PREVIEW_OUTPUT") || "/tmp/wysun-caelestia-preview.png";
                    var started = scene.grabToImage(function(result) {
                        console.info("WYSUN_PREVIEW_CAPTURE", result.save(output), colours.dynamic, colours.name, colours.roles.primary, Appearance.style, Appearance.variant);
                        Qt.quit();
                    });
                    console.info("WYSUN_CAPTURE_REQUEST", started, scene.visible, scene.width, scene.height, preview.visible, preview.width, preview.height);
                }
            }

            Timer {
                interval: 3500
                running: true
                repeat: false
                onTriggered: {
                    console.warn("WYSUN_PREVIEW_CAPTURE_TIMEOUT", colours.dynamic, colours.name, colours.roles.primary, Appearance.style, Appearance.variant);
                    Qt.quit();
                }
            }
        }
    }
}
