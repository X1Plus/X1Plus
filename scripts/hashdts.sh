#!/bin/bash
(/usr/bin/env printf '%s\x00' "$(cat $1 | grep model | cut -d'"' -f2)"; cat $1 | grep init-sequence | sed -e 's/.*\[\(.*\)\].*/\1/' | xxd -r -p) | md5sum | cut -d' ' -f1
