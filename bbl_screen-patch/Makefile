-include ../localconfig.mk

FIRMWARE ?= $(shell jq -r .base.ap ../installer/info.json)
QT5_INCL_PATH ?= /usr/include/x86_64-linux-gnu/qt5/
TOOLCHAIN ?= arm-linux-gnueabihf-
TARGET_CC ?= $(TOOLCHAIN)gcc
LDFLAGS = -shared -ldl #-nolibc # Guh.  Otherwise we end up linking against libc and getting a versioned symbol of dlsym...
CXXFLAGS = -fPIC -std=c++11
CFLAGS = -fPIC
MODULES := kexec_ui.so printer_ui printer_ui.so printer_ui.so.xdelta uncurl.so evdev_fix.so

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
	cd $@/printerui; for qm in *.qm; do lconvert $$qm -o `basename $$qm .qm`.ts; done; rm *.qm

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

uncurl.so: uncurl.c
	$(TARGET_CC) -o $@ $< $(CFLAGS) $(LDFLAGS)

evdev_fix.so: evdev_fix.c
	$(TARGET_CC) -o $@ $< $(CFLAGS) $(LDFLAGS)

%.so: %.ui.o interpose.cpp interpose.moc.h
	$(TARGET_CC) -o $@ $< interpose.cpp $(CXXFLAGS) $(LDFLAGS) -I $(QT5_INCL_PATH)

%.moc.h: %.cpp
	moc -I $(QT5_INCL_PATH) $< -o $@

%.ui.o: %.ui.cpp
	$(TARGET_CC) -c -o $@ $< $(CXXFLAGS) -I $(QT5_INCL_PATH)

%.qm: %.ts
	@lconvert $< -o $@

%.ui.cpp: %/root.qrc $$(addprefix $$(*F)/,$$(shell grep file $$(*F)/root.qrc | sed -e 's/.*>\(.*\)<.*/\1/'))
	cd $(dir $<); rcc $(notdir $<) --format-version=2 | sed 's/static const unsigned char qt_resource_name/extern const unsigned char qt_resource_name/' > $(CURDIR)/$@
	cd $(dir $<)/printerui; rm *.qm || true

