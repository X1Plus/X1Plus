TOOLCHAIN ?= arm-linux-gnueabihf-
TARGET_CC ?= $(TOOLCHAIN)gcc
LDFLAGS =
CXXFLAGS = -fPIC -std=c++11 -I/usr/include
CFLAGS = -fPIC -s
MODULES := bootlogo.dat.gz

all: $(MODULES)

clean:
	@rm -rfv $(MODULES)

bootlogo.dat: bootlogo.png
	convert bootlogo.png bgra:bootlogo.dat

bootlogo.dat.gz: bootlogo.dat
	gzip bootlogo.dat
