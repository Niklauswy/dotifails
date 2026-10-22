// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// 6c70d5cb: same card API, backed by Wysun Recorder's detached worker and control protocol.
pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: root

    property bool running: false
    property bool paused: false
    property real elapsed: 0
    property int refCount: 0
    property string error: ''

    // What to record and how, remembered between recordings (wysun-recorder --prefs).
    property bool mic: false
    property bool system: true
    property bool cursor: true
    property int countdownSeconds: 3
    property string micDevice: ''
    property bool camera: false
    property string cameraDevice: ''
    property var cameraStyle: ({ shape: 'circle', size: 'medium', corner: 'bottom-right' })
    // Devices to choose from (wysun-recorder --audio-devices).
    property var mics: []
    property var cameras: []
    // Live annotations drawn over the recorded output while recording.
    property bool annotating: false
    readonly property string micName: {
        const found = mics.find(m => micDevice ? m.id === micDevice : m.default);
        return found ? found.name : '';
    }

    // Where the current recording is, to keep the HUD out of the video: the output
    // and the region on it (the whole output for a screen recording).
    property string screenName: ''
    property rect region: Qt.rect(0, 0, 0, 0)
    property bool wholeOutput: false
    // Seconds left before the worker starts, and the request waiting for them.
    property int countdown: 0
    property var pending: null
    // Between asking the worker to start and its first status.
    property bool starting: false
    readonly property bool active: running || starting || countdown > 0

    function start(extraArgs = []): void {
        // The shell's own picker: choose a region, window or screen, then record.
        if (!active)
            Quickshell.execDetached(['wysun-shell', 'picker', 'record']);
    }

    function toggle(): void {
        if (active)
            stop();
        else
            start();
    }

    function refreshPrefs(): void {
        if (!prefs.running)
            prefs.running = true;
        if (!devices.running)
            devices.running = true;
    }

    // Saves a choice of the recording bar and remembers it (wysun-recorder --set-pref).
    function setPref(key: string, value: var): void {
        const text = typeof value === 'boolean' ? (value ? 'true' : 'false') : String(value);
        switch (key) {
        case 'record_mic': mic = value; break;
        case 'record_system': system = value; break;
        case 'record_cursor': cursor = value; break;
        case 'record_camera': camera = value; break;
        case 'record_mic_device': micDevice = text; break;
        case 'camera_device': cameraDevice = text; break;
        case 'camera_corner': case 'camera_shape': case 'camera_size':
            cameraStyle = Object.assign({}, cameraStyle, { [key.slice(7)]: text });
            break;
        }
        Quickshell.execDetached(['wysun-recorder', '--set-pref', key, text]);
    }

    // The chosen area becomes a recording after the countdown (none when it is 0).
    function launch(output: string, area: rect, whole: bool, source: string, geometry: var): void {
        screenName = output;
        region = area;
        wholeOutput = whole;
        error = '';
        Quickshell.execDetached(['sh', '-c', 'printf %s "$1" > "$2"', 'sh', JSON.stringify({ screen: output, x: area.x, y: area.y, width: area.width, height: area.height, whole: whole }), stateFile]);
        pending = { source: source, output: output, rect: geometry, mic: mic, mic_device: micDevice, system: system, cursor: cursor, camera: camera && (cameraDevice !== '' || cameras.length > 0), camera_device: cameraDevice || (cameras.length ? cameras[0].id : '') };
        countdown = countdownSeconds;
        if (countdown <= 0)
            begin();
        else
            ticker.restart();
    }

    function begin(): void {
        ticker.stop();
        countdown = 0;
        if (!pending)
            return;
        starting = true;
        startTimeout.restart();
        Quickshell.execDetached(['wysun-recorder', '--start', JSON.stringify(pending)]);
        pending = null;
    }

    function stop(): void {
        if (countdown > 0) {
            ticker.stop();
            countdown = 0;
            pending = null;
        } else if (!control.running) {
            control.command = ['/usr/bin/python3', Quickshell.shellPath('wysun/backend.py'), 'record-stop'];
            control.running = true;
        }
    }

    function togglePause(): void {
        if (!control.running) {
            control.command = ['/usr/bin/python3', Quickshell.shellPath('wysun/backend.py'), 'record-pause'];
            control.running = true;
        }
    }

    // Where the recording is survives a reload of the shell (the worker keeps going).
    readonly property string stateFile: `${Quickshell.env("XDG_RUNTIME_DIR")}/wysun-recording.json`

    Component.onCompleted: {
        refreshPrefs();
        restore.running = true;
    }

    Process {
        id: restore

        command: ['cat', root.stateFile]
        stdout: StdioCollector {
            onStreamFinished: {
                if (root.screenName)
                    return;
                try {
                    const saved = JSON.parse(text);
                    root.screenName = saved.screen;
                    root.region = Qt.rect(saved.x, saved.y, saved.width, saved.height);
                    root.wholeOutput = saved.whole;
                } catch (error) {
                    // No recording was being followed.
                }
            }
        }
    }

    Process {
        id: prefs

        command: ['wysun-recorder', '--prefs']
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    const values = JSON.parse(text);
                    root.mic = values.record_mic;
                    root.system = values.record_system;
                    root.cursor = values.record_cursor;
                    root.countdownSeconds = values.countdown;
                    root.micDevice = values.record_mic_device;
                    root.camera = values.record_camera;
                    root.cameraDevice = values.camera_device;
                    root.cameraStyle = values.camera_style;
                } catch (error) {
                    console.warn('Recorder: preferences unavailable', error);
                }
            }
        }
    }

    Process {
        id: devices

        command: ['wysun-recorder', '--audio-devices']
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    const found = JSON.parse(text);
                    root.mics = found.mics;
                    root.cameras = found.cameras;
                } catch (error) {
                    console.warn('Recorder: devices unavailable', error);
                }
            }
        }
    }

    Process {
        id: status

        command: ['/usr/bin/python3', Quickshell.shellPath('wysun/backend.py'), 'record-status']
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    const state = JSON.parse(text);
                    root.running = state.running;
                    root.paused = state.paused;
                    root.elapsed = state.elapsed;
                    if (state.running) {
                        root.starting = false;
                        startTimeout.stop();
                    } else if (!root.starting && root.countdown === 0) {
                        root.annotating = false;
                        Quickshell.execDetached(['rm', '-f', root.stateFile]);
                    }
                } catch (error) {
                    root.error = 'Estado de Recorder no disponible';
                }
            }
        }
    }

    Process {
        id: control

        onExited: (code, exitStatus) => {
            root.error = code || exitStatus ? 'Abre Wysun Recorder para revisar la operación' : '';
            status.running = true;
        }
    }

    Timer {
        id: ticker

        interval: 1000
        repeat: true
        onTriggered: {
            root.countdown -= 1;
            if (root.countdown <= 0)
                root.begin();
        }
    }

    Timer {
        id: startTimeout

        interval: 15000
        onTriggered: {
            root.starting = false;
            root.error = 'La grabación no arrancó';
        }
    }

    Timer {
        interval: 1000
        running: root.refCount > 0 || root.starting || root.running
        repeat: true
        triggeredOnStart: true
        onTriggered: if (!status.running)
            status.running = true
    }
}
