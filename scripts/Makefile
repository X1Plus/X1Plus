-include ../localconfig.mk

TOOLCHAIN ?= arm-linux-gnueabihf-
TARGET_CC ?= $(TOOLCHAIN)gcc
LDFLAGS = -ldl
CXXFLAGS = -fPIC -std=c++11 -I/usr/include
CFLAGS = -fPIC -s
MODULES := getkey

all: $(MODULES)

clean:
	@rm -rfv $(MODULES)
	@rm -rf printer_ui

getkey: getkey.c
	$(TARGET_CC) -o $@ $< $(CFLAGS) $(LDFLAGS)
