// Replaces the page it shows with an exit (the outgoing page) followed by an enter (the incoming one). The pattern
// components (FadeThrough, SharedAxis) are this with their start/end states set; a page fills the host.
import QtQuick
import WysunM3

Item {
    id: root

    // Where the outgoing page ends and where the incoming one starts.
    property real exitOpacity: 0
    property real exitX: 0
    property real exitY: 0
    property real exitScale: 1
    property real enterOpacity: 0
    property real enterX: 0
    property real enterY: 0
    property real enterScale: 1
    // Fades are effects, moves are spatial (Motion kinds).
    property string exitFadeKind: "fastEffects"
    property string exitMoveKind: "fastSpatial"
    property string enterFadeKind: "defaultEffects"
    property string enterMoveKind: "defaultSpatial"

    readonly property bool exitMoves: exitX !== 0 || exitY !== 0 || exitScale !== 1
    readonly property bool enterMoves: enterX !== 0 || enterY !== 0 || enterScale !== 1
    readonly property int exitDuration: Math.max(Motion.ms(exitFadeKind), exitMoves ? Motion.ms(exitMoveKind) : 0)
    readonly property int enterDuration: Math.max(Motion.ms(enterFadeKind), enterMoves ? Motion.ms(enterMoveKind) : 0)
    readonly property int totalDuration: exitDuration + enterDuration

    readonly property Item currentItem: _current
    readonly property bool running: seq.running

    // Emitted before a page is shown so a pattern can aim its states (forward: deeper / next).
    signal aboutToShow(bool forward)
    signal finished

    property Item _current
    property Item _outgoing

    function show(component: Component, properties: var, forward: bool): Item {
        if (seq.running)
            seq.complete();
        _finish();
        aboutToShow(forward !== false);
        const incoming = component.createObject(root, properties ?? ({}));
        if (!incoming) {
            console.warn("WysunM3: could not create the page: " + component.errorString());
            return null;
        }
        incoming.width = Qt.binding(() => root.width);
        incoming.height = Qt.binding(() => root.height);
        const outgoing = _current;
        _current = incoming;
        if (!outgoing) // the first page just appears
            return incoming;
        outgoing.enabled = false;
        if (Motion.reduced) {
            outgoing.destroy();
            finished();
            return incoming;
        }
        _outgoing = outgoing;
        incoming.opacity = enterOpacity;
        incoming.x = enterX;
        incoming.y = enterY;
        incoming.scale = enterScale;
        exitFade.target = outgoing;
        exitX_.target = outgoing;
        exitY_.target = outgoing;
        exitScale_.target = outgoing;
        for (const a of [enterFade, enterX_, enterY_, enterScale_])
            a.target = incoming;
        seq.start();
        return incoming;
    }

    // Grouped animations do not see Anim's own reduced-motion handling: finish the whole sequence here.
    readonly property bool _reduced: Motion.reduced
    on_ReducedChanged: {
        if (_reduced && seq.running)
            seq.complete();
    }

    function _finish(): void {
        if (_outgoing) {
            _outgoing.destroy();
            _outgoing = null;
            if (_current) {
                _current.opacity = 1;
                _current.x = 0;
                _current.y = 0;
                _current.scale = 1;
            }
            finished();
        }
    }

    SequentialAnimation {
        id: seq

        onRunningChanged: {
            if (!running)
                root._finish();
        }

        ParallelAnimation {
            Anim {
                id: exitFade

                property: "opacity"
                to: root.exitOpacity
                kind: root.exitFadeKind
            }
            Anim {
                id: exitX_

                property: "x"
                to: root.exitX
                kind: root.exitMoveKind
                duration: root.exitMoves ? Motion.ms(kind) : 0
            }
            Anim {
                id: exitY_

                property: "y"
                to: root.exitY
                kind: root.exitMoveKind
                duration: root.exitMoves ? Motion.ms(kind) : 0
            }
            Anim {
                id: exitScale_

                property: "scale"
                to: root.exitScale
                kind: root.exitMoveKind
                duration: root.exitMoves ? Motion.ms(kind) : 0
            }
        }

        ScriptAction {
            script: {
                if (root._outgoing)
                    root._outgoing.visible = false;
            }
        }

        ParallelAnimation {
            Anim {
                id: enterFade

                property: "opacity"
                to: 1
                kind: root.enterFadeKind
            }
            Anim {
                id: enterX_

                property: "x"
                to: 0
                kind: root.enterMoveKind
                duration: root.enterMoves ? Motion.ms(kind) : 0
            }
            Anim {
                id: enterY_

                property: "y"
                to: 0
                kind: root.enterMoveKind
                duration: root.enterMoves ? Motion.ms(kind) : 0
            }
            Anim {
                id: enterScale_

                property: "scale"
                to: 1
                kind: root.enterMoveKind
                duration: root.enterMoves ? Motion.ms(kind) : 0
            }
        }
    }
}
