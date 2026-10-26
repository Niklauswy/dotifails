#include "tokensattached.hpp"

#include <qquickitem.h>

#include "common.hpp"

namespace wysun::config {

namespace {

const AppearanceConfig* resolveAppearance(const ConfigRoot* config, bool complete, const char* prop, QObject* parent) {
    if (config)
        return config->appearance();
    if ((complete || !qobject_cast<QQuickItem*>(parent)) && parent)
        qCWarning(lcConfig, "Tokens.%s accessed without a screen set on %s", prop, parent->metaObject()->className());
    return ConfigSingleton::instance()->appearance();
}

} // namespace

Tokens::Tokens(QObject* parent)
    : QQuickAttachedPropertyPropagator(parent) {
    initialize();
}

void Tokens::classBegin() {}

void Tokens::componentComplete() {
    m_complete = true;
}

QString Tokens::screen() const {
    return m_screen;
}

void Tokens::inheritScreen(const QString& screen) {
    if (screen == m_screen)
        return;

    m_screen = screen;

    m_config = m_screen.isEmpty() ? nullptr : ConfigSingleton::instance()->forScreen(m_screen);

    propagateScreen();
    emit sourceChanged();
}

void Tokens::propagateScreen() {
    const auto children = attachedChildren();
    for (auto* const child : children) {
        auto* const tokens = qobject_cast<Tokens*>(child);
        if (tokens)
            tokens->inheritScreen(m_screen);
    }
}

void Tokens::attachedParentChange(
    QQuickAttachedPropertyPropagator* newParent, QQuickAttachedPropertyPropagator* oldParent) {
    Q_UNUSED(oldParent);
    const auto* tokens = qobject_cast<Tokens*>(newParent);
    if (tokens)
        inheritScreen(tokens->screen());
}

#define TOKENS_ATTACHED_GETTER(Type, name)                                                                             \
    const Type* Tokens::name() const {                                                                                 \
        auto* a = resolveAppearance(m_config, m_complete, #name, parent());                                            \
        return a ? a->name() : nullptr;                                                                                \
    }

TOKENS_ATTACHED_GETTER(AppearanceRounding, rounding)
TOKENS_ATTACHED_GETTER(AppearanceSpacing, spacing)
TOKENS_ATTACHED_GETTER(AppearancePadding, padding)

#undef TOKENS_ATTACHED_GETTER

const AppearanceTransparency* Tokens::transparency() {
    return ConfigSingleton::instance()->appearance()->transparency(); // Transparency is always global
}

const SizeTokens* Tokens::sizes() {
    return TokensRoot::instance()->sizes(); // Sizes are the same on every screen
}

const FontTokens* Tokens::font() const {
    return (m_config ? m_config : ConfigSingleton::instance())->fontTokens();
}

const AnimTokens* Tokens::anim() {
    return AnimTokens::instance();
}

Tokens* Tokens::qmlAttachedProperties(QObject* object) {
    return new Tokens(object);
}

} // namespace wysun::config
