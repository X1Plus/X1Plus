#!/usr/bin/env python3

# X1Plus image build tool
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
#
# An .x1p installable file has the following format:
#
# The outer wrapper is a zip file.  It needs to be a zip file in order for
# Qt to be able to flip through it trivially with Quazip.  Inside the zip
# file, there is the following:
#
#   info.json: a JSON file that specifies what this .x1p file contains (and
#              also contains configuration data for the installer)
#
#   payload.tar.gz: a tarball, which gets extracted into /userdata/x1plus. 
#                   The entry point for the payload is
#                   /userdata/x1plus/install.sh; install.sh is expected to
#                   communicate using DDS with the installer GUI.  This
#                   needs to be a tarball in order to preserve permissions. 
#                   Usually, install.sh will contain a set of Python
#                   packages.
#
# To use the installer, the payload has some bits and bobs from this
# directory, a Python installation, some prebuilts, and a launch script.

import os
import io
import sys
import zipfile
import tarfile
import json

ROOTPATH = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

INFO = json.load(open(f"{ROOTPATH}/installer/info.json", "r"))

# Create a ZIP file.
zf = zipfile.ZipFile(sys.argv[1], "w")
zf.write(f"{ROOTPATH}/installer/info.json", arcname="info.json")

# Create a tar file (we'll put it in memory because we're going to send it
# straight to the zip file).

tf_buf = io.BytesIO()
tf = tarfile.open(fileobj=tf_buf, mode="w|gz")

def add(path, name):
    print(f"{path} -> {name}")
    tf.add(path, arcname=name)

# scripts from this directory
for f in ["dds.py", "ext4.py", "info.json", "install.py", "install.sh"]:
    add(f"{ROOTPATH}/installer/{f}", f)

# CFW base image
add(f"{ROOTPATH}/images/cfw.squashfs", f"{INFO['cfwVersion']}.squashfs")

# bbl_screen build
add(f"{ROOTPATH}/bbl_screen-patch/printer_ui.so.xdelta", "bbl_screen.xdelta")

# prebuilt binaries
for f in ["gensquashfs", "rdsquashfs", "xdelta3", "libdds_intf.so", "loop.ko"]:
    add(f"{ROOTPATH}/prebuilt/{f}", f)

# kexec stub
add(f"{ROOTPATH}/internal-fs/etc/init.d/S75kexec", "S75kexec")
for f in ["boot", "check_kexec", "start_recovery.sh", "disable_upgrade.sh"]:
    add(f"{ROOTPATH}/internal-fs/opt/kexec/{f}", f"kexec/{f}")
for f in ["dtc", "kexec", "kexec_mod_arm.ko", "kexec_mod.ko", "evtest", "jq"]:
    add(f"{ROOTPATH}/prebuilt/{f}", f"kexec/{f}")
add(f"{ROOTPATH}/bbl_screen-patch/kexec_ui.so", "kexec/kexec_ui.so")

# kernel image... ugh
kpath = f"{ROOTPATH}/fat32-boot-fs/boot/kernel/current"
for f in os.listdir(kpath):
    add(os.path.join(kpath, os.readlink(os.path.join(kpath, f))), f"kernel/{f}")

# Copy the prebuilt Python3 into the archive.
print("Copying Python...")
with tarfile.open(f"{ROOTPATH}/prebuilt/python3.tar.gz", "r:*") as rtf:
    for ti in rtf:
        f = rtf.extractfile(ti)
        tf.addfile(ti, fileobj=f)

tf.close()

# Add the tar file.
zf.writestr("payload.tar.gz", tf_buf.getvalue())
zf.close()

