#!/bin/bash
LOGFILE=/mnt/sdcard/perf_log.txt

date > $LOGFILE
while true ; do
	free >> $LOGFILE
	ps -auwxf >> $LOGFILE
	sleep 30
done
