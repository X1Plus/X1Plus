#!/bin/bash
DEVICE_SN=$(cat /proc/cmdline | xargs -n1 | grep "bbl_serial=" | sed "s|bbl_serial=||")

LOGFILE=/mnt/sdcard/x1plus/printers/$DEVICE_SN/logs/perf_log.txt

date > $LOGFILE
while true ; do
	df >> $LOGFILE
	free >> $LOGFILE
	ps -auwxf >> $LOGFILE
	sleep 10
done
