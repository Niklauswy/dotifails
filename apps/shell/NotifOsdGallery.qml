// Galería de la fase 4: avisos, ajustes rápidos, sesión y OSD con datos fijos.
// No abre D-Bus, procesos ni dispositivos y no usa las barras reales:
//   QT_QPA_PLATFORM=offscreen WYSUN_THEME=<variante> HOME=<tmp> XDG_STATE_HOME=<tmp> \
//     WYSUN_GALLERY_OUTPUT=<png> quickshell -p apps/shell/NotifOsdGallery.qml
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Quickshell
import "services" as Services
import "modules/osd" as OsdModule
import "modules/quicksettings" as QuickSettingsModule

ShellRoot {
    id: root
    readonly property var entries: [
        { id: "1", appName: "Correo", summary: "Informe de laboratorio", body: "Tu profesora subió la rúbrica del informe final.\nEntrega hasta el viernes.", urgency: "normal", actions: [] },
        { id: "2", appName: "Batería", summary: "Batería baja", body: "Queda el 14 %. Conecta el cargador.", urgency: "critical", actions: [] },
        { id: "3", appName: "Descargas", summary: "Descarga terminada", body: "wysun-demo.iso", urgency: "low", actions: [] }
    ]
    Preferences { id: prefs }
    Services.Colours { id: colours }
    Motion { id: motion; reducedMotion: Quickshell.env("WYSUN_REDUCED_MOTION") === "1" || prefs.appearance.reducedMotion }
    FontLoader {
        source: Quickshell.shellPath("assets/fonts/Rubik-Variable.ttf")
        onStatusChanged: if (status === FontLoader.Ready) Appearance.refreshFonts()
    }
    FontLoader {
        source: Quickshell.shellPath("assets/fonts/MaterialSymbolsRounded.ttf")
        onStatusChanged: if (status === FontLoader.Ready) Appearance.refreshFonts()
    }

    component Stub: QtObject {
        property string surface: ""
        function close() {}
        function show() {}
        function launch() {}
    }

    FloatingWindow {
        id: window
        visible: true
        title: "Avisos, ajustes rápidos y OSD de Wysun"
        implicitWidth: 1500
        implicitHeight: 900
        color: Appearance.canvas

        Item {
            id: scene
            anchors.fill: parent

            Row {
                anchors.fill: parent
                anchors.margins: Appearance.spaceXl
                spacing: Appearance.spaceXl

                QuickSettingsModule.SurfacePanel {
                    width: 460; height: parent.height
                    controller: Stub { surface: "quicksettings" }
                    motion: motion
                    hostActive: true
                    preview: true
                }
                QuickSettingsModule.SurfacePanel {
                    width: 540; height: parent.height
                    controller: Stub { surface: "notifications" }
                    motion: motion
                    hostActive: true
                    preview: true
                    demoEntries: root.entries
                }
                Column {
                    width: 360
                    height: parent.height
                    spacing: Appearance.spaceXl
                    QuickSettingsModule.SurfacePanel {
                        width: parent.width; height: 460
                        controller: Stub { surface: "session" }
                        motion: motion
                        hostActive: true
                        preview: true
                    }
                    OsdModule.OsdContent {
                        width: parent.width
                        motion: motion
                        mode: "volume"
                        volume: 0.42
                    }
                    OsdModule.OsdContent {
                        width: parent.width
                        motion: motion
                        mode: "source-mute"
                        sourceMuted: true
                        sourceVolume: 0.65
                    }
                }
            }

            Timer {
                interval: 2200
                running: true
                onTriggered: {
                    var output = Quickshell.env("WYSUN_GALLERY_OUTPUT") || "/tmp/wysun-f4-gallery.png";
                    scene.grabToImage(function(result) {
                        console.info("WYSUN_GALLERY_CAPTURE", result.saveToFile(output), Appearance.style, Appearance.variant);
                        Qt.quit();
                    });
                }
            }
            Timer {
                interval: 6000
                running: true
                onTriggered: {
                    console.warn("WYSUN_GALLERY_TIMEOUT");
                    Qt.quit();
                }
            }
        }
    }
}
