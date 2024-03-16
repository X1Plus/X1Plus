#!/bin/sh

# This script is used to enable or disable system debug interface
# such as: adb, rndis, uart, and so on.
#
# Note: This script need to reboot system to make configuration actived.
#
# usage:
#   sec_dbg_ctrl.sh [ en | dis ] [reboot]
#
# return:
#   success: 0x0
#   failure: 0x1

# set workspace path
CMD=`realpath $0`
WORKSPACE=`dirname $CMD`

UART_SCRIPT=/usr/bin/sec_dbg_ctrl_uart.sh
USB_SCRIPT=/usr/bin/sec_dbg_ctrl_usb.sh
SSH_SCRIPT=/usr/bin/sec_dbg_ctrl_ssh.sh

show_help() {
    echo "Usage: $0"
    echo "$0 en | dis"
    echo "   en : enable secure debug, include debug uart, adb & rndis."
    echo "   dis: disable secure debug, include debug uart, adb & rndis."
}

if [ "en"x = "$1"x -o "dis"x = "$1"x ]; then

    # 1. debug uart
    echo "****************************************"
    echo "1. Proc debug uart input & output config"
    echo "****************************************"
    #$UART_SCRIPT $1

    # 2. usb related function
    echo "****************************************"
    echo "2. Proc usb related (adb & rndis) config"
    echo "****************************************"
    $USB_SCRIPT en

    # 3. ssh remote login
    echo "****************************************"
    echo "3. Proc ssh login root account config   "
    echo "****************************************"
    #$SSH_SCRIPT $1

else
    show_help
    echo "Please refer to usage, input right command, thanks."
    exit 1
fi

if [ x"reboot" = x"$2" ]; then
    echo "****************************************"
    echo "3. reboot system after 5 seconds ...    "
    echo "****************************************"
    reboot -d 5
fi
