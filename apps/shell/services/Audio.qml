// Adaptado de caelestia-dots/shell/services/Audio.qml (GPL-3.0),
// modificado para Wysun. Fuente: caelestia-dots/shell, commit
// 507d66285e9d9fde9330adc64159cfdebb28c19a. Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
// Wysun adaptation: no CavaProvider, no plugin imports and no toast. The default
// PipeWire sink/source are the single source of truth for the OSD and controls.
import QtQuick
import Quickshell
import Quickshell.Services.Pipewire

Scope {
    id: root

    readonly property var sink: Pipewire.defaultAudioSink
    readonly property var source: Pipewire.defaultAudioSource
    readonly property bool available: !!sink
    readonly property bool sourceAvailable: !!source
    readonly property real volume: sink?.audio?.volume ?? 0
    readonly property bool muted: !!sink?.audio?.muted
    readonly property real sourceVolume: source?.audio?.volume ?? 0
    readonly property bool sourceMuted: !!source?.audio?.muted
    readonly property string sinkName: sink?.description || sink?.name || ""
    readonly property string sourceName: source?.description || source?.name || ""
    readonly property real maxVolume: 1.0
    readonly property string error: available ? "" : "No hay una salida de audio PipeWire"

    // Ignore the value populated during shell start-up; only later changes are OSD events.
    property bool settled: false
    property real lastVolume: 0
    property real lastSourceVolume: 0
    signal changed(string channel)

    PwObjectTracker {
        objects: [root.sink, root.source].filter(node => node !== null && node !== undefined)
    }

    Timer {
        id: settle
        interval: 350
        onTriggered: {
            root.settled = true;
            root.lastVolume = root.volume;
            root.lastSourceVolume = root.sourceVolume;
        }
    }

    onSinkChanged: {
        root.settled = false;
        settle.restart();
    }
    onSourceChanged: {
        root.settled = false;
        settle.restart();
    }
    onVolumeChanged: {
        if (!settled) return;
        if (Math.abs(volume - lastVolume) < 0.0001) return;
        lastVolume = volume;
        changed("volume");
    }
    onMutedChanged: if (settled) changed("mute")
    onSourceVolumeChanged: {
        if (!settled) return;
        if (Math.abs(sourceVolume - lastSourceVolume) < 0.0001) return;
        lastSourceVolume = sourceVolume;
        changed("source-volume");
    }
    onSourceMutedChanged: if (settled) changed("source-mute")

    function setVolume(value) {
        if (!sink?.audio) return false;
        sink.audio.muted = false;
        sink.audio.volume = Math.max(0, Math.min(maxVolume, Number(value) || 0));
        return true;
    }
    function setSourceVolume(value) {
        if (!source?.audio) return false;
        source.audio.muted = false;
        source.audio.volume = Math.max(0, Math.min(maxVolume, Number(value) || 0));
        return true;
    }
    function toggleMuted() {
        if (!sink?.audio) return false;
        sink.audio.muted = !sink.audio.muted;
        return true;
    }
    function toggleSourceMuted() {
        if (!source?.audio) return false;
        source.audio.muted = !source.audio.muted;
        return true;
    }
}
