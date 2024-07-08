#!/bin/bash

# before anything else: turn the UART on
io -4 -w 0xfe010050 0x11001100

exec 2>/dev/ttyFIQ0
/sbin/getty -L -n -l /bin/bash ttyFIQ0 0 vt100 &

# spin up ADB
echo "starting up adbd..." >&2
start_usb.sh adb
killall start_rknn.sh

# turn the WiFi on 
echo 1 > /sys/class/rfkill/rfkill1/state
/usr/bin/netService >&2 &
disown -a

N=0
while [ -z "$ip_address" -a $N -lt 15 ]; do
	ip_address=`wpa_cli -i wlan0 status | grep ^ip_address= | cut -d= -f2`
	ssid=`wpa_cli -i wlan0 status | grep ^ssid= | cut -d= -f2`
	N=$(($N+1))
	sleep 1
done

if [ -z "$ip_address" ]; then
	echo 'no IP address; giving up' >&2
	echo '{}' > /tmp/emergency_console.json
	exit 0
fi

# set up a sshd

# generate a setup key
PW=$(dd if=/dev/urandom bs=8 count=1 2>/dev/null | xxd -p -c 8)

# create a fake user account.  we don't want to write to /, so we do this
# annoying shenanigan
mkdir /tmp/fakeroot
mkdir /tmp/fakeroot/lib
mkdir /tmp/fakeroot/etc
cp /lib/libc.so.6 /lib/ld-linux-armhf.so.3 /tmp/fakeroot/lib/
cp `which passwd` /tmp/fakeroot/
cp /etc/passwd /tmp/fakeroot/etc
cp /etc/shadow /tmp/fakeroot/etc
echo x1plus:x:0:0:x1plus:/root:/bin/sh >> /tmp/fakeroot/etc/passwd
echo x1plus:*:19555:0:99999:7::: >> /tmp/fakeroot/etc/shadow
(echo $PW; echo $PW) | chroot /tmp/fakeroot /passwd x1plus >&2
mount -o bind /tmp/fakeroot/etc/passwd /etc/passwd
mount -o bind /tmp/fakeroot/etc/shadow /etc/shadow

dropbearkey -t ecdsa -f /tmp/dropbear_hostkey >&2
dropbear -r /tmp/dropbear_hostkey -p 22 >&2

echo '{"wifiNetwork":"'$ssid'","ip":"'$ip_address'","sshPassword":"'$PW'"}' > /tmp/emergency_console.json

