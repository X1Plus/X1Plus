if [[ "$1" != "-n" ]]; then
	echo "backgrounding ourselves and writing to /sdcard/x1plus/install.log... that's what you always wanted, right?"
	mkdir -p /sdcard/x1plus
	echo "about to restart second stage" > /sdcard/x1plus/install.log
	bash /userdata/x1plus/launch.sh -n > /sdcard/x1plus/install.log 2>&1 &
	exit 0
fi

echo "x1plus Firmware R first-stage payload running"
date

# let the installer know that we are up and running
mkdir -p /sdcard/x1plus
id > /sdcard/x1plus/first_stage_status

# We can't kill bbl_screen until it starts, so wait for that.
while ! pidof bbl_screen >/dev/null; do sleep 1; done

# now kill bbl_screen, and launch the installer
/etc/init.d/S99service_check stop
killall bbl_screen
while pidof bbl_screen >/dev/null; do sleep 1; done

chmod +x /userdata/x1plus/kexec_ui.so

if [ -f /usr/bin/screen_start.sh ]; then
	. /usr/bin/screen_start.sh
else
	export QT_QPA_FB_DRM=1
	export QT_QPA_GENERIC_PLUGINS=evdevkeyboard
	export QT_QPA_EVDEV_KEYBOARD_PARAMETERS=/dev/input/event3
	export QT_QUICK_ROTATE_SCREEN=270
	export QT_IM_MODULE=qtvirtualkeyboard
fi

LD_PRELOAD=/userdata/x1plus/kexec_ui.so \
KEXEC_LAUNCH_INSTALLER=yes \
exec bbl_screen
