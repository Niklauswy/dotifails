// Añadir música: one search bar for songs and links. A song search lists YouTube results (a click plays it right
// away, the check keeps it for download; Ctrl+Enter downloads the selection). A Spotify or YouTube list opens a
// choice card: every song with its check, «Todas» / «Solo las que no tengo» / «Ninguna», «Escuchar» and
// «Descargar N». Downloads show as one card per batch with its progress and cancel; songs that could not be
// downloaded fold into one line with «Reintentar» and, per song, «Elegir otra versión». Importing files or a
// folder (Ctrl+O) and the music folder sit quietly at the end.
import QtQuick
import WysunM3
import "../parts"

FocusScope {
    id: page

    property var app
    property string route
    readonly property string kind: "downloads"
    readonly property real scrollOffset: flick.contentY
    readonly property var preview: addMusic.preview
    readonly property bool previewing: preview.visible === true
    readonly property bool choosing: addMusic.choosing !== ""
    property bool showFailed

    Flickable {
        id: flick

        anchors.fill: parent
        contentHeight: column.implicitHeight + 2 * MusicMetrics.pagePadding
        boundsBehavior: Flickable.StopAtBounds
        clip: true

        Column {
            id: column

            x: MusicMetrics.pagePadding
            y: Theme.padding.large ?? 0
            width: flick.width - 2 * x
            spacing: Theme.spacing.extraLarge ?? 0

            // --------------------------------------------------------- search
            Column {
                width: parent.width
                spacing: Theme.spacing.medium ?? 0

                Column {
                    Label {
                        role: "headline.medium"
                        text: "Añadir música"
                    }
                    Label {
                        role: "body.medium"
                        text: "Busca una canción o pega un enlace de Spotify o YouTube. Escucha antes y guarda solo lo que quieras."
                        color: Theme.m3onSurfaceVariant
                    }
                }

                Row {
                    width: parent.width
                    spacing: Theme.spacing.small ?? 0

                    TextField {
                        id: query

                        objectName: "addQuery"
                        width: parent.width - searchButton.width - parent.spacing
                        label: "Canción y artista, o enlace de Spotify o YouTube"
                        leadingIcon: "travel_explore"
                        focus: true
                        onAccepted: addMusic.search(text)
                    }
                    Button {
                        id: searchButton

                        anchors.verticalCenter: query.verticalCenter
                        text: "Buscar"
                        icon: "search"
                        disabled: addMusic.busy || query.text.trim() === ""
                        onClicked: addMusic.search(query.text)
                    }
                }

                Row {
                    spacing: Theme.spacing.small ?? 0

                    CircularProgress {
                        anchors.verticalCenter: parent.verticalCenter
                        visible: addMusic.busy
                        size: Metrics.iconSize
                        indeterminate: true
                    }
                    Label {
                        objectName: "addStatus"
                        anchors.verticalCenter: parent.verticalCenter
                        width: column.width - (addMusic.busy ? Metrics.iconSize + parent.spacing : 0)
                        role: "body.medium"
                        text: addMusic.status
                        color: Theme.m3onSurfaceVariant
                        wrapMode: Text.Wrap
                    }
                }
            }

            // ------------------------------------------------- list to choose
            Surface {
                id: previewCard

                objectName: "previewCard"
                visible: page.previewing
                width: parent.width
                height: previewColumn.implicitHeight + 2 * (Theme.padding.large ?? 0)
                radius: Theme.rounding.extraLarge ?? 0
                container: Theme.m3surfaceContainer
                color: container

                Column {
                    id: previewColumn

                    x: Theme.padding.large ?? 0
                    y: Theme.padding.large ?? 0
                    width: parent.width - 2 * x
                    spacing: Theme.spacing.medium ?? 0

                    Row {
                        width: parent.width
                        spacing: Theme.spacing.large ?? 0

                        Cover {
                            width: MusicMetrics.cardCover * 0.75
                            height: width
                            source: {
                                covers.revision;
                                const own = page.preview.collection ? covers.collection(page.preview.collection) : [];
                                return own.length ? own[0] : (page.preview.cover ?? "");
                            }
                            placeholderIcon: "queue_music"
                            fill: Theme.m3secondaryContainer
                            placeholderColor: Theme.m3onSecondaryContainer
                        }
                        Column {
                            anchors.verticalCenter: parent.verticalCenter
                            width: parent.width - MusicMetrics.cardCover * 0.75 - closePreview.width - 2 * parent.spacing
                            spacing: Theme.spacing.small ?? 0

                            Label {
                                role: "label.large"
                                text: ("Lista de " + (page.preview.kind ?? "")).toUpperCase()
                                color: Theme.m3onSurfaceVariant
                            }
                            Label {
                                objectName: "previewTitle"
                                width: parent.width
                                role: "headline.small"
                                text: page.preview.title ?? ""
                                elide: Text.ElideRight
                            }
                            Label {
                                role: "body.medium"
                                text: page.preview.subtitle ?? ""
                                color: Theme.m3onSurfaceVariant
                            }
                            Row {
                                spacing: Theme.spacing.small ?? 0

                                Button {
                                    objectName: "downloadPreview"
                                    text: page.preview.action ?? ""
                                    icon: "download"
                                    disabled: (page.preview.chosen ?? 0) === 0
                                    onClicked: addMusic.downloadPreview()
                                }
                                Button {
                                    type: "tonal"
                                    text: "Escuchar"
                                    icon: "play_arrow"
                                    onClicked: addMusic.playPreview()
                                }
                            }
                        }
                        IconButton {
                            id: closePreview

                            icon: "close"
                            onClicked: addMusic.closePreview()

                            Tooltip {
                                text: "Cerrar sin descargar"
                            }
                        }
                    }

                    Flow {
                        width: parent.width
                        spacing: Theme.spacing.small ?? 0

                        Chip {
                            objectName: "selectAll"
                            kind: "filter"
                            text: "Todas"
                            selected: (page.preview.chosen ?? 0) === (page.preview.total ?? 0) - (page.preview.owned ?? 0) && (page.preview.chosen ?? 0) > 0
                            onClicked: addMusic.selectPreview("all")
                        }
                        Chip {
                            kind: "suggestion"
                            visible: (page.preview.owned ?? 0) > 0
                            text: (page.preview.owned ?? 0) + " ya están en tu biblioteca"
                            enabled: false
                        }
                        Chip {
                            objectName: "selectNone"
                            kind: "filter"
                            text: "Ninguna"
                            selected: (page.preview.chosen ?? 0) === 0
                            onClicked: addMusic.selectPreview("none")
                        }
                    }

                    Column {
                        objectName: "previewList"
                        width: parent.width

                        Repeater {
                            model: addMusic.previewModel

                            ListItem {
                                width: parent.width
                                headline: model.title
                                supporting: model.detail
                                selected: model.selected
                                disabled: model.owned
                                leading: Component {
                                    Icon {
                                        name: model.owned ? "download_done" : model.selected ? "check_box" : "check_box_outline_blank"
                                        filled: model.selected
                                        color: model.owned ? Theme.m3onSurfaceVariant : Theme.m3primary
                                    }
                                }
                                trailing: Component {
                                    IconButton {
                                        icon: "play_arrow"
                                        onClicked: addMusic.playPreviewRow(index)

                                        Tooltip {
                                            text: "Escuchar sin descargar"
                                        }
                                    }
                                }
                                onClicked: addMusic.togglePreview(index)
                            }
                        }
                    }
                }
            }

            // -------------------------------------------------- song results
            Column {
                objectName: "resultsSection"
                visible: results.count > 0 && !page.previewing
                width: parent.width
                spacing: Theme.spacing.small ?? 0

                Item {
                    width: parent.width
                    height: Metrics.buttonHeight

                    Label {
                        anchors.verticalCenter: parent.verticalCenter
                        role: "title.large"
                        text: page.choosing ? "Elige la versión de «" + addMusic.choosing + "»" : "En YouTube"
                    }
                    Row {
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: Theme.spacing.small ?? 0

                        Button {
                            visible: page.choosing
                            type: "text"
                            text: "Cancelar"
                            onClicked: addMusic.cancelChoice()
                        }
                        Button {
                            objectName: "downloadSelected"
                            visible: !page.choosing
                            text: "Descargar selección"
                            icon: "download"
                            onClicked: addMusic.downloadSelected()

                            Tooltip {
                                text: "Ctrl+Enter en la lista"
                            }
                        }
                    }
                }

                ListView {
                    id: results

                    objectName: "addResults"
                    width: parent.width
                    height: count * Metrics.listItemTwoLine
                    interactive: false
                    model: addMusic.resultsModel
                    activeFocusOnTab: true
                    keyNavigationEnabled: true
                    Keys.onSpacePressed: addMusic.toggleResult(currentIndex)
                    Keys.onReturnPressed: event => {
                        if (event.modifiers & Qt.ControlModifier)
                            addMusic.downloadSelected();
                        else if (page.choosing)
                            addMusic.useVersion(currentIndex);
                        else
                            addMusic.playResult(currentIndex);
                    }
                    Keys.onEnterPressed: event => {
                        if (event.modifiers & Qt.ControlModifier)
                            addMusic.downloadSelected();
                    }
                    delegate: ListItem {
                        width: ListView.view.width
                        headline: model.title
                        supporting: model.detail
                        selected: model.selected
                        highlighted: ListView.isCurrentItem && results.activeFocus
                        leading: Component {
                            IconButton {
                                visible: !page.choosing
                                icon: model.selected ? "check_box" : "check_box_outline_blank"
                                onClicked: addMusic.toggleResult(index)

                                Tooltip {
                                    text: model.selected ? "No descargar" : "Marcar para descargar"
                                }
                            }
                        }
                        trailing: Component {
                            Button {
                                type: page.choosing ? "tonal" : "text"
                                text: page.choosing ? "Usar esta" : "Escuchar"
                                icon: page.choosing ? "check" : "play_arrow"
                                onClicked: page.choosing ? addMusic.useVersion(index) : addMusic.playResult(index)
                            }
                        }
                        onClicked: {
                            results.currentIndex = index;
                            if (page.choosing)
                                addMusic.useVersion(index);
                            else
                                addMusic.playResult(index);
                        }
                    }
                }
            }

            // ------------------------------------------------------ downloads
            Column {
                objectName: "downloads"
                width: parent.width
                spacing: Theme.spacing.medium ?? 0

                Item {
                    width: parent.width
                    height: Metrics.buttonHeight

                    Column {
                        anchors.verticalCenter: parent.verticalCenter

                        Label {
                            role: "title.large"
                            text: "Descargas"
                        }
                        Label {
                            objectName: "downloadSummary"
                            role: "body.medium"
                            text: addMusic.summary
                            color: Theme.m3onSurfaceVariant
                        }
                    }
                    Button {
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        visible: addMusic.counts.canPause === true || addMusic.counts.canResume === true
                        type: "tonal"
                        text: addMusic.counts.paused ? "Continuar" : "Pausar"
                        icon: addMusic.counts.paused ? "play_arrow" : "pause"
                        onClicked: addMusic.counts.paused ? addMusic.resume() : addMusic.pause()
                    }
                }

                Repeater {
                    objectName: "batches"
                    model: addMusic.batchesModel

                    Surface {
                        width: column.width
                        height: batchColumn.implicitHeight + 2 * (Theme.padding.medium ?? 0)
                        radius: Theme.rounding.large ?? 0
                        container: Theme.m3surfaceContainerHigh
                        color: container

                        Column {
                            id: batchColumn

                            x: Theme.padding.large ?? 0
                            y: Theme.padding.medium ?? 0
                            width: parent.width - 2 * x
                            spacing: Theme.spacing.small ?? 0

                            Item {
                                width: parent.width
                                height: Math.max(batchText.implicitHeight, Metrics.iconButtonSize ?? 0)

                                Column {
                                    id: batchText

                                    anchors.verticalCenter: parent.verticalCenter
                                    width: parent.width - cancelBatch.width

                                    Label {
                                        width: parent.width
                                        role: "title.medium"
                                        text: model.title
                                        elide: Text.ElideRight
                                    }
                                    Label {
                                        width: parent.width
                                        role: "body.medium"
                                        text: model.detail
                                        color: Theme.m3onSurfaceVariant
                                        elide: Text.ElideRight
                                    }
                                }
                                IconButton {
                                    id: cancelBatch

                                    anchors.right: parent.right
                                    anchors.verticalCenter: parent.verticalCenter
                                    icon: "close"
                                    onClicked: addMusic.cancelBatch(model.id)

                                    Tooltip {
                                        text: "Cancelar lo que falta de esta descarga"
                                    }
                                }
                            }
                            LinearProgress {
                                width: parent.width
                                value: model.fraction
                            }
                        }
                    }
                }

                // Songs that could not be downloaded: one quiet line, expandable.
                Surface {
                    objectName: "failedCard"
                    visible: (addMusic.counts.failed ?? 0) > 0
                    width: parent.width
                    height: failedColumn.implicitHeight + 2 * (Theme.padding.small ?? 0)
                    radius: Theme.rounding.large ?? 0
                    container: Theme.m3surfaceContainerLow
                    color: container

                    Column {
                        id: failedColumn

                        x: Theme.padding.small ?? 0
                        y: Theme.padding.small ?? 0
                        width: parent.width - 2 * x

                        ListItem {
                            width: parent.width
                            headline: addMusic.counts.failedText ?? ""
                            supporting: page.showFailed ? "Puedes elegir otra versión de cada una" : "Toca para ver cuáles"
                            leadingIcon: "error"
                            trailing: Component {
                                Button {
                                    objectName: "retryFailed"
                                    type: "tonal"
                                    text: "Reintentar"
                                    icon: "refresh"
                                    onClicked: addMusic.retry()
                                }
                            }
                            onClicked: page.showFailed = !page.showFailed
                        }

                        Repeater {
                            model: page.showFailed ? addMusic.failedModel : null

                            ListItem {
                                width: failedColumn.width
                                headline: model.title
                                supporting: model.detail
                                trailing: Component {
                                    Row {
                                        spacing: Theme.spacing.extraSmall ?? 0

                                        Button {
                                            type: "text"
                                            text: "Elegir otra versión"
                                            onClicked: {
                                                addMusic.chooseVersion(model.key);
                                                flick.contentY = 0;
                                            }
                                        }
                                        IconButton {
                                            icon: "delete"
                                            onClicked: addMusic.forget(model.key)

                                            Tooltip {
                                                text: "Quitar de la cola"
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                Row {
                    visible: addMusic.batchesModel.count === 0 && (addMusic.counts.failed ?? 0) === 0
                    spacing: Theme.spacing.small ?? 0

                    Icon {
                        anchors.verticalCenter: parent.verticalCenter
                        name: "task_alt"
                        color: Theme.m3onSurfaceVariant
                    }
                    Label {
                        objectName: "allDone"
                        anchors.verticalCenter: parent.verticalCenter
                        role: "body.medium"
                        text: (addMusic.counts.ready ?? 0) + " canciones en tu equipo, todo al día."
                        color: Theme.m3onSurfaceVariant
                    }
                }
            }

            // ------------------------------------------------ from this computer
            Column {
                width: parent.width
                spacing: Theme.spacing.small ?? 0

                Label {
                    role: "title.medium"
                    text: "Desde este equipo"
                    color: Theme.m3onSurfaceVariant
                }
                Flow {
                    width: parent.width
                    spacing: Theme.spacing.small ?? 0

                    Button {
                        objectName: "importFiles"
                        type: "text"
                        text: "Importar archivos"
                        icon: "audio_file"
                        onClicked: addMusic.importFiles()

                        Tooltip {
                            text: "Ctrl+O"
                        }
                    }
                    Button {
                        type: "text"
                        text: "Importar carpeta"
                        icon: "create_new_folder"
                        onClicked: addMusic.importFolder()
                    }
                    Button {
                        type: "text"
                        text: "Abrir carpeta de música"
                        icon: "folder_open"
                        onClicked: addMusic.openFolder()
                    }
                }
            }
        }
    }
}
