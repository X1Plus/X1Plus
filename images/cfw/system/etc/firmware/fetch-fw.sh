# update firmware for ap6212 (rebranded bcm43430)

#firmware 7.45.98.125
wget https://github.com/murata-wireless/cyw-fmac-fw/raw/master/cyfmac43430-sdio.bin -O fw_bcm43438a1.bin
#wget https://git.kernel.org/pub/scm/linux/kernel/git/firmware/linux-firmware.git/plain/cypress/cyfmac43430-sdio.bin
#regulatory db
wget https://git.kernel.org/pub/scm/linux/kernel/git/firmware/linux-firmware.git/plain/cypress/cyfmac43430-sdio.clm_blob -O clm_bcm43438a1.blob
