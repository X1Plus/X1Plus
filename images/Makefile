FIRMWARE ?= $(shell jq -r .base.ap ../installer/info.json)

.DELETE_ON_ERROR:
.SUFFIXES:
.PHONY: all clean clean-all
.SECONDEXPANSION:

all: cfw.squashfs

clean:
	@rm -fv *.squashfs
	@rm -rfv cfw/opt/python

clean-all: clean

%.squashfs :: %.py .DUMMY
	python3 $< | tar2sqfs -f $@ | tail -n 14 | head -n 3

.DUMMY:
