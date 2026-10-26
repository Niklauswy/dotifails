// Añadir música: search YouTube (name or link) or paste a public Spotify playlist/album/song; pick results
// (click or Space toggles, Ctrl+Enter downloads the selection); import files or a folder through Wysun Files'
// selector (Ctrl+O); and the download queue with continue / pause / retry.
import QtQuick
import WysunM3
import "../parts"

FocusScope {
    id: page

    property var app
    property string route
    readonly property string kind: "downloads"
    readonly property real scrollOffset: flick.contentY

    function tone(name) {
        return ({accent: Theme.m3primary, error: Theme.m3error, warning: Theme.m3tertiary})[name] ?? Theme.m3onSurfaceVariant;
    }

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
            spacing: Theme.spacing.large ?? 0

            Label {
                role: "headline.medium"
                text: "Añadir música"
            }

            Row {
                width: parent.width
                spacing: Theme.spacing.small ?? 0

                TextField {
                    id: query

                    objectName: "addQuery"
                    width: parent.width - searchButton.width - parent.spacing
                    label: "Canción y artista, enlace de YouTube o de Spotify"
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

            ListView {
                id: results

                objectName: "addResults"
                visible: count > 0
                width: parent.width
                height: Math.min(count, 6) * Metrics.listItemTwoLine
                model: addMusic.resultsModel
                clip: true
                activeFocusOnTab: true
                keyNavigationEnabled: true
                Keys.onSpacePressed: addMusic.toggleResult(currentIndex)
                Keys.onReturnPressed: event => {
                    if (event.modifiers & Qt.ControlModifier)
                        addMusic.downloadSelected();
                    else
                        addMusic.toggleResult(currentIndex);
                }
                Keys.onEnterPressed: event => {
                    if (event.modifiers & Qt.ControlModifier)
                        addMusic.downloadSelected();
                }
                delegate: ListItem {
                    width: ListView.view.width
                    headline: model.title
                    supporting: model.detail
                    leadingIcon: model.selected ? "check_box" : "check_box_outline_blank"
                    selected: model.selected
                    highlighted: ListView.isCurrentItem && results.activeFocus
                    onClicked: {
                        results.currentIndex = index;
                        addMusic.toggleResult(index);
                    }
                    onDoubleClicked: {
                        if (!model.selected)
                            addMusic.toggleResult(index);
                        addMusic.downloadSelected();
                    }
                }
            }

            Button {
                objectName: "downloadSelected"
                visible: results.count > 0
                text: "Descargar selección"
                icon: "download"
                onClicked: addMusic.downloadSelected()

                Tooltip {
                    text: "Ctrl+Enter en la lista"
                }
            }

            Label {
                role: "title.large"
                text: "Desde este equipo"
            }
            Flow {
                width: parent.width
                spacing: Theme.spacing.small ?? 0

                Button {
                    objectName: "importFiles"
                    type: "tonal"
                    text: "Importar archivos"
                    icon: "audio_file"
                    onClicked: addMusic.importFiles()

                    Tooltip {
                        text: "Ctrl+O"
                    }
                }
                Button {
                    type: "tonal"
                    text: "Importar carpeta"
                    icon: "create_new_folder"
                    onClicked: addMusic.importFolder()
                }
                Button {
                    type: "outlined"
                    text: "Abrir carpeta de música"
                    icon: "folder_open"
                    onClicked: addMusic.openFolder()
                }
            }

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
            Row {
                spacing: Theme.spacing.small ?? 0

                Button {
                    type: "tonal"
                    text: "Continuar"
                    icon: "play_arrow"
                    disabled: !addMusic.counts.canResume
                    onClicked: addMusic.resume()
                }
                Button {
                    type: "tonal"
                    text: "Pausar cola"
                    icon: "pause"
                    disabled: !addMusic.counts.canPause
                    onClicked: addMusic.pause()
                }
                Button {
                    type: "outlined"
                    text: "Reintentar errores"
                    icon: "refresh"
                    disabled: !addMusic.counts.canRetry
                    onClicked: addMusic.retry()
                }
            }

            Column {
                objectName: "downloadQueue"
                width: parent.width

                Repeater {
                    model: addMusic.downloadsModel

                    ListItem {
                        width: parent.width
                        headline: model.title
                        supporting: model.detail
                        trailing: Component {
                            Chip {
                                kind: "suggestion"
                                text: model.statusText
                                enabled: false
                            }
                        }
                        leading: Component {
                            Icon {
                                name: ({error: "error", warning: "rule", accent: "downloading"})[model.tone] ?? "schedule"
                                color: page.tone(model.tone)
                            }
                        }
                    }
                }

                ListItem {
                    visible: addMusic.downloadsModel.count === 0
                    width: parent.width
                    headline: "Todo listo"
                    supporting: "Tu música está descargada y lista para escuchar."
                    leadingIcon: "task_alt"
                }
            }
        }
    }
}
