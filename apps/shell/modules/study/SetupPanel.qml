pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Templates
import Quickshell
import Wysun.Config
import qs.components
import qs.components.controls
import qs.services

// Setup panel (option B, Material 3 Expressive): duration slider, rhythm group, allowed apps, hide time.
Column {
    id: root

    readonly property var steps: [30, 60, 90, 120, 150, 180, 210, 240, 0]
    property int stepIndex: Math.max(0, steps.indexOf(Study.prefs.duration))
    property int rhythm: Study.prefs.rhythm
    property bool hideTime: Study.prefs.hideTime
    property var known: Study.prefs.allowed.slice()
    property var allowed: Study.prefs.allowed.slice()
    property bool adding
    readonly property int duration: steps[stepIndex]

    signal start(var config)

    // Back to the remembered choices each time the panel opens.
    function reset(): void {
        stepIndex = Math.max(0, steps.indexOf(Study.prefs.duration));
        rhythm = Study.prefs.rhythm;
        hideTime = Study.prefs.hideTime;
        known = Study.prefs.allowed.slice();
        allowed = Study.prefs.allowed.slice();
        adding = false;
        search.text = "";
    }

    function formatDuration(m: int): string {
        if (!m)
            return "Libre";
        return m >= 60 ? (m % 60 ? `${Math.floor(m / 60)} h ${m % 60}` : `${m / 60} h`) : `${m} min`;
    }

    function appName(cls: string): string {
        return Study.appName(cls);
    }

    function toggleApp(cls: string): void {
        allowed = allowed.includes(cls) ? allowed.filter(c => c !== cls) : allowed.concat([cls]);
    }

    function addApp(cls: string): void {
        if (!known.includes(cls))
            known = known.concat([cls]);
        if (!allowed.includes(cls))
            allowed = allowed.concat([cls]);
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
        width: root.width - root.leftPadding - root.rightPadding
        implicitHeight: Tokens.padding.extraLarge
        from: 0
        to: root.steps.length - 1
        stepSize: 1
        snapMode: Slider.SnapAlways
        value: root.stepIndex
        onMoved: root.stepIndex = Math.round(value)
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
            x: parent.width * 3 / 8 - width / 2
            text: "2 h"
        }
        Tick {
            anchors.right: parent.right
            text: "Libre"
        }
    }

    Label {
        text: "Ritmo"
    }

    RhythmGroup {
        width: root.width - root.leftPadding - root.rightPadding
        current: root.rhythm
        onPicked: value => root.rhythm = value
    }

    Label {
        text: "Permitido"
    }

    Flow {
        width: root.width - root.leftPadding - root.rightPadding
        spacing: Tokens.spacing.small

        Repeater {
            model: root.known

            FilterChip {
                required property string modelData

                text: root.appName(modelData)
                selected: root.allowed.includes(modelData)
                onClicked: root.toggleApp(modelData)
            }
        }

        FilterChip {
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
        }

        ListView {
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
        text: "Empezar"
        enabled: root.allowed.length > 0
        onClicked: root.start({duration: root.duration, rhythm: root.rhythm, allowed: root.allowed, hideTime: root.hideTime})
    }
}
