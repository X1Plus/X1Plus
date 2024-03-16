#!/bin/sh

source /usr/bin/flash_test.sh
source /usr/bin/aging_test_lib.sh
source /usr/bin/log_crypto.sh
DEVICE_ID=0

SYSLOG_SRC_PATH="/userdata/log"
EXPORT_LOG=$SYSLOG_SRC_PATH/"log_export.log"
EXPORT_DEST_PATH="/mnt/sdcard/x1plus/export/"
EXPORT_SIZE_NODE="/tmp/export_size"
EXPORT_DONE_NODE="/tmp/export_done"
GCODE_FILE_PATH="/userdata/Metadata"

HANDLE_LOG_NODE="/tmp/handle_log"

function _start() {
    touch $HANDLE_LOG_NODE
    sleep 5 # wait log monitor zip finished
    mkdir -p $EXPORT_DEST_PATH
    rm -rf $EXPORT_DEST_PATH/*
    rm -rf /userdata/log/tutk*
}

function _exit() {
    rm -f $HANDLE_LOG_NODE
    exit 1
}

function get_export_size() {
    echo `du -lh $SYSLOG_SRC_PATH --max-depth=1 -b | tail -n 1 | awk '{print $1}'`
}

function get_dev_id() {
    # Use Bambu Device SN, NOT SoC SN from /proc/device-tree/serial-number
    DEVICE_ID=$(cat /proc/cmdline | xargs -n1 | grep "bbl_serial=" | sed "s|bbl_serial=||")
}

function main() {
    if [ "`sdcard_is_exist`" = "1" ]; then
        if [ `need_crypt` == 1 ]; then
            _start
            password=`get_password`
            salt=`get_salt`
            timestamp=$(date +%Y%m%d%H%M%S)
            get_dev_id
            echo `get_export_size` > $EXPORT_SIZE_NODE
            echo "total export size is `cat $EXPORT_SIZE_NODE` bytes"

            tar -cvf - $GCODE_FILE_PATH | gzip | dd of=/userdata/log/gcode.tar.gz > /dev/null 2>&1
            if [ $? != 0 ]; then
                echo "export gcode failed"
            fi
			 #tar -cvf - /userdata/log | openssl enc -e -aes-128-cbc -K $password -iv $salt | dd of=$EXPORT_DEST_PATH/${DEVICE_ID}_all_${timestamp}_enc.tar > /dev/null 2>&1
             tar -cvf $EXPORT_DEST_PATH/${DEVICE_ID}_all_${timestamp}.tar /userdata/log > /dev/null 2>&1
            if [ $? != 0 ]; then
                echo "export datalog failed"
                _exit
            else
                echo "export all datalog success"
                touch $EXPORT_DONE_NODE
            fi
        else
            echo "no production printer, do not export logs"
        fi

    else
        echo "no sdcard exsit"
        _exit
    fi
}

rm -rf $EXPORT_LOG $EXPORT_DONE_NODE
exec 1>>$EXPORT_LOG 2>&1

main
rm -f $HANDLE_LOG_NODE
sync

exit 0
