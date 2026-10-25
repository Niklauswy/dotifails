#version 440
// Wysun boot · the phosphor. Turns a clean render into what an old office CRT would show: coarse
// pixels, few brightness levels with ordered (Bayer) dithering between them, a dark scanline at
// the bottom of every pixel row and a little colour fringing. Works on opaque frames and on
// transparent sprites (the glow dithers into the glass).

layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;

layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    vec2 res;       // size of the item in pixels
    float cell;     // size of one phosphor pixel
    float levels;   // brightness steps per channel
};
layout(binding = 1) uniform sampler2D source;

float bayer(vec2 c) {
    // 4x4 ordered dither threshold in 0..1.
    int x = int(mod(c.x, 4.0));
    int y = int(mod(c.y, 4.0));
    int index = x + y * 4;
    const float matrix[16] = float[16](0.0, 8.0, 2.0, 10.0, 12.0, 4.0, 14.0, 6.0,
                                       3.0, 11.0, 1.0, 9.0, 15.0, 7.0, 13.0, 5.0);
    return (matrix[index] + 0.5) / 16.0;
}

vec4 straight(vec4 c) {
    return c.a > 0.0 ? vec4(c.rgb / c.a, c.a) : vec4(0.0);
}

void main() {
    vec2 pixel = qt_TexCoord0 * res;
    vec2 c = floor(pixel / cell);
    vec2 step_ = vec2(cell / res.x, 0.0);
    vec2 uv = (c + 0.5) * cell / res;

    vec4 centre = straight(texture(source, uv));
    vec4 left = straight(texture(source, uv - step_));
    vec4 right = straight(texture(source, uv + step_));
    // The beam lands a little late for red and early for blue.
    vec3 colour = vec3(mix(centre.r, left.r, 0.35), centre.g, mix(centre.b, right.b, 0.35));
    float alpha = max(centre.a, max(left.a, right.a) * 0.6);

    float threshold = bayer(c);
    colour = floor(colour * levels + threshold) / levels;
    alpha = clamp(floor(alpha * levels + threshold) / levels, 0.0, 1.0);

    // Each phosphor row ends in a dark gap: the scanline.
    float row = mod(pixel.y, cell);
    float scan = row >= cell - 1.0 ? 0.55 : 1.0;
    fragColor = vec4(clamp(colour, 0.0, 1.0) * scan * alpha, alpha) * qt_Opacity;
}
