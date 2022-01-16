#!/bin/sh

#xset -dpms #disabilita energystar
#xset s off #disabilita screenserver
#xset s noblank
#xset dpms 0 3600 6000
## 0 = standby
## 3600 sec = suspend
## 6000 sec = off

unclutter -idle 0.1 &
matchbox-window-manager &
python3 /home/pi/screensaver/screensaver.py --slidetime 30 --idlewait 300 | tee /home/pi/screensaver.log &

sleep 5 &
/usr/bin/chromium-browser --kiosk --start-fullscreen --no-first-run http://127.0.0.1:1880/ui
