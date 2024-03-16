#!/bin/sh
/etc/init.d/S99service_check stop
/etc/init.d/S99screen_service stop
sleep 5
/opt/bbl_screen_patch -platform vnc:size=1280x720

