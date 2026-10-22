pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Hyprland
import qs.components.containers
import Wysun.Config
import qs.components
import qs.components.controls
import qs.services

StyledWindow {
    id: win
    name: "colors"
    screen: Quickshell.screens.find(s => s.name === Hypr.focusedMonitor?.name) ?? Quickshell.screens[0]
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: visible ? WlrKeyboardFocus.OnDemand : WlrKeyboardFocus.None
    visible: true
    property bool dismissOnFocusLoss: true
    readonly property bool compact: height < 680
    implicitWidth: Math.min(920, (screen?.width ?? 1280) * 0.9)
    implicitHeight: Math.min(720, (screen?.height ?? 900) * 0.9)
    color: "transparent"
    property color inputColor: Colours.palette.m3primary
    property real hue: 0.60
    property real saturation: 0.50
    property real brightness: 0.92
    readonly property color selected: Qt.hsva(hue, saturation, brightness, 1)
    readonly property string hex: selected.toString().toUpperCase()
    readonly property string rgb: `rgb(${Math.round(selected.r * 255)}, ${Math.round(selected.g * 255)}, ${Math.round(selected.b * 255)})`
    readonly property string hsl: `hsl(${Math.round(Math.max(0, selected.hslHue) * 360)}, ${Math.round(selected.hslSaturation * 100)}%, ${Math.round(selected.hslLightness * 100)}%)`
    property var paletteData: ({recent: [], favorites: []})
    // Colour handed over by the direct eyedropper (Super+Shift+C): already copied.
    property string pickedColor: ''
    function adopt(value: string): void {
        choose(value); send('save', hex); message = hex + ' copiado';
    }
    property bool favoritesOnly: false
    readonly property bool favorite: (paletteData.favorites || []).includes(hex)
    readonly property var swatches: favoritesOnly ? (paletteData.favorites || []) : (paletteData.recent || [])
    readonly property string hints: "C capturar · H R L copiar · F favorito · 1–9 elegir · E editar · Esc cerrar"
    property string message: hints
    property bool invalid: false
    property bool ready: false
    property bool sampling: false
    property int parseRevision: 0
    property var pending: []
    readonly property real luminance: {
        function linear(v) { return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }
        return 0.2126 * linear(selected.r) + 0.7152 * linear(selected.g) + 0.0722 * linear(selected.b);
    }
    readonly property bool darkInk: luminance > 0.179
    readonly property color ink: darkInk ? "black" : "white" // theme-exception: legible text on user-selected colours.
    readonly property real contrast: darkInk ? (luminance + 0.05) / 0.05 : 1.05 / (luminance + 0.05)

    function send(action: string, value: string): void {
        const request = {action: action, color: value, revision: parseRevision};
        if (ready) service.write(JSON.stringify(request) + '\n');
        else pending = pending.concat([request]);
    }
    function choose(value, preserveText = false): void {
        inputColor = value;
        const c = inputColor;
        parseRevision++;
        if (c.hsvHue >= 0) hue = c.hsvHue;
        saturation = c.hsvSaturation; brightness = c.hsvValue;
        invalid = false; if (!preserveText) entry.text = hex;
    }
    function edit(): void { parseRevision++; send('parse', entry.text); }
    function copy(format: string): void {
        if (invalid) return;
        Quickshell.clipboardText = format === 'RGB' ? rgb : format === 'HSL' ? hsl : hex;
        send('save', hex); message = format + ' copiado';
    }
    function sample(): void {
        if (sampling) return;
        sampling = true; visible = false; sampleDelay.start();
    }
    function restore(): void { sampling = false; visible = true; background.forceActiveFocus(); }
    function pickSwatch(index: int): void { if (index < swatches.length) { choose(swatches[index]); message = swatches[index] + ' seleccionado'; } }
    function paletteCopy(): void {
        Quickshell.clipboardText = ':root {\n' + (paletteData.favorites || []).map((c, i) => `  --color-${i + 1}: ${c};`).join('\n') + '\n}';
        message = 'Paleta CSS copiada';
    }
    onHexChanged: { if (!entry.activeFocus) entry.text = hex; }
    Component.onCompleted: { entry.text = hex; service.running = true; background.forceActiveFocus(); }
    Process {
        id: service
        command: ['/usr/bin/python3', Quickshell.shellPath('modules/colors/backend.py')]
        stdinEnabled: true
        onStarted: {
            win.ready = true; write(JSON.stringify({action:'read'}) + '\n');
            for (const request of win.pending) write(JSON.stringify(request) + '\n');
            win.pending = [];
        }
        stdout: SplitParser {
            onRead: line => {
                try {
                    const result = JSON.parse(line);
                    if (result.data) win.paletteData = result.data;
                    if (result.action === 'read') {
                        if (win.pickedColor) win.adopt(win.pickedColor);
                        else win.choose(result.data?.recent?.[0] || Colours.palette.m3primary);
                    }
                    if (result.action === 'parse' && result.revision !== win.parseRevision) return;
                    if (result.error) { win.invalid = result.action === 'parse'; win.message = result.error; }
                    else if (result.action === 'parse' && result.color) { win.choose(result.color, entry.activeFocus); win.message = 'Color actualizado'; }
                } catch (e) { win.message = 'No se pudo leer la paleta'; }
            }
        }
        onExited: { win.ready = false; win.message = 'Almacenamiento no disponible. Cierra y vuelve a abrir Colores.'; }
    }
    Timer { id: sampleDelay; interval: 200; onTriggered: picker.running = true }
    // Feedback lines ("HEX copiado"…) fade back to the shortcut hints.
    onMessageChanged: if (message !== hints && !invalid) hintTimer.restart()
    Timer { id: hintTimer; interval: 3000; onTriggered: if (!win.invalid) win.message = win.hints }
    Process {
        id: picker
        command: ['hyprpicker', '--format=hex', '--no-fancy', '--render-inactive']
        property string output: ''
        onStarted: output = ''
        onRunningChanged: if (!running && win.sampling) Qt.callLater(() => {
            if (win.sampling && !picker.running) { win.restore(); win.message = 'No se pudo abrir el selector de pantalla'; }
        })
        stdout: StdioCollector { onStreamFinished: picker.output = text }
        onExited: code => {
            win.restore();
            try {
                const found = output.match(/#[0-9a-fA-F]{6}/g);
                if (code !== 0 || !found) throw new Error();
                win.choose(Qt.color(found[found.length - 1].toUpperCase()));
                win.send('save', win.hex); win.message = 'Color capturado';
            } catch (e) { win.message = 'Captura cancelada o selector no disponible'; }
        }
    }
    IpcHandler {
        target: 'colors'
        function state(): string { return JSON.stringify({hex: win.hex, rgb: win.rgb, hsl: win.hsl, favorite: win.favorite, invalid: win.invalid, ready: win.ready, sampling: win.sampling, message: win.message}); }
        function set(value: string): void { entry.text = value; win.edit(); }
        function copy(format: string): void { win.copy(format); }
        function favorite(): void { if (!win.invalid) win.send('favorite', win.hex); }
        function sample(): void { win.sample(); }
    }
    // Single keys act while the value field is not being typed in (E edits it).
    Shortcut { sequence: 'Escape'; onActivated: entry.activeFocus ? background.forceActiveFocus() : win.destroy() }
    Shortcut { sequence: 'Ctrl+P'; onActivated: win.sample() }
    Shortcut { sequences: ['C']; enabled: !entry.activeFocus; onActivated: win.sample() }
    Shortcut { sequences: ['H', 'Return', 'Enter', 'Ctrl+C']; enabled: !entry.activeFocus; onActivated: win.copy('HEX') }
    Shortcut { sequence: 'R'; enabled: !entry.activeFocus; onActivated: win.copy('RGB') }
    Shortcut { sequence: 'L'; enabled: !entry.activeFocus; onActivated: win.copy('HSL') }
    Shortcut { sequence: 'F'; enabled: !entry.activeFocus && !win.invalid && win.ready; onActivated: win.send('favorite', win.hex) }
    Shortcut { sequence: 'P'; enabled: !entry.activeFocus && (win.paletteData.favorites || []).length > 0; onActivated: win.paletteCopy() }
    Shortcut { sequence: 'T'; enabled: !entry.activeFocus; onActivated: win.favoritesOnly = !win.favoritesOnly }
    Shortcut { sequences: ['E', 'Ctrl+L']; enabled: !entry.activeFocus; onActivated: { entry.forceActiveFocus(); entry.selectAll(); } }
    Shortcut { sequence: 'Ctrl+V'; enabled: !entry.activeFocus; onActivated: { entry.text = Quickshell.clipboardText; win.edit(); } }
    Repeater {
        model: 9
        Item {
            required property int index
            Shortcut { sequence: String(index + 1); enabled: !entry.activeFocus; onActivated: win.pickSwatch(index) }
        }
    }

    component Action: IconTextButton {
        activeFocusOnTab: !disabled
        Accessible.role: Accessible.Button
        Accessible.name: text
        Keys.onReturnPressed: if (!disabled) clicked()
        Keys.onSpacePressed: if (!disabled) clicked()
        border.width: activeFocus ? Tokens.spacing.extraSmall / 2 : 0
        border.color: Colours.palette.m3primary
    }
    component IconAction: IconButton {
        activeFocusOnTab: !disabled
        Accessible.role: Accessible.Button
        Keys.onReturnPressed: if (!disabled) clicked()
        Keys.onSpacePressed: if (!disabled) clicked()
        border.width: activeFocus ? Tokens.spacing.extraSmall / 2 : 0
        border.color: Colours.palette.m3primary
    }
    component Chip: TextButton {
        activeFocusOnTab: !disabled
        Accessible.role: Accessible.Button
        Accessible.name: text
        Keys.onReturnPressed: if (!disabled) clicked()
        Keys.onSpacePressed: if (!disabled) clicked()
        border.width: activeFocus ? Tokens.spacing.extraSmall / 2 : 0
        border.color: Colours.palette.m3primary
    }
    HyprlandFocusGrab {
        active: win.dismissOnFocusLoss && win.visible && !win.sampling
        windows: [win]
        onCleared: if (!win.sampling) win.destroy()
    }
    function snapshot(path: string): void { background.grabToImage(result => result.saveToFile(path)); }
    Rectangle {
        id: background
        anchors.fill: parent
        radius: Tokens.rounding.extraExtraLarge
        color: Colours.palette.m3surface
        focus: true
        activeFocusOnTab: false

    ColumnLayout {
        id: layout
        anchors.fill: parent
        anchors.margins: win.compact ? Tokens.padding.large : Tokens.padding.largeIncreased
        spacing: win.compact ? Tokens.spacing.small : Tokens.spacing.large
        RowLayout {
            Layout.fillWidth: true
            spacing: Tokens.spacing.medium
            Rectangle {
                implicitWidth: win.compact ? Tokens.spacing.extraExtraLarge : Tokens.font.icon.large.pixelSize + Tokens.padding.largeIncreased * 2
                implicitHeight: implicitWidth
                radius: Tokens.rounding.extraLarge
                color: Colours.palette.m3primaryContainer
                MaterialIcon { anchors.centerIn: parent; text: 'palette'; color: Colours.palette.m3onPrimaryContainer; fontStyle: Tokens.font.icon.large }
            }
            ColumnLayout {
                spacing: 0
                StyledText { text: 'Colores'; font: win.compact ? Tokens.font.headline.small : Tokens.font.headline.medium }
                StyledText { text: 'Explora, captura y guarda'; color: Colours.palette.m3onSurfaceVariant }
            }
            Item { Layout.fillWidth: true }
            Action { icon: 'colorize'; text: 'Capturar · C'; type: IconTextButton.Filled; isRound: true; onClicked: win.sample(); Accessible.name: 'Capturar color de pantalla, tecla C' }
            IconAction { icon: 'close'; type: IconButton.Text; onClicked: win.destroy(); Accessible.name: 'Cerrar' }
        }
        RowLayout {
            Layout.fillWidth: true; Layout.fillHeight: true
            spacing: Tokens.spacing.large
            ColumnLayout {
                Layout.fillWidth: true; Layout.fillHeight: true
                spacing: win.compact ? Tokens.spacing.medium : Tokens.spacing.large
                ColorPlane {
                    Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumHeight: Tokens.spacing.extraExtraLarge * 3
                    hue: win.hue; saturation: win.saturation; brightness: win.brightness
                    onSelected: (s, v) => { win.saturation = s; win.brightness = v; win.invalid = false; entry.text = win.hex; }
                }
                ColumnLayout {
                    Layout.fillWidth: true; spacing: win.compact ? Tokens.spacing.small : Tokens.spacing.medium
                    Repeater {
                        model: ['Matiz', 'Saturación', 'Brillo']
                        delegate: ColumnLayout {
                            id: adjustment
                            required property int index
                            required property string modelData
                            Layout.fillWidth: true; spacing: win.compact ? Tokens.spacing.extraSmall : Tokens.spacing.small
                            RowLayout {
                                StyledText { text: adjustment.modelData; color: Colours.palette.m3onSurfaceVariant }
                                Item { Layout.fillWidth: true }
                                StyledText { text: Math.round((adjustment.index === 0 ? win.hue * 360 : adjustment.index === 1 ? win.saturation * 100 : win.brightness * 100)) + (adjustment.index === 0 ? '°' : '%'); font: Tokens.font.label.medium }
                            }
                            StyledSlider {
                                activeFocusOnTab: true
                                stepSize: 0.01
                                Keys.onLeftPressed: interaction(Math.max(0, value - stepSize))
                                Keys.onRightPressed: interaction(Math.min(1, value + stepSize))
                                Layout.fillWidth: true; Layout.preferredHeight: Tokens.spacing.large
                                from: 0; to: 1
                                value: adjustment.index === 0 ? win.hue : adjustment.index === 1 ? win.saturation : win.brightness
                                Accessible.name: adjustment.modelData
                                onInteraction: v => {
                                    if (adjustment.index === 0) win.hue = Math.min(v, 0.99999);
                                    else if (adjustment.index === 1) win.saturation = v;
                                    else win.brightness = v;
                                    win.invalid = false; entry.text = win.hex;
                                }
                            }
                        }
                    }
                }
            }
            Rectangle {
                Layout.preferredWidth: Math.max(260, win.width * 0.34)
                Layout.fillHeight: true
                color: Colours.palette.m3surfaceContainer
                radius: Tokens.rounding.extraLarge
                ColumnLayout {
                    anchors.fill: parent; anchors.margins: Tokens.padding.large
                    spacing: win.compact ? Tokens.spacing.small : Tokens.spacing.medium
                    Rectangle {
                        Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumHeight: Tokens.spacing.extraExtraLarge * 2
                        color: win.selected; radius: Tokens.rounding.large
                        ColumnLayout {
                            anchors.fill: parent; anchors.margins: Tokens.padding.large
                            StyledText { visible: !win.compact; text: 'VISTA PREVIA'; color: win.ink; font: Tokens.font.label.small; opacity: 0.7 }
                            Item { Layout.fillHeight: true }
                            StyledText { text: 'Aa'; color: win.ink; font: win.compact ? Tokens.font.title.large : Tokens.font.headline.large }
                            StyledText { text: win.contrast.toFixed(1) + ':1 · Texto ' + (win.darkInk ? 'oscuro' : 'claro'); color: win.ink; font: Tokens.font.label.small }
                        }
                    }
                    StyledTextField {
                        id: entry
                        Layout.fillWidth: true
                        placeholderText: ''
                        verticalPadding: win.compact ? Tokens.padding.small : Tokens.padding.large
                        leadingIcon: 'tag'
                        radius: Tokens.rounding.large
                        isError: win.invalid
                        errorText: 'Color no válido'
                        font: Tokens.font.title.medium
                        onTextEdited: win.edit()
                        Accessible.name: 'Valor del color en HEX, RGB o HSL'
                    }
                    Repeater {
                        model: ['RGB', 'HSL']
                        delegate: RowLayout {
                            id: formatRow
                            required property string modelData
                            Layout.fillWidth: true
                            ColumnLayout {
                                Layout.fillWidth: true; spacing: Tokens.spacing.extraSmall
                                StyledText { text: formatRow.modelData; font: Tokens.font.label.small; color: Colours.palette.m3onSurfaceVariant }
                                StyledText { Layout.fillWidth: true; text: formatRow.modelData === 'RGB' ? win.rgb : win.hsl; font: Tokens.font.body.small; elide: Text.ElideRight }
                            }
                            StyledText { text: formatRow.modelData === 'RGB' ? 'R' : 'L'; font: Tokens.font.label.small; color: Colours.palette.m3onSurfaceVariant }
                            IconAction { icon: 'content_copy'; type: IconButton.Text; disabled: win.invalid; onClicked: win.copy(formatRow.modelData); Accessible.name: 'Copiar ' + formatRow.modelData + ', tecla ' + (formatRow.modelData === 'RGB' ? 'R' : 'L') }
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true; spacing: Tokens.spacing.small
                        Action { Layout.fillWidth: true; text: 'Copiar HEX · H'; icon: 'content_copy'; isRound: true; disabled: win.invalid; onClicked: win.copy('HEX') }
                        IconAction { icon: win.favorite ? 'bookmark_added' : 'bookmark_add'; type: IconButton.Tonal; isRound: true; disabled: win.invalid || !win.ready; onClicked: win.send('favorite', win.hex); Accessible.name: win.favorite ? 'Quitar favorito' : 'Guardar favorito' }
                    }
                }
            }
        }
        ColumnLayout {
            Layout.fillWidth: true; spacing: Tokens.spacing.small
            RowLayout {
                spacing: Tokens.spacing.small
                Chip { text: 'Recientes'; type: TextButton.Text; isToggle: true; checked: !win.favoritesOnly; onClicked: win.favoritesOnly = false }
                Chip { text: 'Favoritos · ' + (win.paletteData.favorites || []).length; type: TextButton.Text; isToggle: true; checked: win.favoritesOnly; onClicked: win.favoritesOnly = true }
                Item { Layout.fillWidth: true }
                Chip { text: 'Copiar paleta CSS · P'; type: TextButton.Text; disabled: !(win.paletteData.favorites || []).length; onClicked: win.paletteCopy() }
            }
            Item {
                Layout.fillWidth: true; Layout.preferredHeight: win.compact ? Tokens.spacing.extraExtraLarge : Tokens.spacing.extraExtraLarge + Tokens.spacing.large
                StyledText {
                    anchors.centerIn: parent; visible: !win.swatches.length
                    text: win.favoritesOnly ? 'Guarda un color con el marcador para crear tu paleta.' : 'Los colores capturados y copiados aparecerán aquí.'
                    color: Colours.palette.m3onSurfaceVariant; font: Tokens.font.body.small
                }
                ListView {
                    anchors.fill: parent; orientation: ListView.Horizontal; clip: true
                    spacing: Tokens.spacing.small; model: win.swatches
                    delegate: Rectangle {
                        id: swatch
                        required property string modelData
                        required property int index
                        width: Tokens.spacing.extraExtraLarge * 2; height: ListView.view.height
                        radius: Tokens.rounding.large
                        color: modelData
                        border.width: win.hex === modelData ? Tokens.spacing.extraSmall : 0
                        border.color: Colours.palette.m3primary
                        Accessible.role: Accessible.Button; Accessible.name: modelData
                        activeFocusOnTab: true
                        Keys.onReturnPressed: win.choose(modelData)
                        Keys.onSpacePressed: win.choose(modelData)
                        Rectangle { anchors.fill: parent; radius: parent.radius; color: 'transparent'; border.color: Colours.palette.m3onSurface; border.width: parent.activeFocus ? Tokens.spacing.extraSmall / 2 : 0 }
                        StateLayer { radius: swatch.radius; onClicked: win.choose(swatch.modelData) }
                        Rectangle {
                            visible: swatch.index < 9
                            anchors.left: parent.left; anchors.top: parent.top; anchors.margins: Tokens.spacing.extraSmall
                            implicitWidth: number.implicitWidth + Tokens.padding.small * 2
                            implicitHeight: number.implicitHeight + Tokens.spacing.extraSmall
                            radius: height / 2
                            color: Colours.palette.m3surfaceContainerHighest
                            StyledText { id: number; anchors.centerIn: parent; text: swatch.index + 1; font: Tokens.font.label.small; color: Colours.palette.m3onSurface }
                        }
                    }
                }
            }
        }
        StyledText { Layout.fillWidth: true; text: win.message; color: win.invalid ? Colours.palette.m3error : Colours.palette.m3onSurfaceVariant; font: Tokens.font.label.small; elide: Text.ElideRight }
    }
    }
}
