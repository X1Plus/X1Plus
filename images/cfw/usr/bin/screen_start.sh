#!/bin/sh

TS_NODE=/dev/input/event1
for INPUT in /sys/class/input/event*; do
	INPUT_NAME=$(cat $INPUT/device/name)
	if [ "$INPUT_NAME" == "tlsc6x_touch" -o "$INPUT_NAME" == "fts_ts" ]; then
		TS_NODE=$(echo $INPUT | sed -e 's#/sys/class/input/event#/dev/input/event#')
		echo "screen_start: found $INPUT_NAME on $TS_NODE" >&2
	fi
done

# X1
export QT_QPA_FB_DRM=1;
# sometimes the camera shows up before the gpio-keys depending on usb timing, make sure we get the right one
export QT_QPA_EVDEV_KEYBOARD_PARAMETERS=/dev/input/by-path/platform-gpio-keys-event;
export QT_IM_MODULE=qtvirtualkeyboard;
#export QT_QPA_GENERIC_PLUGINS=evdevkeyboard
export QT_QPA_LINUXFB_ROTATION=270;
export QT_QPA_EVDEV_TOUCHSCREEN_PARAMETERS=$TS_NODE:rotate=90;
export QT_QPA_FB_NO_LIBINPUT=1;
