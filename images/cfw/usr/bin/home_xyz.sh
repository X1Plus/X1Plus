#!/bin/sh

source /usr/bin/mqtt_access.sh

function home_xyz() {
    json="{ \
        \"print\":{\"command\":\"gcode_line\", \"sequence_id\":\"2001\", \"param\":\"G28\"} \
    }"
    mqtt_pub "$json"
}

home_xyz