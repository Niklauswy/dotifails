// Text fields (outlined and filled) and the search bar.
import QtQuick
import WysunM3
import ".."

Page {
    Section {
        title: "Barra de búsqueda"
        note: "Ctrl+L enfoca; Escape borra; Enter busca."

        SearchBar {
            width: Math.min(parent.width, Metrics.textFieldMinWidth * 3)
            placeholder: "Buscar en Wysun"
            trailing: Component {
                IconButton {
                    icon: "tune"
                }
            }
        }
    }

    Section {
        title: "Campos de texto"

        TextField {
            label: "Nombre"
            supportingText: "Como aparecerá en la carpeta"
        }
        TextField {
            label: "Carpeta"
            leadingIcon: "folder"
            trailingIcon: "close"
            text: "Documentos"
        }
        TextField {
            label: "Contraseña"
            echoMode: TextInput.Password
            trailingIcon: "visibility"
        }
        TextField {
            label: "Nombre"
            error: true
            errorText: "Ya existe un archivo con ese nombre"
            text: "foto.png"
        }
        TextField {
            label: "Deshabilitado"
            disabled: true
            text: "Solo lectura"
        }
        TextField {
            variant: "filled"
            label: "Etiqueta (filled)"
        }
        TextField {
            variant: "filled"
            label: "Con icono"
            leadingIcon: "search"
            text: "mar"
        }
    }

    Section {
        title: "Deslizadores"
        note: "Pista de 4 px y asa de 20 px; la variante ondulada es la del progreso de una canción."

        Slider {
            width: Metrics.textFieldMinWidth * 1.5
            value: 0.4
        }
        Slider {
            width: Metrics.textFieldMinWidth * 1.5
            value: 0.65
            wavy: true
            waveMoving: true
        }
    }
}
