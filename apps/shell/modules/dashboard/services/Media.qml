// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun
// Origen: services/Players.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Avisos y licencia íntegra: THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
import QtQuick
import Quickshell.Services.Mpris
import "../Logic.js" as Logic

QtObject {
    id: root
    property var players: Mpris.players.values
    property var manualActive: null
    property var active: null
    readonly property string title: active?.trackTitle || "Sin reproducción"
    readonly property string artist: active?.trackArtist || ""
    readonly property string album: active?.trackAlbum || ""
    readonly property string artwork: Logic.localArtwork(active?.trackArtUrl || "")
    function select(player) {
        if (players.indexOf(player) < 0) return false;
        manualActive = player;
        refresh();
        return true;
    }
    function refresh() { active = Logic.activePlayer(players, manualActive, active); }
    // Reading isPlaying in this binding keeps selection reactive when a stopped
    // player starts, without replacing a user's explicit selection.
    readonly property string playbackSignature: players.map(p => p.dbusName + ":" + p.isPlaying).join("|")
    onPlaybackSignatureChanged: refresh()
    onPlayersChanged: { if (players.indexOf(manualActive) < 0) manualActive = null; refresh(); }
    Component.onCompleted: refresh()
    function previous() { if (!active?.canControl || !active.canGoPrevious) return false; active.previous(); return true; }
    function next() { if (!active?.canControl || !active.canGoNext) return false; active.next(); return true; }
    function toggle() { if (!active?.canControl || !active.canTogglePlaying) return false; active.togglePlaying(); return true; }
}
