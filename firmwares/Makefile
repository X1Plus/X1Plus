FIRMWARE ?= allknown

.DELETE_ON_ERROR:
.SUFFIXES:
.PHONY: all allknown clean clean-all
.SECONDEXPANSION:

all: $(FIRMWARE).squashfs

allknown: 00.00.19.15.squashfs 00.00.22.14.squashfs

clean:
	@rm -fv *.squashfs

clean-all: clean
	@rm -fv *.img.zip.sig

define fetchimage =
	wget -q -N -c "https://public-cdn.bambulab.com/upgrade/device/BL-P001/$(1)/product/$(2)$(3)"
	../scripts/repack_update.py $(3) $(4)
endef

define fetchimage_fullurl =
	wget -q -N -c "$(1)/$(2)"
	../scripts/repack_update.py $(2) $(3)
endef

00.00.19.15.squashfs:
	$(call fetchimage,01.05.01.00,,update-v00.00.19.15-20230423131316_product.img.zip.sig,$@)

00.00.22.14.squashfs:
	$(call fetchimage,01.06.00.00,,update-v00.00.22.14-20230728202148_product.img.zip.sig,$@)

00.00.24.13.squashfs:
	$(call fetchimage,01.06.05.01,,update-v00.00.24.13-20230922180718_product.img.zip.sig,$@)

00.00.28.14.squashfs:
	$(call fetchimage,01.06.06.00,13a3c14595/,update-v00.00.28.14-20231113183951_product.img.zip.sig,$@)

00.00.28.21.squashfs:
	$(call fetchimage,01.06.06.03,7ffc1bcd4c/,update-v00.00.28.21-20231123141858_product.img.zip.sig,$@)

00.00.28.36.squashfs:
	$(call fetchimage,01.07.00.00,3b63468a6f/,update-v00.00.28.36-20231207153519_product.img.zip.sig,$@)

00.00.28.44.squashfs:
	$(call fetchimage,01.07.01.00,c6c10c944a/,update-v00.00.28.44-20231222033833_product.img.zip.sig,$@)

00.00.28.55.squashfs:
	$(call fetchimage,01.07.02.00,62201b7e2c/,update-v00.00.28.55-20240112183717_product.img.zip.sig,$@)

00.00.28.59.squashfs:
	$(call fetchimage,01.07.03.00,1916138d2c/,update-v00.00.28.59-20240330174859_product.img.zip.sig,$@)

00.00.32.17.squashfs:
	$(call fetchimage,01.07.03.05,79a426f63e/,update-v00.00.32.17-20240409222723_product.img.zip.sig,$@)

00.00.32.18.squashfs:
	$(call fetchimage_fullurl,https://public-cdn.bblmw.com/upgrade/device/BL-P001/01.08.00.00/product/45ea644d25,update-v00.00.32.18-20240422102213_product.img.zip.sig,$@)
