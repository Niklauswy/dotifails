#version 440

layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;

layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    float progress;
    float outgoingZoom;
    float incomingZoom;
    float blurStrength;
    float revealStart;
    float revealEnd;
};

layout(binding = 1) uniform sampler2D from;
layout(binding = 2) uniform sampler2D to;

void main() {
    float p = clamp(progress, 0.0, 1.0);
    // Exact endpoints keep captures of interrupted transitions seamless.
    if (p <= 0.0) {
        fragColor = texture(from, qt_TexCoord0) * qt_Opacity;
        return;
    }
    if (p >= 1.0) {
        fragColor = texture(to, qt_TexCoord0) * qt_Opacity;
        return;
    }

    vec2 center = vec2(0.5);
    float travel = smoothstep(0.0, 1.0, p);
    vec2 oldUv = center + (qt_TexCoord0 - center) / mix(1.0, outgoingZoom, travel);
    vec2 newUv = center + (qt_TexCoord0 - center) / mix(incomingZoom, 1.0, travel);

    // Anticipation, readable overlap, then a sharp image settling into place.
    float dissolve = smoothstep(revealStart, revealEnd, p);
    float blur = blurStrength * sin(p * 3.14159265359);
    vec2 stepUv = (center - oldUv) * blur;
    // Five stable, weighted taps on the outgoing image, one on the incoming.
    // The previous effect used 26 fetches and blurred both sides of the swap.
    vec4 outgoing = texture(from, oldUv - 2.0 * stepUv)
        + 4.0 * texture(from, oldUv - stepUv)
        + 6.0 * texture(from, oldUv)
        + 4.0 * texture(from, oldUv + stepUv)
        + texture(from, oldUv + 2.0 * stepUv);
    outgoing /= 16.0;
    vec4 incoming = texture(to, newUv);
    fragColor = mix(outgoing, incoming, dissolve) * qt_Opacity;
}
