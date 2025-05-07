#!/bin/sh

source /usr/bin/mqtt_access.sh

function set_heatbed_temp() {
    temp=$1
    json="{ \
        \"print\":{\"command\":\"gcode_line\", \"sequence_id\":\"2002\", \"param\":\"M140 S$temp\"} \
    }"
    mqtt_pub "$json"
}

if [ "$#" -ne 2 ]; then
    echo "Usage: $0 -s <temperature>"
    exit 1
fi

while getopts ":s:" opt; do
  case ${opt} in
    s )
      temperature=$OPTARG
      set_heatbed_temp $temperature
      ;;
    \? )
      echo "Invalid option: $OPTARG" 1>&2
      ;;
    : )
      echo "Invalid option: $OPTARG requires an argument" 1>&2
      ;;
  esac
done
