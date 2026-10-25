qml_module(wysun-components
    URI Wysun.Components
    SOURCES
        animatedrepeater.cpp
        lazylistview.cpp
        wavyline.cpp
        buttonrow.cpp
        circularindicatormanager.cpp
        linearindicatormanager.cpp
        sparklineitem.cpp
        visualiserbars.cpp
        roundedmask.cpp
    LIBRARIES
        Qt::Gui
        Qt::Quick
        wysun-core
    DEPENDENCIES
        Wysun
)

qt_add_shaders(wysun-components "components_shaders"
    BATCHABLE OPTIMIZED NOHLSL NOMSL
    GLSL "300es,330"
    PREFIX "/"
    FILES
        shaders/roundedmask.frag
        shaders/roundedmask.vert
)

# The waffle mascot (components/widgets/Waffle.qml): the lock's own shader, so it is drawn the same way
# in the lock, the boot farewell and the shell's panels.
qt_add_shaders(wysun-components "mascot_shader"
    BATCHABLE OPTIMIZED NOHLSL NOMSL
    GLSL "300es,330"
    PREFIX "/"
    FILES
        ${CMAKE_CURRENT_SOURCE_DIR}/../../../../modules/lockscreen/shaders/mascot.frag
    OUTPUTS
        shaders/mascot.frag.qsb
)
