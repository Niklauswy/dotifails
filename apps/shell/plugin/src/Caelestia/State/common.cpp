// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Base: 6c70d5cb0cbf31413d300699540c858ad28c1539; véanse LICENSE y UPSTREAM.json.
#include "common.hpp"

#include <qstandardpaths.h>

namespace caelestia::state {

using Qt::StringLiterals::operator""_s;

Q_LOGGING_CATEGORY(lcState, "caelestia.state", QtInfoMsg)

QString stateDir() {
    return QStandardPaths::writableLocation(QStandardPaths::GenericStateLocation) + u"/wysun"_s;
}

QString monitorStateDir() {
    return stateDir() + u"/monitors"_s;
}

QString runtimeDir() {
    return QStandardPaths::writableLocation(QStandardPaths::RuntimeLocation) + u"/wysun"_s;
}

QString monitorRuntimeDir() {
    return runtimeDir() + u"/monitors"_s;
}

} // namespace caelestia::state
