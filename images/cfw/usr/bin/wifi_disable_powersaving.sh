#!/bin/sh

while true ; do
  POWER="`iwconfig 2>&1 | grep 'Power Management:off'`"
  if [ "$POWER" = "" ] ; then
    iwconfig wlan0 power off > /dev/null 2>&1
    logger -t wifi_disable_powersaving "[ turning powersaving off ]"
  fi
  sleep 4
done
