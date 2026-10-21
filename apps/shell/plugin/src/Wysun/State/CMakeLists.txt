qml_module(wysun-state
    URI Wysun.State
    INCLUDE_PREFIX state
    SOURCES
        common.cpp
        rootnodes.cpp
    DEPENDENCIES
        Wysun.Settings
)
target_link_libraries(wysun-state PUBLIC wysun-settings)
