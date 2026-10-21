#pragma once

#include <qquickimageprovider.h>

#include "imagecacher.hpp"

namespace wysun::images {

class CachingImageProvider : public QQuickAsyncImageProvider {
public:
    using FillMode = ImageCacher::FillMode;

    explicit CachingImageProvider(FillMode fillMode);

    QQuickImageResponse* requestImageResponse(const QString& id, const QSize& requestedSize) override;

private:
    FillMode m_fillMode;
};

} // namespace wysun::images
