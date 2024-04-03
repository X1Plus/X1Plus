#!/bin/sh

while true ; do
  POWER="`iw wlan0 get power_save 2>&1 | grep 'Power save: off'`"
  if [ "$POWER" = "" ] ; then
    iw wlan0 set power_save off > /dev/null 2>&1
    logger -t wifi_disable_powersaving "[ turning powersaving off ]"
  fi
  sleep 4
done
