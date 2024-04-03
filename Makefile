-include localconfig.mk
export UPDATE_KEY_MATERIAL

REQUIRED_X1PLUS_DOCKER_ENV_VERSION := 3

ifeq "$(HOME)" "/home/docker"
ifneq "$(X1PLUS_DOCKER_ENV_VERSION)" "$(REQUIRED_X1PLUS_DOCKER_ENV_VERSION)"
$(error You are building in Docker, but your Docker environment does not match the requirements of the checked out branch.  Rebuild your Docker environment with `docker build -t x1plus scripts/docker/` and then try again)
endif
endif

# Always update this.
$(shell scripts/mkinfojson.py >&2)
ifneq "$(.SHELLSTATUS)" "0"
$(error Failed to build info.json -- check mkinfojson.py output.)
endif

FIRMWARE ?= $(shell jq -r .base.ap installer/info.json)
CFWVERSION ?= $(shell jq -r .cfwVersion installer/info.json)
MODULES := initramfs bbl_screen-patch images

.DELETE_ON_ERROR:
.SUFFIXES:
.SECONDEXPANSION:
.PHONY: all clean clean-all cfw firmwares $(MODULES) $(addprefix clean-,$(MODULES)) $(addprefix clean-all-,$(MODULES)) modules scripts

define make =
	$(MAKE) -C $(1) $(MAKEFLAGS) FIRMWARE=$(FIRMWARE) $(2)
endef

all: $(CFWVERSION).x1p
	make -C installer-clientside/stage1

# needs:
#   prebuilts: gensquashfs, rdsquashfs, xdelta3, libdds_intf.so, dtc, python3.tar.gz
#   kernel: prebuilts/kernel, initramfs/initramfs
#   internal-fs/opt/kexec/{boot,check_kexec}
#   internal-fs/etc/init.d/S75kexec
#   bbl_screen-patch: kexec_ui.so, printer_ui.so.xdelta, uncurl.so
#   installer/*
#   images/cfw.squashfs
$(CFWVERSION).x1p: images initramfs bbl_screen-patch
	scripts/mkx1p.py $@

bbl_screen-patch: firmwares

# pulls in uncurl
images: bbl_screen-patch firmwares

modules: $(MODULES)
$(MODULES) : firmwares
firmwares scripts $(MODULES) : $$(@D)/Makefile
	$(call make,$@,all)

clean: $$(addprefix clean-,$(MODULES) firmwares)
$(addprefix clean-,$(MODULES) firmwares): clean-%:
	$(call make,$*,clean)

clean-all: $$(addprefix clean-all-,$(MODULES) firmwares)
$(addprefix clean-all-,$(MODULES) firmwares): clean-all-%:
	$(call make,$*,clean-all)

cfw: initramfs images
