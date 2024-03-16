#!/bin/bash

# disable upgrade binary
mount -o bind /dev/null /usr/bin/upgrade

# Always generate our modded service_List, to ensure support across OTAs
cp /usr/etc/conf/service_list.list /tmp/service_list.list
sed -i 's|/usr/bin/upgrade.*||' /tmp/service_list.list

# Mount it to make service_check.sh happy
mount -o bind /tmp/service_list.list /usr/etc/conf/service_list.list

# Ensure we are in LAN mode to prevent cloud connectivity
echo -n "lan" > /config/device/conn_mode

# Make sure our BBL_Screen process is killed so we boot, otherwise 
# we hang for a while.
killall bbl_screen

exit 0
