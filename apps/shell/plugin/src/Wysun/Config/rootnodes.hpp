#pragma once

#include <qjsonobject.h>

#include "settings/rootnode.hpp"
#include "settings/singleton.hpp"
#include "appearanceconfig.hpp"
#include "backgroundconfig.hpp"
#include "barconfig.hpp"
#include "borderconfig.hpp"
#include "common.hpp"
#include "dashboardconfig.hpp"
#include "font.hpp"
#include "generalconfig.hpp"
#include "launcherconfig.hpp"
#include "lockconfig.hpp"
#include "nexusconfig.hpp"
#include "notifsconfig.hpp"
#include "osdconfig.hpp"
#include "serviceconfig.hpp"
#include "sessionconfig.hpp"
#include "sidebarconfig.hpp"
#include "tokens.hpp"
#include "userpaths.hpp"
#include "utilitiesconfig.hpp"

namespace wysun::config {

class ConfigRoot : public settings::RootNode {
    CONFIG_NODE_NO_CTOR(ConfigRoot, settings::RootNode)
    QML_ANONYMOUS

    CONFIG_PROPERTY(bool, enabled, true)
    CONFIG_SUBOBJECT(AppearanceConfig, appearance)
    CONFIG_SUBOBJECT(GeneralConfig, general)
    CONFIG_SUBOBJECT(BackgroundConfig, background)
    CONFIG_SUBOBJECT(BarConfig, bar)
    CONFIG_SUBOBJECT(BorderConfig, border)
    CONFIG_SUBOBJECT(DashboardConfig, dashboard)
    CONFIG_SUBOBJECT(LauncherConfig, launcher)
    CONFIG_SUBOBJECT(LockConfig, lock)
    CONFIG_SUBOBJECT(NexusConfig, nexus)
    CONFIG_SUBOBJECT(NotifsConfig, notifs)
    CONFIG_SUBOBJECT(OsdConfig, osd)
    CONFIG_SUBOBJECT(ServiceConfig, services)
    CONFIG_SUBOBJECT(SessionConfig, session)
    CONFIG_SUBOBJECT(SidebarConfig, sidebar)
    CONFIG_SUBOBJECT(UtilitiesConfig, utilities)
    CONFIG_SUBOBJECT(UserPaths, paths)

public:
    explicit ConfigRoot(const QString& path, ConfigRoot* fallback = nullptr, QObject* parent = nullptr);

    [[nodiscard]] const FontTokens* fontTokens() const;

private:
    // Binds computed values to the global token base values
    void bindTokens();

    FontTokens* const m_fontTokens;
};

// The shape and motion tokens of apps/python/wysun_core/tokens.json, the source the Qt apps read too. The
// installer copies it to $XDG_DATA_HOME/wysun/theme/tokens.json and it is read once at startup: whatever is
// missing or of another type keeps its value from tokens.hpp, the fallback. Sizes and wallpaper motion are
// shell-only and live only in tokens.hpp.
class TokensRoot : public settings::ObjectNode {
    CONFIG_NODE_NO_CTOR(TokensRoot, settings::ObjectNode)
    QML_NAMED_ELEMENT(TokenConfig)
    QML_SINGLETON

    CONFIG_SUBOBJECT(AppearanceTokens, appearance)
    CONFIG_SUBOBJECT(SizeTokens, sizes)

public:
    static TokensRoot* instance();
    static TokensRoot* create(QQmlEngine*, QJSEngine*);

private:
    explicit TokensRoot(QObject* parent = nullptr);

    void load(const QString& path);
};

// Maps tokens.json onto the TokensRoot tree: rounding, spacing and padding as they are, anim.durations and
// anim.curves into appearance.animDurations and appearance.curves. The other groups are for the Qt apps.
[[nodiscard]] QJsonObject shellTokens(const QJsonObject& tokens);

SETTINGS_SINGLETON_DECL(ConfigSingleton, ConfigRoot, GlobalConfig)

} // namespace wysun::config
