#include "rootnodes.hpp"

#include <qfile.h>
#include <qjsondocument.h>
#include <qqmlengine.h>

#include "core/toaster.hpp"
#include "util/i18n.hpp"
#include "common.hpp"

namespace wysun::config {

using Qt::StringLiterals::operator""_s;

namespace {

using util::i18n::mark;
using util::i18n::markN;

struct Handler {
    static void loaded(settings::RootNode* layer, const QString& screen) {
        if (!screen.isEmpty())
            return;

        const auto* config = static_cast<ConfigRoot*>(layer);
        if (!config->utilities()->toasts()->configLoaded())
            return;

        const auto issues = static_cast<int>(config->diagnostics().count());
        const auto message = issues > 0
                                 ? markN(u"Config loaded with %n issue."_s, u"Config loaded with %n issues."_s, issues)
                                 : mark(u"Config loaded successfully!"_s);
        Toaster::instance()->toast(mark(u"Config loaded"_s), message,
            issues > 0 ? u"settings_alert"_s : u"rule_settings"_s, issues > 0 ? Toast::Type::Warning : Toast::Type::Info);
    }

    static void loadFailed(const QString& error, const QString& screen) {
        const auto title =
            // TRANSLATORS: %1 = a monitor name
            screen.isEmpty() ? mark(u"Failed to parse config"_s) : mark(u"Failed to parse config for %1"_s, { screen });
        Toaster::instance()->toast(title, error, u"settings_alert"_s, Toast::Type::Warning);
    }

    static void saveFailed(const QString& error, const QString& screen) {
        const auto title =
            // TRANSLATORS: %1 = a monitor name
            screen.isEmpty() ? mark(u"Failed to save config"_s) : mark(u"Failed to save config for %1"_s, { screen });
        Toaster::instance()->toast(title, error, u"settings_alert"_s, Toast::Type::Error);
    }
};

} // namespace

ConfigRoot::ConfigRoot(const QString& path, ConfigRoot* fallback, QObject* parent)
    : RootNode(true, path, fallback, parent)
    , m_fontTokens(new FontTokens(this)) {
    bindTokens();
}

const FontTokens* ConfigRoot::fontTokens() const {
    return m_fontTokens;
}

void ConfigRoot::bindTokens() {
    const auto* tokens = TokensRoot::instance()->appearance();
    m_appearance->rounding()->bindTokens(tokens->rounding());
    m_appearance->spacing()->bindTokens(tokens->spacing());
    m_appearance->padding()->bindTokens(tokens->padding());
    m_appearance->anim()->durations()->bindTokens(tokens->animDurations());

    m_fontTokens->bindFont(m_appearance->font());
}

QJsonObject shellTokens(const QJsonObject& tokens) {
    QJsonObject appearance;
    for (const auto& group : { u"rounding"_s, u"spacing"_s, u"padding"_s }) {
        if (tokens.contains(group))
            appearance.insert(group, tokens.value(group));
    }
    const auto anim = tokens.value(u"anim"_s).toObject();
    if (anim.contains(u"durations"_s))
        appearance.insert(u"animDurations"_s, anim.value(u"durations"_s));
    if (anim.contains(u"curves"_s))
        appearance.insert(u"curves"_s, anim.value(u"curves"_s));
    return { { u"appearance"_s, appearance } };
}

TokensRoot* TokensRoot::instance() {
    static TokensRoot instance;
    return &instance;
}

TokensRoot* TokensRoot::create(QQmlEngine*, QJSEngine*) {
    QQmlEngine::setObjectOwnership(instance(), QQmlEngine::CppOwnership);
    return instance();
}

TokensRoot::TokensRoot(QObject* parent)
    : ObjectNode(nullptr, parent) {
    load(tokensPath());
}

void TokensRoot::load(const QString& path) {
    QJsonObject tokens;
    if (path.isEmpty()) {
        qCWarning(lcConfig) << "wysun/theme/tokens.json not found, using the built-in tokens";
    } else {
        QFile file(path);
        QJsonParseError error{};
        const auto document = file.open(QIODevice::ReadOnly) ? QJsonDocument::fromJson(file.readAll(), &error)
                                                             : QJsonDocument();
        if (document.isObject())
            tokens = document.object();
        else
            qCWarning(lcConfig).noquote() << "Could not read" << path << '(' << (file.isOpen() ? error.errorString()
                                                                                            : file.errorString())
                                          << "), using the built-in tokens";
    }

    QList<settings::Diagnostic> diagnostics;
    syncJson(shellTokens(tokens), diagnostics);
    if (!diagnostics.isEmpty())
        qCWarning(lcConfig).noquote() << path << "has" << diagnostics.count()
                                      << "invalid tokens; they keep their built-in values";
}

SETTINGS_SINGLETON_IMPL(ConfigSingleton, ConfigRoot, configDir(), monitorConfigDir(), u"shell.json"_s, Handler)

} // namespace wysun::config
