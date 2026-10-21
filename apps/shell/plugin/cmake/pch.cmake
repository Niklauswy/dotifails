add_library(wysun-pch INTERFACE)
target_precompile_headers(wysun-pch INTERFACE
    <qobject.h>
    <qqmlintegration.h>
    <qstring.h>
    <qqmlengine.h>
    <qloggingcategory.h>
    <qvariant.h>
    <qtimer.h>
    <qdir.h>
    <qlist.h>
    <qstringlist.h>
    <qpointer.h>
)
