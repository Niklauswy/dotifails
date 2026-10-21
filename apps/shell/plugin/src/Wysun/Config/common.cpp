// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Base: 6c70d5cb0cbf31413d300699540c858ad28c1539; véanse LICENSE y UPSTREAM.json.
#include "common.hpp"

#include <qstandardpaths.h>

namespace wysun::config {

using Qt::StringLiterals::operator""_s;

Q_LOGGING_CATEGORY(lcConfig, "wysun.config", QtInfoMsg)

QString configDir() {
    return QStandardPaths::writableLocation(QStandardPaths::GenericConfigLocation) + u"/wysun/shell"_s;
}

QString monitorConfigDir() {
    return configDir() + u"/monitors"_s;
}

} // namespace wysun::config
