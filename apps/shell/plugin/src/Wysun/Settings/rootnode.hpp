#pragma once

#include "common.hpp"
#include "objectnode.hpp"
#include "settingsfile.hpp"

namespace wysun::settings {

class RootNode : public ObjectNode {
    Q_OBJECT

    Q_PROPERTY(QList<wysun::settings::Diagnostic> diagnostics READ diagnostics NOTIFY diagnosticsChanged)

public:
    explicit RootNode(bool watch, const QString& path, RootNode* fallback, QObject* parent = nullptr);

    [[nodiscard]] QList<Diagnostic> diagnostics() const;

    void load();

signals:
    void diagnosticsChanged();
    void treeLoaded(wysun::settings::RootNode* self);
    void treeLoadFailed(wysun::settings::RootNode* self, const QString& error);
    void treeSaveFailed(wysun::settings::RootNode* self, const QString& error);

private:
    SettingsFile* const m_file;
    QList<Diagnostic> m_diagnostics;

    void reloadFromFile();
    void saveToFile();
};

} // namespace wysun::settings
