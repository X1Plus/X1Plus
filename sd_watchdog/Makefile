-include ../localconfig.mk

TOOLCHAIN ?= arm-linux-gnueabihf-
TARGET_CC ?= $(TOOLCHAIN)gcc
LDFLAGS =
CXXFLAGS = -fPIC -std=c++11 -I/usr/include
CFLAGS = -fPIC -s
MODULES := sd_watchdog

all: $(MODULES)

clean:
	@rm -rfv $(MODULES)
	@rm -rf printer_ui

sd_watchdog: sd_watchdog.c
	$(TARGET_CC) -o $@ $< $(CFLAGS) $(LDFLAGS)

caca: caca.c
	$(TARGET_CC) -o $@ $< $(CFLAGS) $(LDFLAGS)
