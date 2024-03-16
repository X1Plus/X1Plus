FIRMWARE ?= $(shell jq -r .base.ap ../installer/info.json)

.DELETE_ON_ERROR:
.SUFFIXES:
.PHONY: all clean clean-all
.SECONDEXPANSION:

all: $(addsuffix .squashfs, $(notdir $(abspath $(wildcard */))))

clean:
	@rm -fv *.squashfs

clean-all: clean

EPOCH := $(shell date +%s)

%.squashfs :: %.pack cfw/opt/python/ .DUMMY
	gensquashfs -d mtime=$(EPOCH) -k -c xz -X dictsize=8192,level=4,extreme,armthumb -F $(*F).pack -D $(*F) -f $@ | tail -n 14 | head -n 3

.DUMMY:

cfw/opt/python/: ../prebuilt/python3.tar.gz
	rm -rf $@
	mkdir -p $@
	tar xzf $< -C $@
	touch -r $< $@
