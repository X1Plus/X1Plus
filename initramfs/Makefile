-include ../localconfig.mk

FIRMWARE ?= $(shell jq -r .base.ap ../installer/info.json)

.DELETE_ON_ERROR:
.SUFFIXES:
.PHONY: all clean clean-all
.SECONDEXPANSION:

all: initramfs

clean:
	@rm -fv initramfs

clean-all: clean
	@rm -fv $(addprefix .,$(shell grep -E '^file /.+/' initramfs.pack | cut -d ' ' -f 2))
	@find . -type d -depth -delete 2>/dev/null

Makefile ../localconfig.mk init stage2 signon initramfs.pack ter-i32b.psf bootlogo.dat.gz :: ;

initramfs: initramfs.pack $(addprefix ./,$(shell grep -E '^file /' initramfs.pack | cut -d ' ' -f 3))
	../scripts/gen_init_cpio $< | gzip -9 > initramfs

./%:: ../firmwares/$(FIRMWARE).squashfs
	@mkdir -p $(@D)
	rdsquashfs -c $@ $< > $@
