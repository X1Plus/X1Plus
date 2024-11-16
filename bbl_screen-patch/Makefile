-include ../localconfig.mk

FIRMWARE ?= $(shell jq -r .base.ap ../installer/info.json)
QT5_INCL_PATH ?= /usr/include/x86_64-linux-gnu/qt5/
TOOLCHAIN ?= arm-linux-gnueabihf-
TARGET_CC ?= $(TOOLCHAIN)gcc
TARGET_CXX ?= $(TOOLCHAIN)g++
LDFLAGS = -shared -ldl
CXXFLAGS = -fPIC -std=c++11 -Ivendor -O3 -mcpu=cortex-a7 -Wno-psabi # yes, -O3 actually helps here with the VNC shenanigans
CFLAGS = -fPIC -Ivendor -O3 -mcpu=cortex-a7 # yes, -O3 actually helps here with the VNC shenanigans
MODULES := kexec_ui.so printer_ui printer_ui.so printer_ui.so.xdelta uncurl.so evdev_fix.so base.ts workaround_ifaddrs.so device_gate_shim.so netService_shim.so forward_shim.so

.DELETE_ON_ERROR:
.SUFFIXES:
.PHONY: all clean clean-all deploy
.INTERMEDIATE: bbl_screen printer_ui.so
.SECONDEXPANSION:

all: $(MODULES)

clean:
	@rm -rfv $(MODULES)
	@rm -rf printer_ui

clean-all: clean
	@rm -rfv bbl_screen
	@rm -rf printer_ui-orig

bbl_screen: ../firmwares/$(FIRMWARE).squashfs
	rdsquashfs -c usr/bin/bbl_screen $< > bbl_screen

printer_ui.so.xdelta: bbl_screen printer_ui.so
	xdelta3 -vv -f -e -s bbl_screen printer_ui.so printer_ui.so.xdelta

printer_ui-orig: bbl_screen
	@rm -rfv $@
	./extract_qrc.py $< $@

ifneq ("$(wildcard printer_ui-orig/printerui/*.qm)","")
.PHONY: need_unpack_qm

need_unpack_qm:

printer_ui-orig: need_unpack_qm
endif

ifeq ("$(NO_AUTO_PATCH)","")
printer_ui: printer_ui-orig $$(shell find patches)
	rsync -a --delete $@-orig/ $@/
	./patcher.py -a
else
.PHONY: patch_printer_ui
patch_printer_ui:
	rsync -a --delete printer_ui-orig/ printer_ui/
	./patcher.py -a

printer_ui: printer_ui-orig $$(shell find patches)
	@echo "bbl_screen-patch/Makefile: I *would* overwrite printer_ui right now for dependency reasons, but you asked me not to by setting NO_AUTO_PATCH in your localconfig.mk, so I will not.  If you want to run the patcher and blow away the printer_ui directory, do a 'make patch_printer_ui'."
endif

base.ts: printer_ui.so kexec_ui.so
	@rm -f base.ts
	lupdate -locations absolute printer_ui-orig/printerui/app_en.ts printer_ui kexec_ui -ts base.ts

%.so: %.c
	$(TARGET_CC) -o $@ $< $(CFLAGS) $(LDFLAGS)

%.so: %.cpp
	$(TARGET_CC) -o $@ $< $(CXXFLAGS) $(LDFLAGS)

device_gate_shim.so: workaround_ifaddrs.c link_is_up.cpp mqtt_reroute.cpp
	$(TARGET_CXX) -o $@ workaround_ifaddrs.c link_is_up.cpp mqtt_reroute.cpp $(CXXFLAGS) $(LDFLAGS)

forward_shim.so: forward_shim.c
	$(TARGET_CXX) -o $@ forward_shim.c $(CXXFLAGS) $(LDFLAGS) ../prebuilt/libdbus-1.so

kexec_ui.so: kexec_ui.ui.o interpose.cpp interpose.moc.h
	$(TARGET_CC) -o $@ $< interpose.cpp workaround_ifaddrs.c $(CXXFLAGS) $(LDFLAGS) -I $(QT5_INCL_PATH)

printer_ui.so: printer_ui.ui.o interpose.cpp interpose_vnc.cpp interpose.moc.h
	$(TARGET_CC) -o $@ $< interpose.cpp interpose_vnc.cpp workaround_ifaddrs.c $(CXXFLAGS) $(LDFLAGS) -I $(QT5_INCL_PATH) -DHAS_DBUS -DHAS_VNC ../prebuilt/libvncserver.so.1

%.moc.h: %.cpp
	moc -I $(QT5_INCL_PATH) $< -o $@

%.ui.o: %.ui.cpp
	$(TARGET_CC) -c -o $@ $< $(CXXFLAGS) -I $(QT5_INCL_PATH)

%.qm: %.ts
	lconvert $< -o $@

%.ui.cpp: %/root.qrc $$(addprefix $$(*F)/,$$(shell grep file $$(*F)/root.qrc | sed -e 's/.*>\(.*\)<.*/\1/'))
	cd $(dir $<); qmllint $$(grep file $(notdir $<) | sed -e 's/.*>\(.*\)<.*/\1/' | grep 'qml$$\|js$$')
	cd $(dir $<); rcc $(notdir $<) --format-version=2 | sed 's/static const unsigned char qt_resource_name/extern const unsigned char qt_resource_name/' > $(CURDIR)/$@
	rm -f $(dir $<)/printerui/*.qm

# sigh
kexec_ui/root.qrc: printer_ui
