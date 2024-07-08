#!/bin/sh
echo "================"
echo "dmesg"
echo "================"
dmesg
echo "================"
echo "lsmod"
echo "================"
lsmod
echo "================"
echo "/config/wifi/config.txt"
echo "================"
cat /config/wifi/config.txt
echo "================"
echo "wpa_supplicant.conf"
echo "================"
sed -e 's/psk=\".*\"/psk=\"######\"/g' -e 's/ssid=\".*\"/ssid=\"######\"/g' /userdata/cfg/wpa_supplicant.conf
echo "================"
echo "iw list"
echo "================"
iw list
echo "================"
echo "iw reg get"
echo "================"
iw reg get
echo "================"
echo "iw dev"
echo "================"
iw dev | sed -e 's/ssid .*/ssid ######/g'
echo "================"
echo "ifconfig"
echo "================"
ifconfig | sed -e 's/inet addr.*/inet addr:#.#.#.#  Bcast:#.#.#.#  Mask:#.#.#.#/g'
