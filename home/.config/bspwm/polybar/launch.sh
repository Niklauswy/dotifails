#!/usr/bin/env sh

## Add this to your wm startup file.

# Terminate already running bar instances
killall -q polybar

# Wait until the processes have been shut down
while pgrep -u $UID -x polybar >/dev/null; do sleep 1; done

# Launch bar1 and bar2
if type "xrandr"; then
  for m in $(xrandr --query | grep " connected" | cut -d" " -f1); do
    MONITOR=$m polybar -r -q logo -c "~/.config/bspwm/polybar/pruebas/config" &
    MONITOR=$m polybar -r -q ventanas -c "~/.config/bspwm/polybar/pruebas/config" &


  done
else 
  polybar -q logo -c "~/.config/bspwm/polybar/pruebas/config" &
  polybar -q ventanas -c "~/.config/bspwm/polybar/pruebas/config" &

fi
