#!/bin/sh
# Opt-in only: the owner's damaged Atmel touchscreen, not a general Samsung default.
for device in 'Atmel Atmel maXTouch Digitizer' 'Atmel Atmel maXTouch Digitizer stylus' 'Atmel Atmel maXTouch Digitizer eraser'; do
    xinput disable "$device" 2>/dev/null || true
done
for device in 'ZNT0001:00 14E5:E545 Touchpad' 'ZNT0001:00 14E5:E545 Mouse'; do
    xinput enable "$device" 2>/dev/null || true
done
