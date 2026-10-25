qml_module(wysun-shaders
    URI Wysun.Shaders
    SOURCES
        shaders.hpp
    LIBRARIES
        Qt::Gui
        wysun-config
)

qt_add_shaders(wysun-shaders "shaders"
    BATCHABLE OPTIMIZED NOHLSL NOMSL
    GLSL "300es,330"
    PREFIX "/shaders"
    FILES
        crossfade.frag
        chromatic-bloom.frag
        colour-distance.frag
        crosshatch.frag
        crosswarp.frag
        directional.frag
        directional-wipe.frag
        fade-colour.frag
        glitch.frag
        glitch-displace.frag
        heat-melt.frag
        ink-splash.frag
        inkwell-drop.frag
        iris.frag
        liquid-rift.frag
        morph.frag
        parametric-glitch.frag
        perlin.frag
        pixelate.frag
        pixelfade-wave.frag
        plasma-flow.frag
        polka-dots-curtain.frag
        puzzle-right.frag
        random-squares.frag
        smoke.frag
        soft-warp-fade.frag
        voronoi-shatter.frag
        zoom-blur-pull.frag
)
