#!/bin/bash

chars="/-\|"

echo "Booting X1Plus..." > /tmp/.progress_spinner

while :; do
  for (( i=0; i<${#chars}; i++ )); do
    PROGRESS=$(cat /tmp/.progress_spinner 2>/dev/null)
    if [ "$PROGRESS" != "" ]; then
      sleep 0.2
      echo -en "\e[?25l\e[s\e[21;0H\e[2K${chars:$i:1} $PROGRESS \e[u" > /dev/tty0
    else
      exit 0
    fi
  done
done

exit 0
