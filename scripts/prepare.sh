#!/bin/sh

ROOT=""
DTSFILE=panel_b.dts

O=`getopt -n 'prepare.sh' -l dts:,root: -- d:r: "$@"` || exit 1
eval set -- "$O"
while true; do
	case "$1" in
	-d|--dts) DTSFILE="$2"; shift 2;;
	-r|--root) ROOT="$2"; shift 2;;
	--) shift; break;;
	*) echo "error: invalid argument $1"; exit 1;;
	esac
done

echo "Hi!  I'll prepare the cannon for you!"
echo

DTSMODEL="$(grep 'model =' $DTSFILE | cut -d'"' -f2)" #'
DTMODEL="$(cat /proc/device-tree/model)"
if [ "$DTSMODEL" != "$DTMODEL" ] ; then
	echo "This device tree does not appear to match the booted printer model."
	echo "  Script device tree: $DTSMODEL"
	echo "  Running printer image: $DTMODEL"
	echo "Cowardly refusing to boot."
	exit 1
fi

if grep kexec /proc/cmdline >/dev/null; then
	echo "For some reason, you cannot kexec from a printer that has already kexec'ed once."
	echo "Reboot and try again.  (Soft-reboot is OK, no need to hit the power switch.)"
	exit 1
fi

io -4 -w 0xfe010050 0x11001100 # turn the UART back on
CMDLINE="storagemedia=emmc androidboot.storagemedia=emmc androidboot.mode=normal boot_reason=cold mp_state=production fuse.programmed=1"
CMDLINE="$CMDLINE rootwait earlycon=uart8250,mmio32,0xff570000 console=ttyFIQ0 rootfstype=ext4 snd_aloop.index=7 from_kexec=hellyes initcall_debug ignore_loglevel"
if [ ! -z "$ROOT" ]; then
	CMDLINE="$CMDLINE root=$ROOT"
fi

for i in `cat /proc/cmdline`; do
	# grab a rootfs
	case "$i" in
	root=*)
		if [ -z "$ROOT" ]; then
			echo "booting from on-printer root, $i"
			CMDLINE="$CMDLINE $i"
		fi;;
	androidboot.slot_suffix=*)
		CMDLINE="$CMDLINE $i";;
	esac
done
(sed -e "s#XXXBOOTARGSXXX#$CMDLINE#" -e "s/XXXSERIALNUMBERXXX/$(cat /proc/device-tree/serial-number)/" $DTSFILE) | ./dtc -O dtb -o boot.dtb 2>/dev/null
KALLSYMS=$(grep 'T kallsyms_lookup_name' /proc/kallsyms | cut -d' ' -f1)

set -x
insmod kexec_mod_arm.ko ptr_kallsyms_lookup_name=0x$KALLSYMS
insmod kexec_mod.ko ptr_kallsyms_lookup_name=0x$KALLSYMS
./kexec -l --command-line="$CMDLINE" --dtb=boot.dtb kernel
set +x

echo
echo 'Ready for blastoff!  Come on, hop into the cannon!'
echo
echo "When ready, run ./kexec -f -e"
