#!/bin/bash

# Shared x1plus functions for bash scripts

x1p_sn() {
    # Used to get the device serial number from cmdline
    echo $(cat /proc/cmdline | xargs -n1 | grep "bbl_serial=" | sed "s|bbl_serial=||")
}

x1p_get_setting() {
    # Used to check if an x1plus setting is set
    # $1 - required - json setting name (jq format, so "test.flag" for nested stuff)
    # $2 - optional - flag file check path (legacy, do not use for new settings!)
    # response: exit code 1 on false, exit code 1 on true

    SETTING_JSON_FILE="/mnt/sdcard/x1plus/printers/$(x1p_sn)/settings.json"
    LEGACY_FLAGFILE_PATH="/mnt/sdcard/x1plus/printers/$(x1p_sn)/"

    # First try the settings JSON file if it exists (this is always source of truth if it exists)
    if [ -f "${SETTING_JSON_FILE}" ]; then
        # Read our JSON file, default to false if unset
        SETTING_VALUE=$(jq ".\"${1}\" // false" ${SETTING_JSON_FILE})
        if [ "${SETTING_VALUE}" == "true" ]; then
            return 0
        elif [ "${SETTING_VALUE}" == "false" ]; then
            return 1
        else
            # Currently unused, BUT if you request something that's not a boolean, just pass it through and exit 0
            echo "${SETTING_VALUE}"
            return 0
        fi
    elif [ -n "${2}" ]; then
        # Second, try the legacy file if passed through, used with OG init.d scripts
        if [ -f "${LEGACY_FLAGFILE_PATH}${2}" ]; then
            return 0
        fi
        # No flag file, return false
        return 1
    fi

    # We should never get here, if we do, assume false cuz what else can we do? :/
    return 1
}