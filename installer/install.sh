#!/bin/sh

# ... which had better be /userdata/x1plus
cd $(dirname $0)

# Ensure we enable UART before we start the installer
io -4 -w 0xfe010050 0x11001100

# Launch installer
PYTHONUNBUFFERED=1 exec bin/python3 install.py 2>&1 | tee /mnt/sdcard/x1plus_installer_log.txt | tee /dev/ttyFIQ0