// Wysun Recorder: the recording settings, saved as they change. Python provides `bridge` (ThemeBridge) and
// `settings` (SettingsController); the controls are WysunM3's and every colour, size and corner comes from the theme.
import QtQuick
import WysunM3

Window {
    id: window

    objectName: "recorderWindow"
    title: "Wysun Recorder"
    width: Metrics.windowMedium * 1.3
    height: Metrics.windowExpanded
    minimumWidth: Metrics.windowMedium
    minimumHeight: Metrics.windowMedium * 0.7
    color: Theme.m3surface
    onActiveChanged: {
        if (active)
            settings.reload();
    }

    Item {
        anchors.fill: parent
        focus: true
        Keys.onEscapePressed: window.close()

        ThemeFeed {
            scheme: bridge.scheme
            tokens: bridge.tokens
            reducedMotion: bridge.reducedMotion
        }

        TopAppBar {
            id: bar

            width: parent.width
            title: "Ajustes de grabación"
            scrollOffset: scroll.contentY
        }

        Flickable {
            id: scroll

            objectName: "scroll"
            anchors.top: bar.bottom
            anchors.bottom: parent.bottom
            anchors.left: parent.left
            anchors.right: parent.right
            contentWidth: width
            contentHeight: column.height + 2 * (Theme.padding.large ?? 0)
            boundsBehavior: Flickable.StopAtBounds
            clip: true

            Column {
                id: column

                x: (scroll.width - width) / 2
                width: Math.min(scroll.width - 2 * (Theme.padding.large ?? 0), Metrics.windowExpanded)

                Section {
                    title: "Al grabar"

                    SettingRow {
                        title: "Micrófono"
                        hint: "Graba la entrada de audio predeterminada."
                        control: Component {
                            PrefSwitch {
                                key: "record_mic"
                            }
                        }
                    }
                    SettingRow {
                        title: "Dispositivo de micrófono"
                        hint: "Cuál grabar cuando el micrófono está activo. También se elige en la barra al grabar."
                        control: Component {
                            PrefDropdown {
                                key: "record_mic_device"
                                model: [
                                    {
                                        value: "",
                                        text: "Predeterminado del sistema"
                                    }
                                ].concat(settings.mics.map(mic => ({
                                            value: mic.id,
                                            text: mic.name
                                        })))
                            }
                        }
                    }
                    SettingRow {
                        title: "Audio del sistema"
                        hint: "Incluye lo que suena en el equipo."
                        control: Component {
                            PrefSwitch {
                                key: "record_system"
                            }
                        }
                    }
                    SettingRow {
                        title: "Cursor"
                        hint: "Muestra el puntero en el video."
                        control: Component {
                            PrefSwitch {
                                key: "record_cursor"
                            }
                        }
                    }
                    SettingRow {
                        title: "Cuenta atrás"
                        hint: "Tiempo antes de empezar a grabar. 0 empieza al instante."
                        control: Component {
                            Row {
                                spacing: Theme.spacing.small ?? 0

                                Slider {
                                    id: countdown

                                    objectName: "countdown"
                                    anchors.verticalCenter: parent.verticalCenter
                                    from: 0
                                    to: 30
                                    stepSize: 1
                                    live: false
                                    value: settings.values.countdown
                                    onMoved: value => {
                                        settings.setPref("countdown", Math.round(value));
                                        countdown.value = Qt.binding(() => settings.values.countdown);
                                    }
                                }
                                Label {
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: Metrics.iconButtonSize
                                    role: "label.large"
                                    text: Math.round(countdown.value) + " s"
                                }
                            }
                        }
                    }
                }

                Section {
                    title: "Cámara"

                    SettingRow {
                        title: "Grabar con cámara"
                        hint: "Se añade al video en una esquina, como una burbuja."
                        control: Component {
                            PrefSwitch {
                                key: "record_camera"
                                disabled: settings.cameras.length === 0
                            }
                        }
                    }
                    SettingRow {
                        title: "Cámara"
                        hint: "La que se usa al grabar."
                        control: Component {
                            PrefDropdown {
                                key: "camera_device"
                                disabled: settings.cameras.length === 0
                                fallback: settings.cameras.length > 0 ? settings.cameras[0].id : ""
                                placeholder: "No se encontró ninguna cámara"
                                model: settings.cameras.map(camera => ({
                                            value: camera.id,
                                            text: camera.name
                                        }))
                            }
                        }
                    }
                    SettingRow {
                        title: "Esquina"
                        hint: "Dónde queda la burbuja."
                        control: Component {
                            PrefDropdown {
                                key: "camera_corner"
                                model: [
                                    {
                                        value: "top-left",
                                        text: "Arriba a la izquierda"
                                    },
                                    {
                                        value: "top-right",
                                        text: "Arriba a la derecha"
                                    },
                                    {
                                        value: "bottom-left",
                                        text: "Abajo a la izquierda"
                                    },
                                    {
                                        value: "bottom-right",
                                        text: "Abajo a la derecha"
                                    }
                                ]
                            }
                        }
                    }
                    SettingRow {
                        title: "Forma"
                        hint: "Círculo o rectángulo redondeado."
                        control: Component {
                            PrefDropdown {
                                key: "camera_shape"
                                model: [
                                    {
                                        value: "circle",
                                        text: "Círculo"
                                    },
                                    {
                                        value: "rounded",
                                        text: "Redondeada"
                                    }
                                ]
                            }
                        }
                    }
                    SettingRow {
                        title: "Tamaño"
                        hint: "Qué parte del video ocupa."
                        control: Component {
                            PrefDropdown {
                                key: "camera_size"
                                model: [
                                    {
                                        value: "small",
                                        text: "Pequeña"
                                    },
                                    {
                                        value: "medium",
                                        text: "Mediana"
                                    },
                                    {
                                        value: "large",
                                        text: "Grande"
                                    }
                                ]
                            }
                        }
                    }
                }

                Section {
                    title: "Calidad"

                    SettingRow {
                        title: "Fotogramas por segundo"
                        hint: "30 es lo habitual; 60 pesa el doble."
                        control: Component {
                            PrefDropdown {
                                key: "fps"
                                numeric: true
                                model: [
                                    {
                                        value: "15",
                                        text: "15 fps"
                                    },
                                    {
                                        value: "24",
                                        text: "24 fps"
                                    },
                                    {
                                        value: "30",
                                        text: "30 fps"
                                    },
                                    {
                                        value: "60",
                                        text: "60 fps"
                                    }
                                ]
                            }
                        }
                    }
                    SettingRow {
                        title: "Calidad de video"
                        hint: "Alta ocupa más espacio y exige más al equipo."
                        control: Component {
                            PrefDropdown {
                                key: "quality"
                                model: [
                                    {
                                        value: "compact",
                                        text: "Compacta"
                                    },
                                    {
                                        value: "standard",
                                        text: "Estándar"
                                    },
                                    {
                                        value: "high",
                                        text: "Alta"
                                    }
                                ]
                            }
                        }
                    }
                }

                Section {
                    title: "Archivos"

                    SettingRow {
                        title: "Carpeta de videos"
                        hint: "Dónde se guardan los MP4 al terminar."
                        control: Component {
                            Row {
                                spacing: Theme.spacing.small ?? 0

                                Label {
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: Metrics.textFieldMinWidth
                                    role: "body.medium"
                                    color: Theme.m3onSurfaceVariant
                                    elide: Text.ElideMiddle
                                    text: settings.values.videos_folder
                                }
                                Button {
                                    objectName: "chooseFolder"
                                    anchors.verticalCenter: parent.verticalCenter
                                    type: "tonal"
                                    icon: "folder_open"
                                    text: "Cambiar…"
                                    disabled: settings.picking
                                    onClicked: settings.chooseFolder()
                                }
                            }
                        }
                    }
                }

                Section {
                    title: "Privacidad"

                    SettingRow {
                        title: "Recordar pantalla autorizada"
                        hint: "Evita pedir permiso cada vez que grabas una pantalla."
                        control: Component {
                            PrefSwitch {
                                key: "remember_source"
                            }
                        }
                    }
                    SettingRow {
                        title: "Permisos de pantalla"
                        hint: "Vuelve a pedir autorización en la próxima grabación."
                        control: Component {
                            Button {
                                objectName: "forgetPermissions"
                                type: "tonal"
                                icon: "lock_reset"
                                text: "Olvidar"
                                onClicked: settings.forgetPermissions()
                            }
                        }
                    }
                }

                Section {
                    title: "Atajos"

                    SettingRow {
                        title: "Super+Shift+L"
                        hint: "Elegir qué grabar (pantalla, ventana o área), o terminar"
                    }
                    SettingRow {
                        title: "Ctrl+Shift+R"
                        hint: "Pausar o reanudar"
                    }
                    SettingRow {
                        title: "Ctrl+Shift+S"
                        hint: "Terminar"
                    }
                    SettingRow {
                        title: "Ctrl+Shift+A"
                        hint: "Dibujar sobre la pantalla mientras grabas"
                    }
                }
            }
        }

        SnackbarHost {
            id: snackbars

            objectName: "snackbars"
            anchors.fill: parent
        }

        Connections {
            target: settings

            function onMessage(text) {
                snackbars.show(text);
            }
        }
    }
}
