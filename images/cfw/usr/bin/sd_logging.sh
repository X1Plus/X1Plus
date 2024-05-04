#!/bin/sh

# Toggle SD logging. This feature is for debugging purposes only.

DEVICE_ID=$(cat /proc/cmdline | xargs -n1 | grep "bbl_serial=" | sed "s|bbl_serial=||")
logpath="/mnt/sdcard/x1plus/printers/$DEVICE_ID/logsd"
echo $logpath
if [ -f "$logpath" ]; then
    rm "$logpath"
    echo "log path set to /tmp/"
else
    touch "$logpath"
    echo "log path set to /sdcard/"
fi

/etc/init.d/S01logging restart
/etc/init.d/S93syslog_shim restart
