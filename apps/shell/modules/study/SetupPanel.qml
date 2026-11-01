pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Templates
import Quickshell
import Wysun.Config
import qs.components
import qs.components.controls
import qs.services

// Setup panel (option B, Material 3 Expressive): duration slider, rhythm group, blocked apps, hide time.
Column {
    id: root

    // Up to 3 h: past a few hours of deep focus, study gets less effective, not more.
    readonly property var steps: [30, 60, 90, 120, 150, 180]
    property int stepIndex: indexFor(Study.prefs.duration)
    property int rhythm: Study.prefs.rhythm
    property bool hideTime: Study.prefs.hideTime
    property var known: Study.prefs.blocked.slice()
    property var blocked: Study.prefs.blocked.slice()
    property bool adding
    readonly property int duration: steps[stepIndex]
    // Keyboard: focused row (0 duration, 1 rhythm, 2 blocked apps, 3 hide time, 4 start) and chip in row 2.
    property int row: 4
    property int chip: 0
    readonly property var rhythms: [25, 50, 90]

    signal start(var config)

    // Back to the remembered choices each time the panel opens.
    function indexFor(duration: int): int {
        const i = steps.indexOf(duration);
        return i >= 0 ? i : steps.indexOf(120);
    }

    function reset(): void {
        row = 4;
        chip = 0;
        stepIndex = indexFor(Study.prefs.duration);
        rhythm = Study.prefs.rhythm;
        hideTime = Study.prefs.hideTime;
        known = Study.prefs.blocked.slice();
        blocked = Study.prefs.blocked.slice();
        adding = false;
        search.text = "";
    }

    function config(): var {
        return {duration: duration, rhythm: rhythm, blocked: blocked, hideTime: hideTime};
    }

    // Arrows move between rows and change the value in the row; Space toggles; Enter starts.
    // Returns false for keys it does not use (Escape is the surface's).
    function handleKey(event: var): bool {
        const k = event.key;
        if (adding)
            return false;
        if (k === Qt.Key_Up || k === Qt.Key_Backtab || (k === Qt.Key_Tab && (event.modifiers & Qt.ShiftModifier))) {
            row = Math.max(0, row - 1);
        } else if (k === Qt.Key_Down || k === Qt.Key_Tab) {
            row = Math.min(4, row + 1);
        } else if (k === Qt.Key_Left || k === Qt.Key_Right) {
            const d = k === Qt.Key_Left ? -1 : 1;
            if (row === 0)
                stepIndex = Math.max(0, Math.min(steps.length - 1, stepIndex + d));
            else if (row === 1)
                rhythm = rhythms[(rhythms.indexOf(rhythm) + d + rhythms.length) % rhythms.length];
            else if (row === 2)
                chip = Math.max(0, Math.min(known.length, chip + d));
            else if (row === 3)
                hideTime = d > 0;
        } else if (k === Qt.Key_Space) {
            if (row === 2)
                chip < known.length ? toggleApp(known[chip]) : (adding = true);
            else if (row === 3)
                hideTime = !hideTime;
            else if (row === 4)
                start(config());
        } else if (k === Qt.Key_Return || k === Qt.Key_Enter) {
            if (row === 2 && chip === known.length)
                adding = true;
            else
                start(config());
        } else {
            return false;
        }
        return true;
    }

    function formatDuration(m: int): string {
        return m >= 60 ? (m % 60 ? `${Math.floor(m / 60)} h ${m % 60}` : `${m / 60} h`) : `${m} min`;
    }

    function appName(cls: string): string {
        return Study.appName(cls);
    }

    function toggleApp(cls: string): void {
        blocked = blocked.includes(cls) ? blocked.filter(c => c !== cls) : blocked.concat([cls]);
    }

    function addApp(cls: string): void {
        if (!known.includes(cls))
            known = known.concat([cls]);
        if (!blocked.includes(cls))
            blocked = blocked.concat([cls]);
        adding = false;
        search.text = "";
    }

    width: Tokens.padding.extraExtraLarge * 9
    padding: Tokens.padding.extraLarge - Tokens.padding.extraSmall
    spacing: 0

    StyledText {
        text: "Sesión de estudio"
        font: Tokens.font.headline.small
    }

    StyledText {
        topPadding: Tokens.spacing.extraSmall
        text: Study.summaryLine(root.duration, root.rhythm)
        color: Colours.palette.m3onSurfaceVariant
        font: Tokens.font.body.medium
        animate: true
    }

    component Label: StyledText {
        topPadding: Tokens.spacing.extraLarge - Tokens.spacing.extraSmall
        bottomPadding: Tokens.spacing.small
        font: Tokens.font.title.small
    }

    Item {
        width: root.width - root.leftPadding - root.rightPadding
        implicitHeight: durationLabel.implicitHeight

        Label {
            id: durationLabel

            text: "Duración"
        }

        StyledText {
            anchors.right: parent.right
            anchors.baseline: durationLabel.baseline
            text: root.formatDuration(root.duration)
            color: Colours.palette.m3primary
            font: Tokens.font.title.small
        }
    }

    StyledSlider {
        id: slider

        width: root.width - root.leftPadding - root.rightPadding
        implicitHeight: Tokens.padding.extraLarge
        from: 0
        to: root.steps.length - 1
        stepSize: 1
        snapMode: Slider.SnapAlways
        value: root.stepIndex
        // StyledSlider handles the drag itself and reports the position (0..1) through `interaction`.
        onInteraction: v => root.stepIndex = Math.round(v * (root.steps.length - 1))

        FocusRing {
            on: root.row === 0
            gap: Tokens.padding.small
            radius: Tokens.rounding.medium
        }
    }

    Item {
        width: root.width - root.leftPadding - root.rightPadding
        implicitHeight: tick30.implicitHeight + Tokens.spacing.extraSmall

        component Tick: StyledText {
            y: Tokens.spacing.extraSmall
            color: Colours.palette.m3onSurfaceVariant
            font: Tokens.font.label.small
        }

        Tick {
            id: tick30

            text: "30 min"
        }
        Tick {
            anchors.right: parent.right
            text: "3 h"
        }
    }

    Label {
        text: "Ritmo"
    }

    RhythmGroup {
        width: root.width - root.leftPadding - root.rightPadding
        keyFocus: root.row === 1
        current: root.rhythm
        onPicked: value => root.rhythm = value
    }

    Label {
        text: "Bloqueadas"
    }

    Flow {
        width: root.width - root.leftPadding - root.rightPadding
        spacing: Tokens.spacing.small

        Repeater {
            model: root.known

            FilterChip {
                required property string modelData
                required property int index

                keyFocus: root.row === 2 && root.chip === index
                text: root.appName(modelData)
                selected: root.blocked.includes(modelData)
                onClicked: root.toggleApp(modelData)
            }
        }

        FilterChip {
            keyFocus: root.row === 2 && root.chip === root.known.length
            text: "Añadir"
            icon: "add"
            onClicked: root.adding = !root.adding
        }
    }

    // Installed apps to add, filtered as you type.
    Column {
        width: root.width - root.leftPadding - root.rightPadding
        visible: root.adding
        topPadding: Tokens.spacing.small
        spacing: Tokens.spacing.small

        StyledTextField {
            id: search

            width: parent.width
            placeholderText: "Buscar app"
            onVisibleChanged: if (visible) forceActiveFocus()
            // Enter adds the first match; Escape goes back to the panel.
            Keys.onReturnPressed: if (appList.count > 0) root.addApp(appList.model[0].startupClass || appList.model[0].id)
            Keys.onEscapePressed: {
                root.adding = false;
                text = "";
            }
        }

        ListView {
            id: appList

            width: parent.width
            height: Math.min(contentHeight, Tokens.padding.extraExtraLarge * 4)
            clip: true
            model: DesktopEntries.applications.values.filter(a => !a.noDisplay && a.name.toLowerCase().includes(search.text.toLowerCase())
                                                             && !root.known.includes(a.startupClass || a.id)).slice(0, 40)

            delegate: StyledRect {
                id: entry

                required property var modelData

                width: ListView.view.width
                implicitHeight: Tokens.padding.extraExtraLarge - Tokens.padding.small
                radius: Tokens.rounding.medium
                color: hover.containsMouse ? Colours.palette.m3surfaceContainerHigh : "transparent"

                Row {
                    anchors.verticalCenter: parent.verticalCenter
                    x: Tokens.padding.small
                    spacing: Tokens.spacing.medium

                    AppIcon {
                        anchors.verticalCenter: parent.verticalCenter
                        name: entry.modelData.icon
                        size: Tokens.font.icon.medium.pointSize * 1.6
                    }

                    StyledText {
                        anchors.verticalCenter: parent.verticalCenter
                        text: entry.modelData.name
                        font: Tokens.font.body.medium
                    }
                }

                MouseArea {
                    id: hover

                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.addApp(entry.modelData.startupClass || entry.modelData.id)
                }
            }
        }
    }

    Item {
        width: root.width - root.leftPadding - root.rightPadding
        implicitHeight: Math.max(hideText.implicitHeight, hideSwitch.implicitHeight) + Tokens.spacing.extraLarge - Tokens.spacing.extraSmall

        Column {
            id: hideText

            anchors.left: parent.left
            anchors.right: hideSwitch.left
            anchors.bottom: parent.bottom

            StyledText {
                text: "Ocultar el tiempo"
                font: Tokens.font.body.large
            }

            StyledText {
                text: "Solo verás los minutos si los pides"
                color: Colours.palette.m3onSurfaceVariant
                font: Tokens.font.body.medium
            }
        }

        FocusRing {
            on: root.row === 3
            gap: Tokens.padding.small
            radius: Tokens.rounding.medium
        }

        StyledSwitch {
            id: hideSwitch

            anchors.right: parent.right
            anchors.verticalCenter: hideText.verticalCenter
            checked: root.hideTime
            onToggled: root.hideTime = checked
        }
    }

    Item {
        width: 1
        height: Tokens.spacing.extraLarge - Tokens.spacing.extraSmall
    }

    ActionButton {
        width: root.width - root.leftPadding - root.rightPadding
        large: true
        keyFocus: root.row === 4
        text: "Empezar"
        onClicked: root.start(root.config())
    }
}
