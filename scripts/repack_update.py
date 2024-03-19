#!/usr/bin/env python3

# Bambu Lab firmware repack tool
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

from Crypto.Cipher import AES
from hashlib import sha256
from sys import argv
from os.path import basename, splitext
from zipfile import ZipFile
from io import BytesIO
import time
import struct
import ext4
import tempfile
import os


KEY_MATERIAL = bytes.fromhex(os.environ["UPDATE_KEY_MATERIAL"])
INNER_HEADER_LEN = 0x70
SHA256_LEN = 0x20
INNER_HEADER_SHA256_OFFSET = INNER_HEADER_LEN - SHA256_LEN
OUTER_HEADER_LEN = 0x1a0

def is_correct_decrypt(out_data):
    sha256_correct = out_data[INNER_HEADER_SHA256_OFFSET:INNER_HEADER_SHA256_OFFSET+SHA256_LEN]
    sha256_actual = sha256(out_data[INNER_HEADER_LEN:]).digest()
    return sha256_correct == sha256_actual

def dump_rootfs(f, dir):
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

    vol = ext4.Volume(f)
    traverse_ino("", vol.root)
    return packs

def main(in_file, out_file):
    if not KEY_MATERIAL:
        print("Please set environment variable UPDATE_KEY_MATERIAL to the update key")
        return
    if not in_file.endswith(".sig"):
        print("Input file must end with .sig")
        return
    
    in_file_name = basename(in_file)

    with open(in_file, "rb") as f:
        in_data = f.read()

    in_data = in_data[OUTER_HEADER_LEN:]

    print(f"decrypting {len(in_data)} bytes")
    out_data = AES.new(KEY_MATERIAL, AES.MODE_CTR, nonce=b"\x00" * 8).decrypt(in_data)
    if not is_correct_decrypt(out_data):
        raise ValueError("hash failed after decrypt")

    out_data = out_data[INNER_HEADER_LEN:]
    
    with ZipFile(BytesIO(out_data), "r") as z:
        names = z.namelist()
        if len(names) != 1:
            raise ValueError("too many files in update.zip")
        print(f"decompressing {names[0]}")
        update_data = z.read(names[0])
    del out_data
    
    print(f"loaded update.img with {len(update_data)} bytes")
    
    if update_data[0:4] != b"RKFW":
        raise ValueError("missing RKFW signature in update.img")
    ioff, isize = struct.unpack("<LL", update_data[0x21:0x21+8])
    print(f"update RKAF @ {ioff}, sz {isize}")
    rkaf = update_data[ioff:ioff+isize]
    del update_data
    
    if rkaf[0:4] != b"RKAF":
        raise ValueError("missing RKAF signature in embedded-update")
    nfiles = struct.unpack("<L", rkaf[0x88:0x88+4])[0]
    files = {}
    for i in range(nfiles):
        ofs = 0x8c + i * 0x70
        name, path, ioff, noff, isize, fsize = struct.unpack("<32s64sLLLL", rkaf[ofs:ofs+0x70])
        name = name.split(b"\x00")[0].decode()
        path = path.split(b"\x00")[0].decode()
        print(f"  {name}@{ioff} -> {path} ({fsize} bytes)")
        files[name] = (ioff, fsize)
    
    rootfs = rkaf[files['rootfs'][0] : files['rootfs'][0] + files['rootfs'][1]]
    del rkaf
    
    with tempfile.TemporaryDirectory() as d:
        print(f"unpacking ext2fs to {d}")
        packs = dump_rootfs(BytesIO(rootfs), d)
        with open(f"{d}/packfile", "w") as f:
            f.write(packs)
        nfiles = len(packs.split('\n'))
        print(f"unpacked {nfiles} inodes")
        ts = int(time.time())
        print(f"invoking gensquashfs to generate {out_file}, mtime={ts}")
        gensquashfs = os.environ.get('GENSQUASHFS', 'gensquashfs')
        os.system(f"set -x;{gensquashfs} -d mtime={ts} -k -c xz -X dictsize=8192,level=0 -F \"{d}/packfile\" -f \"{out_file}\"|grep -Fv 'packing ino_'")

    print(f"done")

if __name__ == "__main__":
    main(argv[1], argv[2])
