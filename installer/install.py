# Printer-side installation script
#
# Copyright (c) 2023 - 2024 Joshua Wise, and the X1Plus authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
import hashlib
import os
import struct
import ctypes as c
from zipfile import *
import ext4
import tempfile
import shutil
import dds
import requests
import json
import select
import time
import filecmp
import glob
import re
import subprocess

# XXX: have config for filesystem size
installer_path = os.path.dirname(__file__) # will get cleaned out on boot
INFO = json.load(open(f"{installer_path}/info.json"))
boot_path = "/mnt/sdcard/x1plus"
fs_size = 1*1024*1024*1024 # 1GB
basefw_squashfs = INFO["base"]["squashfsName"]
basefw_squashfs_md5 = INFO["base"]["squashfsMd5"]
basefw_update_url = INFO["base"]["updateUrl"]
basefw_update = os.path.basename(basefw_update_url)
basefw_update_md5 = INFO["base"]["updateMd5"]
basefw_mtime = INFO["base"]["mtime"]
cfw_version = INFO["cfwVersion"]
cfw_squashfs = f"{cfw_version}.squashfs"
demand_free_space = fs_size + 1 * 1024 * 1024 * 1024
# latest_safe_bblap = "00.00.28.55" # 1.07.02.00
latest_safe_bblap = "00.00.30.73" # Firmware R - "1.06.06.58" aka 1.07.02.00+R

dds_rx_queue = dds.subscribe("device/request/upgrade")
dds_tx_pub = dds.publisher("device/report/upgrade")

print("waiting for DDS to spin up...")
time.sleep(3)
print("ok, that oughta be good enough")
def report_progress(what):
    print(f"[...] {what}")
    dds_tx_pub(json.dumps({ 'command': 'x1plus', 'progress': what }))

def report_interim_progress(what):
    print(f"[...] ... {what} ...")
    dds_tx_pub(json.dumps({ 'command': 'x1plus', 'progress_interim': what }))

def report_success():
    print("[+]")
    dds_tx_pub(json.dumps({ 'command': 'x1plus', 'progress_success': True }))

def report_failure(why, e = None):
    print(f"... failed ({why})")
    dds_tx_pub(json.dumps({ 'command': 'x1plus', 'progress_failure': why }))
    if e is not None:
        dds.shutdown()
        raise e
    dds.shutdown()
    sys.exit(1)

def report_complete():
    dds_tx_pub(json.dumps({ 'command': 'x1plus', 'progress_complete': True }))
    print("[+] complete")
    dds.shutdown()
    sys.exit(0)

def ask_permission(what):
    # flush the input queue
    while not dds_rx_queue.empty():
        dds_rx_queue.get()

    dds_tx_pub(json.dumps({ 'command': 'x1plus', 'prompt_yesno': what }))
    print(f"[?] {what}")
    print("y/n")
    
    # This is sort of a cheesy way to impedance-match these two inputs, but
    # it is what it is.
    while True:
        if sys.stdin.isatty():
            # otherwise there is probably no stdin
            if select.select([sys.stdin, ], [], [], 0.1)[0]:
                return sys.stdin.readline() == 'y\n'
        else:
            time.sleep(0.1)

        try:
            qv = dds_rx_queue.get_nowait()
            qv = json.loads(qv)
            if qv['command'] == 'x1plus' and 'yesno' in qv:
                print(f"DDS chose {qv['yesno']}")
                return qv['yesno'] == True
        except:
            pass

def device_tree_compute_key():
    dtkey = b""

    print("\nfirmware versions")

    for filename in glob.glob("/config/version/*"):
        print("[%s] [%s]" % ( filename, open(filename, "r").read().strip() ) )

    print("\ndevicetree")

    for root, dirs, files in os.walk('/proc/device-tree/'):
        for file in files:
            print(os.path.join(root, file))

    try:
        with open("/proc/device-tree/model", "rb") as f:
            dtkey += f.read()
    except Exception as e:
        print(e)
        dtkey += b"no device tree model"

    print(f"device-tree model [{dtkey}]")

    try:
        for panel in sorted(glob.glob("/proc/device-tree/dsi@ffb30000/panel@*")):
            print(f"panel [{panel}]")
            try:
                status = open(f"{panel}/status", "r").read()
                print(f"status [{status}]")
            except:
                # older oem firmware devicetrees have no status
                status = "okay"
                print("no status file in devicetree")
            if status[0:4] == "okay":
                dtkey += open(f"{panel}/panel-init-sequence", "rb").read()
                break
    except Exception as e:
        print(e)
        dtkey += b"no panel init sequence"

    print(f"panel-init-sequence [{dtkey}]")

    return hashlib.md5(dtkey).hexdigest()

def exists_with_md5(path, md5):
    if not os.path.isfile(path):
        return False

    m = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b''):
            m.update(chunk)
    
    return m.hexdigest() == md5

def system_is_sd_boot():
    with open("/proc/mounts", "r") as f:
        for m in f.readlines():
            src,dest,fstype,params,_,_ = m.strip().split(' ')
            if dest == '/' and fstype == 'overlay':
                return True
    return False

def dump_rootfs(f, ofs, dir):
    packs = ""

    def traverse_ino(path, ino):
        nonlocal packs
        if ino.is_dir:
            packs += f"dir {path}/ 0{ino.inode.i_mode & 0xFFF:o} {ino.inode.i_uid_lo} {ino.inode.i_gid_lo}\n"
            for fn, iidx, ftype in ino.open_dir():
                if fn == "." or fn == "..":
                    continue
                if iidx == 0:
                    continue
                traverse_ino(path + "/" + fn, vol.get_inode(iidx))
        elif (ino.inode.i_mode & 0xF000) == ext4.ext4_inode.S_IFIFO:
            raise ValueError("unsupported FIFO")
        elif (ino.inode.i_mode & 0xF000) == ext4.ext4_inode.S_IFCHR:
            packs += f"nod {path} 0{ino.inode.i_mode & 0xFFF:o} {ino.inode.i_uid_lo} {ino.inode.i_gid_lo} c {ino.inode.i_block[0] >> 8} {ino.inode.i_block[0] & 0xFF}\n"
        elif (ino.inode.i_mode & 0xF000) == ext4.ext4_inode.S_IFBLK:
            raise ValueError("unsupported IFBLK")
        elif (ino.inode.i_mode & 0xF000) == ext4.ext4_inode.S_IFLNK:
            packs += f"slink {path} 0{ino.inode.i_mode & 0xFFF:o} {ino.inode.i_uid_lo} {ino.inode.i_gid_lo} {ino.open_read().read().decode()}\n"
        elif (ino.inode.i_mode & 0xF000) == ext4.ext4_inode.S_IFREG:
            fn = f"ino_{ino.inode_idx}"
            with open(f"{dir}/{fn}", "wb") as f:
                f.write(ino.open_read().read())
            packs += f"file {path} 0{ino.inode.i_mode & 0xFFF:o} {ino.inode.i_uid_lo} {ino.inode.i_gid_lo} {fn}\n"
        else:
            raise ValueError(f"unsupported file {path} {ino.inode.i_mode:o}")

    vol = ext4.Volume(f, offset = ofs)
    traverse_ino("", vol.root)
    return packs

def validate_sd():
    found_sdcard = False
    for dev in glob.glob("/dev/mmcblk2p*"):
        if dev != "/dev/mmcblk2p1":
            report_failure(f"The SD card's partition scheme is unsupported. Format the SD card from the on-printer menu, then restart the installer.")
    with open("/proc/mounts", "r") as f:
        mounts = f.read().strip().split('\n')
    for m in mounts:
        dev, pt, fs = m.split(' ')[:3]
        if pt == "/mnt/sdcard":
            if dev != "/dev/mmcblk2p1" or fs != "vfat":
                report_failure(f"The SD card's filesystem is unsupported. Format the SD card from the on-printer menu, then restart the installer.")
            found_sdcard = True
    if not found_sdcard:
        report_failure(f"SD card was not mounted in the expected location. If the SD card is inserted, please file a bug.")

validate_sd()

df = shutil.disk_usage("/mnt/sdcard")
if df.free < demand_free_space:
    report_failure(f"The SD card does not have enough free space. Make sure that at least {demand_free_space//(1024*1024)} MB are available.")

if not os.path.isfile("/sys/devices/virtual/misc/loop-control/dev"):
    if os.system(f"insmod {installer_path}/loop.ko") != 0:
        report_failure("Failed to load loopback kernel module.")

report_success()

if os.path.isfile("/oem/device/sn"):
    sn = open("/oem/device/sn", "r").read()
else:
    if os.system("bbl_3dpsn 2>/dev/null > /tmp/.bambu_sn") != 0:
        report_failure("Failed to get device serial number from bbl_3dpsn. Are you on the right BBL firmware version?")
    sn = open("/tmp/.bambu_sn", "r").read()

backup_path = f"{boot_path}/printers/{sn}/backups.tar"
if not os.path.isfile(backup_path):
    # We only do this once, ideally to grab the keys and config in a pristine state.
    report_progress("Backing up printer configuration")
    try:
        os.makedirs(os.path.dirname(backup_path), exist_ok = True)
    except:
        pass # whatever, we'll catch it in a moment anyway
    files = [ "/oem", "/config", "/userdata/cfg" ]
    files += glob.glob("/userdata/upgrade.json")
    files += glob.glob("/userdata/upgrade/firmware/*.json")
    if os.system(f"tar cvf {backup_path} {' '.join(files)}") != 0:
        report_failure(f"Error while creating {backup_path}.")
    os.system("sync")
    report_success()

# validate that we're on a machine that has a supported device tree
report_progress("Checking system compatibility")

if not os.path.isfile(f"{installer_path}/kernel/{device_tree_compute_key()}.dts"):
    report_failure("This custom firmware image does not support this printer's hardware version.")

report_success()


def download_firmware(update_url, dest_path):
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    report_interim_progress("Connecting...")
    success = False
    retry = 1
    while success == False and retry < 20:
        try:
            if os.system("ping -c 3 -W 1000 8.8.8.8") != 0:
                report_interim_progress("Network is unreachable. Please check your WiFi connection.")
                os.system("/userdata/x1plus/debug_wifi.sh")
                time.sleep(5)
            resp = requests.get(update_url, headers={'User-Agent': f'X1Plus/{cfw_version}'}, stream=True, verify="/etc/ssl/certs/", timeout=30)
            resp.raise_for_status()
        except (requests.Timeout, requests.exceptions.HTTPError, requests.exceptions.RequestException) as e:
            report_interim_progress(f"{e.__class__.__name__}: {e} ... retry {retry}")
            time.sleep( pow( 2, retry ) if retry < 4 else 16 )
            retry += 1
        except Exception as e:
            report_interim_progress(f"An error occurred: {e} ... retry {retry}")
            time.sleep( pow( 2, retry ) if retry < 4 else 16 )
            retry += 1
        else:
            try:
                totlen = int(resp.headers.get('content-length', 0))
                curlen = 0
                with open(dest_path, "wb") as f:
                    for buf in resp.iter_content(chunk_size=131072):
                        if not buf:
                            break
                        f.write(buf)
                        curlen += len(buf)
                        curlen_mb = round(int(curlen) / 1024 / 1024, 2)
                        totlen_mb = round(int(totlen) / 1024 / 1024, 2)
                        report_interim_progress(f"Downloading... ({curlen_mb:.2f} / {totlen_mb:.2f} MB)")
                if curlen == totlen:
                    success = True
                else:
                    report_interim_progress(f"Error - downloaded {curlen} bytes, expected {totlen} ... retry {retry}")
                    time.sleep( pow( 2, retry ) if retry < 4 else 16 )
                    retry += 1
            except Exception as e:
                report_interim_progress(f"An error occurred: {e} ... retry {retry}")
                time.sleep( pow( 2, retry ) if retry < 4 else 16 )
                retry += 1
    return success

# see if we already have a repacked base filesystem
basefw_squashfs_path = f"{boot_path}/images/{basefw_squashfs}"
if not exists_with_md5(basefw_squashfs_path, basefw_squashfs_md5):
    basefw_update_path = f"{boot_path}/firmware/{basefw_update}"
    if not exists_with_md5(basefw_update_path, basefw_update_md5):
        report_progress("Downloading base firmware")
        if not ask_permission(f"Base firmware does not exist on the SD card: {basefw_update}<br><br>Download it from Bambu Lab servers?"):
            report_failure(f"Base firmware {basefw_update} does not exist on the SD card.  Place it in {boot_path}/firmware and try again.")
        if download_firmware(basefw_update_url, basefw_update_path):
            report_interim_progress("Verifying download...")
            if not exists_with_md5(basefw_update_path, basefw_update_md5):
                report_failure("Checksum on downloaded file failed.")
            else:
                report_success()
        else:
            report_failure(f"Download failed.")

    report_progress("Uncompressing base firmware")
    report_interim_progress("<i>This bit takes a while.</i>")
    print("decrypting")
    # decrypt the update.zip.sig
    bbl_verify = c.CDLL("libbbl_verify.so")
    rv = bbl_verify.bbl_image_verify(basefw_update_path.encode(), f"{installer_path}/".encode())
    if rv != 0:
        report_failure("Failed to verify original Bambu Lab update.")
    unpack_path = f"{installer_path}/{basefw_update}"[:-4]
    
    report_interim_progress("Really, go get a cup of tea or something.")
    print("unzipping")
    # unpack the update.img
    try:
        with ZipFile(unpack_path, "r") as z:
            zfile = z.infolist()[0]
            z.extract(zfile, path=installer_path)
            update_img_path = f"{installer_path}/{zfile.filename}"
    except Exception as e:
        report_failure("Failed to extract original Bambu Lab update.", e)
    report_success()
    
    report_progress("Extracting base firmware")
    # look for header offsets
    try:
        with open(update_img_path, "rb") as f:
            # RKFW header first
            if f.read(4) != b'RKFW':
                raise ValueError("bad RKFW header")
            f.seek(0x21)
            rkafoff, rkafsize = struct.unpack("<LL", f.read(8))
            print(f"RKFW header: RKAF @ {rkafoff}, sz {rkafsize}")
            
            # RKAF header next
            f.seek(rkafoff)
            if f.read(4) != b'RKAF':
                raise ValueError("bad RKAF header")
            f.seek(rkafoff + 0x88)
            nfiles, = struct.unpack("<L", f.read(4))
            rootfsoff = None
            for i in range(nfiles):
                name, path, ioff, noff, isize, fsize = struct.unpack("<32s64sLLLL", f.read(0x70))
                name = name.split(b"\x00")[0].decode()
                path = path.split(b"\x00")[0].decode()
                if name == "rootfs":
                    rootfsoff = rkafoff + ioff
            if rootfsoff is None:
                raise ValueError("no rootfs in RKAF")
            print(f"RKAF header: rootfs at {rootfsoff}")
    except Exception as e:
        report_failure("Failed to unpack original Bambu Lab update.", e)
    
    # actually do the repacking
    try:
        with open(update_img_path, "rb") as f:
            with tempfile.TemporaryDirectory(dir = installer_path) as d:
                print(f"unpacking ext2fs to {d}")
                packs = dump_rootfs(f, rootfsoff, d)
                with open(f"{d}/packfile", "w") as packf:
                    packf.write(packs)
                nfiles = len(packs.split('\n'))
                print(f"unpacked {nfiles} inodes")
                report_success()
                report_progress("Packing base filesystem")
                print(f"invoking gensquashfs to generate {basefw_squashfs_path}")
                os.makedirs(os.path.dirname(basefw_squashfs_path), exist_ok = True)
                # level=4,armthumb is marginally (5%) tighter but is WAY too slow
                if os.system(f"{installer_path}/gensquashfs -d mtime=${basefw_mtime} -c xz -X dictsize=8192,level=0 -F \"{d}/packfile\" -f \"{basefw_squashfs_path}\"|grep -Fv 'packing ino_'") != 0:
                    raise RuntimeError("failed to invoke gensquashfs")
    except Exception as e:
        report_failure("Failed to repack original Bambu Lab update.", e)
    
    if not exists_with_md5(basefw_update_path, basefw_update_md5):
        report_failure("Generated base filesystem has incorrect digest.")
    report_success()

# create a filesystem on the sd card
# XXX: add checkbox config to keep / destroy user ext4 contents
skip_ext4_create = False

rw_ext4 = f"{boot_path}/rw.ext4"

if system_is_sd_boot():
    print("skipping ext4 creation because we are already booted into kexec")
    skip_ext4_create = True

if os.path.isfile(rw_ext4) and not skip_ext4_create:
    os.makedirs("/tmp/rw_ext4", exist_ok = True)
    if os.system(f"mount -o loop,ro {rw_ext4} /tmp/rw_ext4") == 0:
        if os.path.isfile("/tmp/rw_ext4/preserve"):
            print("skipping ext4 creation because of preserve flag")
            skip_ext4_create = True
        os.system(f"umount /tmp/rw_ext4")

if skip_ext4_create:
    # make sure it is at least mountable
    report_progress("Preserved existing writable rootfs")
    if not system_is_sd_boot():
        os.makedirs("/tmp/rw_ext4", exist_ok = True)
        if os.system(f"mount -o loop,ro {rw_ext4} /tmp/rw_ext4") != 0:
            report_failure(f"{rw_ext4} appears not to be mountable, but it was otherwise going to be preserved.")
        os.system("umount /tmp/rw_ext4")
else:
    report_progress("Creating writable rootfs on SD card")
    try:
        with open(rw_ext4, "a+b") as f:
            f.truncate(fs_size)
        if os.system(f"mkfs.ext4 -F {rw_ext4}") != 0:
            raise RuntimeError("mkfs.ext4 returned error")
        os.makedirs("/tmp/rw_ext4", exist_ok = True)
        if os.system(f"mount -o loop {rw_ext4} /tmp/rw_ext4") != 0:
            raise RuntimeError("mount returned error")
        os.makedirs("/tmp/rw_ext4/upper", exist_ok = True)
        os.makedirs("/tmp/rw_ext4/work", exist_ok = True)
        os.chmod("/tmp/rw_ext4/upper", 0o755)
        os.chmod("/tmp/rw_ext4/work", 0o755)
        os.system("umount /tmp/rw_ext4")
        os.system("sync")
    except Exception as e:
        os.unlink(rw_ext4)
        report_failure(f"Failed to create ext4 filesystem in {rw_ext4}.", e)
    report_success()

report_progress("Copying custom firmware")
try:
    shutil.copyfile(f"{installer_path}/{cfw_squashfs}", f"{boot_path}/images/{cfw_squashfs}")
except Exception as e:
    report_failure(f"Failed to copy {cfw_squashfs}.", e)

# we do the base firmware patch in here at the same time
bbl_screen_squashfs = f"bbl_screen-{cfw_version}.squashfs"
try:
    if os.system(f"{installer_path}/rdsquashfs -c usr/bin/bbl_screen {basefw_squashfs_path} > {installer_path}/bbl_screen.orig") != 0:
        report_failure("Failed to extract binaries from base filesystem.")
    if os.system(f"{installer_path}/xdelta3 -f -d -s {installer_path}/bbl_screen.orig {installer_path}/bbl_screen.xdelta {installer_path}/printer_ui.so") != 0:
        report_failure("Failed to patch binaries from base filesystem.")
    with open(f"{installer_path}/printer_ui.pack", "w") as f:
        f.write(f"file /opt/x1plus/lib/printer_ui.so 755 0 0 printer_ui.so")
    if os.system(f"{installer_path}/gensquashfs -d mtime=${basefw_mtime} -c xz -X dictsize=8192,level=0 -F \"{installer_path}/printer_ui.pack\" -D \"{installer_path}\" -f {boot_path}/images/{bbl_screen_squashfs}") != 0:
        raise RuntimeError("failed to invoke gensquashfs")
except Exception as e:
    report_failure(f"Failed to patch base binaries.", e)

os.system("sync")

report_success()

report_progress("Copying kernel")

try:
    shutil.copytree(f"{installer_path}/kernel", f"{boot_path}/kernel/{cfw_version}", dirs_exist_ok = True)
except Exception as e:
    report_failure("Failed to copy kernel image.", e)
os.system("sync")

report_success()

report_progress("Generating boot.conf")

try:
    with open(f"{boot_path}/boot.conf", "w") as f:
        f.write(f"KERNEL={cfw_version}\n")
        f.write(f"VOLATILE=rw.ext4\n")
        f.write(f"BASE={basefw_squashfs}\n")
        f.write(f"CFW=\"{cfw_squashfs} {bbl_screen_squashfs}\"\n")
        f.write(f"CMDLINE=\"storagemedia=emmc androidboot.storagemedia=emmc androidboot.mode=normal boot_reason=cold mp_state=production fuse.programmed=1 earlycon=uart8250,mmio32,0xff570000 console=ttyFIQ0 rootwait snd_aloop.index=7 fbcon=rotate:3\"")
except Exception as e:
    report_failure("Failed to write boot.conf.", e)
os.system("sync")
report_success()

def bootloader_is_outdated(path):
    try:
        if filecmp.cmp(f"{path}/etc/init.d/S75kexec", f"{installer_path}/S75kexec") == False:
            return True
        if filecmp.cmp(f"{path}/opt/kexec/boot", f"{installer_path}/kexec/boot") == False:
            return True
        if filecmp.cmp(f"{path}/opt/kexec/check_kexec", f"{installer_path}/kexec/check_kexec") == False:
            return True            
        if filecmp.cmp(f"{path}/opt/kexec/kexec_ui.so", f"{installer_path}/kexec/kexec_ui.so") == False:
            return True
    except:
        return True
    return False

def install_bootloader_in_path(path):
    # We try to be a little more careful here -- we do this in a
    # sequence that ought be safe.
    
    # Don't install on anything newer than a version that we know is ok.
    try:
        with open(f"{path}/etc/bblap/Version", "r") as apvf:
            apv = apvf.read().strip()
            if apv > latest_safe_bblap:
                raise RuntimeError(f"rootfs version {apv} too new to install bootloader")
    except Exception as e:
        return e
    
    # Before we go fiddling with anything, make sure there is not an old
    # init script that can end up in a bad state.
    for script in ["S48kexec", "S75kexec"]:
        try:
            os.unlink(f"{path}/etc/init.d/{script}")
        except FileNotFoundError as e:
            pass
    os.system("sync")
    
    try:
        # Now we can copy in the stub...
        shutil.rmtree(f"{path}/opt/kexec", ignore_errors = True)
        os.makedirs(f"{path}/opt", exist_ok = True)
        shutil.copytree(f"{installer_path}/kexec", f"{path}/opt/kexec")
        os.system("sync")
        
        # Write the start script...
        shutil.copy(f"{installer_path}/S75kexec", f"{path}/etc/init.d/x75kexec")
        os.system("sync")
        
        # ... then rename it as atomically as an inexpensive eMMC will let us.
        os.rename(f"{path}/etc/init.d/x75kexec", f"{path}/etc/init.d/S75kexec")
        os.system("sync")
        
    except Exception as e:
        return e

    return None

# Figure out which partition is primary, and which is secondary.
with open("/proc/cmdline", "r") as f:
    bootpart = next((a.split("=")[1] for a in f.read().strip().split() if a.startswith("androidboot.slot_suffix")), "-a")

parts = ["_a", "_b"] if bootpart == "_a" else ["_b", "_a"]
report_progress(f"{'Installing' if not system_is_sd_boot() else 'Updating'} bootloader shim")

# Do the primary partition first.
if system_is_sd_boot():
    os.makedirs("/tmp/system", exist_ok = True)
    if os.system(f"mount -o ro /dev/block/by-name/system{parts[0]} /tmp/system") != 0:
        report_failure("Failed to mount primary root partition.")
    if bootloader_is_outdated("/tmp/system"):
        report_interim_progress("Updating primary partition.")
        if os.system(f"mount -o remount,rw /tmp/system") != 0:
            report_failure("Failed to remount primary root partition as writable.")
        e = install_bootloader_in_path("/tmp/system")
        if e is not None:
            report_failure("Failed to install primary bootloader.", e)
    if os.system("umount /tmp/system") != 0:
        report_failure("Failed to unmount primary root partition.")
    os.system("sync")
else:
    if bootloader_is_outdated("/"):
        report_interim_progress("Installing on primary partition.")
        if os.system("mount -o remount,rw /") != 0:
            report_failure("Failed to remount root filesystem as writable.")
        e = install_bootloader_in_path("/")
        if e is not None:
            report_failure("Failed to install bootloader.", e)
        os.system("sync")
        if os.system("mount -o remount,ro /") != 0:
            time.sleep(2)
            os.system("mount -o remount,ro /")
            # Oh, well.
        os.system("sync")

# Now, the secondary partition.
os.makedirs("/tmp/system", exist_ok = True)
if os.system(f"mount -o ro /dev/block/by-name/system{parts[1]} /tmp/system") != 0:
    report_failure("Failed to mount backup root partition.")
if bootloader_is_outdated("/tmp/system"):
    report_interim_progress("Installing on backup partition.")
    if os.system(f"mount -o remount,rw /tmp/system") != 0:
        report_failure("Failed to remount backup root partition as writable.")
    e = install_bootloader_in_path("/tmp/system")
    if e is not None:
        # It's ok if this fails.  They could have downgraded from something
        # we don't support.  Not the end of the world.
        print("Failed to install backup bootloader.", e)
if os.system("umount /tmp/system") != 0:
    report_failure("Failed to unmount backup root partition.")
os.system("sync")

report_success()

report_complete()
