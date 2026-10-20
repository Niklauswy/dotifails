// Fixture providers shared by the offscreen dashboard view and the Quickshell
// load test. No MPRIS, /proc, df, sysfs or Hyprland is touched.
import QtQuick

QtObject {
    id: root
    property bool empty: false
    readonly property var providers: empty ? emptyProviders : fullProviders

    property QtObject player: QtObject {
        property string identity: "Wysun Music"
        property bool isPlaying: true
        property bool canControl: true
        property bool canGoPrevious: true
        property bool canGoNext: true
        property bool canTogglePlaying: true
        property bool canSeek: true
        property bool lengthSupported: true
        property bool positionSupported: true
        property real length: 215
        property real position: 84
    }
    property QtObject mediaFixture: QtObject {
        property var players: [root.player]
        property var active: root.player
        property string title: "Canción de prueba"
        property string artist: "Artista local"
        property string album: "Álbum sin conexión"
        property string artwork: ""
        function select(p) { return true; }
        function previous() { return true; }
        function next() { return true; }
        function toggle() { root.player.isPlaying = !root.player.isPlaying; return true; }
    }
    property QtObject fullProviders: QtObject {
        property var metrics: ({ cpu: 34, memory: 62, storage: 81, cpuTemperature: 58, gpu: 12, gpuTemperature: 49 })
        property var media: root.mediaFixture
        property var workspaces: [
            { id: 1, name: "1", active: false, focused: false, activate: function() {} },
            { id: 2, name: "2", active: true, focused: true, activate: function() {} },
            { id: 3, name: "3", active: false, focused: false, activate: function() {} }
        ]
        property var windows: [
            { title: "Informe de laboratorio — Wysun", workspace: { id: 2 }, wayland: {} },
            { title: "Terminal", workspace: { id: 2 }, wayland: {} },
            { title: "Navegador", workspace: { id: 1 }, wayland: {} }
        ]
    }
    // Every provider absent: the dashboard must say "No disponible", never 0 %.
    property QtObject emptyProviders: QtObject {
        property var metrics: ({ cpu: null, memory: null, storage: null, cpuTemperature: null, gpu: null, gpuTemperature: null })
        property var media: null
        property var workspaces: []
        property var windows: []
    }
}
