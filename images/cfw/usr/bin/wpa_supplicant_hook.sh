#!/bin/bash

echo "Starting wifi, checking driver status..."

WIFI_READY=`cat /proc/net/dev | grep wlan0`
while [ -z "$WIFI_READY" ]
do
    sleep 1
    WIFI_READY=`cat /proc/net/dev | grep wlan0`
    #echo "wifi ready: $WIFI_READY"
    CNT=`expr $CNT + 1`
    if [ $CNT -gt 100 ];then
        echo "wifi driver is not ready. please check if /etc/init.d/S36load_wifi_modules run correctly. then run /etc/init.d/S67wifi start"
        exit 0
    fi
done
echo "wifi driver is ready"
SSID=`grep ssid /userdata/cfg/wpa_supplicant.conf | cut -d '"' -f 2`
PWD=`grep psk /userdata/cfg/wpa_supplicant.conf | cut -d '"' -f 2`
if [ "x$SSID" = "xSSID" ];then
    echo "ssid in /userdata/cfg/wpa_supplicant.conf not valid"
    exit 0
fi
if [ "x$PWD" = "xPWD" ];then
    echo "passwd in /userdata/cfg/wpa_supplicant.conf not valid"
    exit 0
fi


mkdir -p /var/run/wpa_supplicant

wpa_cli -iwlan0 terminate > /dev/null 2>&1
# kill wpa_supplicant started by connman
killall wpa_supplicant

[ -e "/sys/class/net/eth0/device/bNumEndpoints" ] || wpa_supplicant -B -Dnl80211 -iwlan0 -c /data/cfg/wpa_supplicant.conf
[ -e "/sys/class/net/eth0/device/bNumEndpoints" ] || wpa_cli -iwlan0 -a /usr/bin/wpa_disconnect_hook.sh -B
#/usr/sbin/bbl-ble.sh &

while true; do
	sleep 2

	if [ ! -e "/sys/class/net/eth0/device/bNumEndpoints" ]; then

		# wait for wifi config COMPLETED, if not, continue
		wpa_cli -iwlan0 status | grep -q 'wpa_state=COMPLETED' || continue
		# echo "wifi status: COMPLETED"

		# if ip address or default route loss, retry dhcp
		ip_addr=`wpa_cli -iwlan0 status | grep 'ip_address='`
		default_route=`route -n | grep '^0\.0\.0\.0.*wlan0$'`
		if [ -z "${ip_addr}" ] || [ -z "${default_route}" ]; then
			# echo "restart DHCPC"
			sleep 1
			wlan0_ready=`ifconfig | grep wlan0`
			if [ -n "${wlan0_ready}" ]; then
				pkill udhcpc
				sleep 1
				udhcpc -i wlan0 -f -S -R &
			fi
			sleep 10
		fi
	else
		udhcpc -i eth0 -f &
	fi
done

exit 0
