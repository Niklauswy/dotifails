// Shows snackbars one at a time, first in first out, at the bottom of the area it fills. show({text, action?,
// duration? (ms), longer?, closable?}) or show("text"); without a duration a snackbar stays 4 s (10 s `longer`),
// the M3 guidance. The action dismisses it and emits actionTriggered(action); a timeout, close or dismiss()
// emits dismissed(text).
import QtQuick
import WysunM3

Item {
    id: root

    property var _queue: []
    property var _current: null
    readonly property string currentText: _current ? _current.text ?? "" : ""
    readonly property int queued: _queue.length

    signal actionTriggered(string action)
    signal dismissed(string text)

    function show(options) {
        const entry = typeof options === "string" ? {
            text: options
        } : options;
        _queue = _queue.concat([entry]);
        if (!_current)
            _next();
    }

    function dismiss() {
        if (!_current)
            return;
        const text = currentText;
        _close();
        dismissed(text);
        _next();
    }

    function _close() {
        timer.stop();
        _current = null;
    }

    function _next() {
        if (_current || _queue.length === 0)
            return;
        _current = _queue[0];
        _queue = _queue.slice(1);
        timer.interval = _current.duration ?? Theme.duration("extraLarge") * (_current.longer ? Metrics.snackbarLongFactor : Metrics.snackbarShortFactor);
        timer.restart();
    }

    Timer {
        id: timer

        onTriggered: root.dismiss()
    }

    Snackbar {
        id: bar

        readonly property real margin: Theme.padding.large ?? 0

        x: (root.width - width) / 2
        y: root._current ? root.height - height - margin : root.height
        maxWidth: Math.min(Metrics.snackbarMaxWidth, root.width - 2 * margin)
        visible: y < root.height
        opacity: root._current ? 1 : 0
        text: root._current?.text ?? text
        actionText: root._current?.action ?? ""
        closable: !!root._current?.closable
        onAction: {
            const action = actionText;
            root._close();
            root.actionTriggered(action);
            root._next();
        }
        onCloseRequested: root.dismiss()

        SpringBehavior on y {
            kind: "fastSpatial"
        }
        SpringBehavior on opacity {
            kind: "fastEffects"
        }
    }
}
