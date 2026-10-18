# Blue CRT assets

Tux: generated with the built-in image generation tool, transparent RGBA original retained at `greeter/assets/tux.png` and `plymouth/tux.png`. Runtime rendering scales and composites the original; no external service or generation is needed during installation.

Prompt:

> Create a production-ready standalone Linux Tux mascot sprite, full body seated penguin with friendly large white eyes, glossy black head and flippers, white belly, golden yellow beak and large feet. A beautifully art-directed late-1990s prerendered computer mascot, like a high quality 1997 workstation CD-ROM illustration, subtly dithered shading with crisp pixel-aware edges, substantial volume and realistic soft highlights, restrained blue CRT rim illumination on the black silhouette. Classic recognizable Tux anatomy and proportions, seated facing viewer, a slight friendly head tilt, feet spread. NO modern flat vector icon style, NO text, NO computer, NO surrounding objects, NO logos or background scene. Full mascot centered with generous transparent margins; isolated on a truly transparent background. This image will sit next to a gray beveled login dialog on a saturated navy-blue CRT desktop. Rich but restrained detail, clear silhouette even at 220px. Output one polished 1024x1024 transparent PNG.

Procedural assets (`generate_assets.py`): three CRT backgrounds, nine dialog tiles, nine selection tiles, 72 loading frames, 16 deterministic noise overlays, scan band, curtain and an invisible greeter logo. DejaVu fonts retain their included license. Live greeter glass, scanlines, sync disturbance, power-on reveal and keystroke indicator are Cairo drawings in `native/blue-crt/blue-crt.c`.

## Revision 4 — additional generated assets

Built-in image generation, transparent output. Original atlases remain intact:

- `greeter/assets/tux-motion.png`: eight equal cells, four columns × two rows. Cairo clips each cell at runtime, blends poses and anchors the feet while breathing. The original `tux.png` remains a fallback.
- `grub/computer.png`: original CRT computer illustration; `grub/computer-icon.png` is a 144px export produced with gdk-pixbuf-thumbnailer for GRUB's minimum image dimensions. `plymouth/computer.png` is an unchanged copy used by shutdown/reboot.

Tux prompt:

> Use case: identity-preserve. Create a production animation SPRITE SHEET of the supplied Tux mascot, keeping exactly its glossy late-1990s rendered style, blue rim light, anatomy, colours, camera and body scale. Transparent RGBA background. ONE atlas, precisely FOUR columns by TWO rows, EIGHT equal square cells, no gaps between cells, no labels, no grid lines. Each cell contains the full same seated mascot centred at the SAME coordinates, with identical feet baseline and head scale and at least 10% transparent margin; no body part crosses cell edges. Reading left to right, top to bottom: frame 0 idle eyes open both flippers down; frame 1 identical but eyelids halfway closed; frame 2 identical but both eyes fully closed natural blink; frame 3 eyes open belly slightly expanded breathing, otherwise same pose; frame 4 right flipper (on viewer's left) lifted halfway in preparation to wave; frame 5 same flipper raised in a friendly wave; frame 6 same raised flipper gently tilted outward at the tip; frame 7 same flipper returning halfway down. Keep torso, beak and feet absolutely stationary across all cells so a sprite animation is stable. Crisp readable full-body silhouette. This is a functional 8-frame animation asset for a Linux login screen, not an illustration board. Output wide 4:2 canvas, ideally 2048x1024.

Computer prompt:

> Use case: stylized-concept. A single production UI illustration asset for a nostalgic Linux BIOS/GRUB boot selector: a beautifully detailed compact 1995 beige-grey CRT desktop computer with its matching small horizontal system unit below, three-quarter view, isolated on true transparent background. Its curved glass screen glows deep cobalt blue with a tiny white command cursor only, absolutely NO words, letters, logos or numbers. Thick sculpted grey plastic bevel, fine moulded ventilation slots, small green power indicator, disk slot and subtle age in the plastic, restrained reflected blue light. Late-1990s high-quality prerendered desktop icon aesthetic, crisp dithered shading, tactile depth, friendly proportions, elegant collectible object. NO keyboard, mouse, cables, desk or surrounding background. Full object centered with 12 percent transparent margins, strong silhouette at 128 pixels. Avoid modern flat vector or neon cyberpunk. Square PNG.

Additional procedural assets: 48 shutdown frames, 48 reboot frames, native menu class icons, nine-slice timeout relief and keyboard caps. See `generate_assets.py`.
