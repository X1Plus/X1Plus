#!/usr/bin/env python3

# QRC extraction tool
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
import unicorn as uc
import unicorn.arm_const as uca
import elftools.elf.elffile as ef
import subprocess
import zipfile
import os
import struct
import zlib
import xml.etree.ElementTree

TOOLCHAIN = os.environ.get("TOOLCHAIN", "arm-linux-gnueabihf-")

# loosely based on https://github.com/pgaskin/qrc, mercilessly hacked by joshua

def unpack_qrc(bin, treep, datap, namep):
    qrcbundle = {}
    def rdnode(ofs, pfx = ""):
        ndata = bin[treep + ofs:]
        nameoffset, flags, d1, d2, mtime = struct.unpack(">LHLLQ", ndata[:22])
        #print(nameoffset, flags, d1, d2)
    
        nlen, = struct.unpack(">H", bin[namep+nameoffset:namep+nameoffset+2])
        name = bin[namep+nameoffset+2+4:namep+nameoffset+2+4+nlen*2].decode('utf-16be')
        #print(f"{pfx}{name}")

        if flags & 2: # directory
            childcount = d1
            childoffset = d2
        
            for i in range(childcount):
                rdnode((childoffset + i) * 22, f"{pfx}{name}/" if ofs != 0 else pfx)
        else:
            compressed = flags & 1
            compressed_zstd = flags & 4
            # d1 contains country and language, we ignore those
            dataoffset = d2
            datalen, = struct.unpack(">L", bin[datap+dataoffset:datap+dataoffset+4])
            data = bin[datap+dataoffset+4:datap+dataoffset+4+datalen]
            if compressed_zstd:
                raise ValueError("compressed with zstd")
            if compressed:
                data = zlib.decompress(data[4:])
            
            qrcbundle[f"{pfx}{name}"] = data
    rdnode(0)
    return qrcbundle


if len(sys.argv) < 2:
    print(f"usage: {sys.argv[0]} arm_elf_qt_binary...")
    exit(2)

def extract(binary):
    bundles = {}
    
    print(f"looking up potential targets in {binary}...")
    # this is an extremely frumious hack to try to look up callsites for
    # qRegisterResourceData and assume that all the generated callsites look
    # the same.  but it is not *that* much more frumious than the original
    # hack of emulating shit, so...
    spr = subprocess.run(f"{TOOLCHAIN}objdump -d {binary} | grep bl.*qRegisterResourceData", shell=True, capture_output=True)
    spr_error = spr.stderr.decode()
    if spr_error.strip() != "":
        raise Exception(f"Error running objdump (do you have the correct prefixed one installed?): {spr_error}")
    targets = []
    for l in spr.stdout.decode().strip().split('\n'):
        # back up 8 instructions from the bl
        tgt = int(l.split(':')[0].strip(), 16) - 8*4
        print(f"found potential qInitResources at 0x{tgt:x}")
        targets.append(tgt)

    with open(binary, "rb") as f:
        elf = ef.ELFFile(f)
        if elf.get_machine_arch() != "ARM":
            raise Exception(f"Only ARM binaries are supported, but {binary} is {elf.get_machine_arch()}")
        for qrc_name, qrc_init in enumerate(targets):
            # initialize unicorn
            emu = uc.Uc(uc.UC_ARCH_ARM, uc.UC_MODE_THUMB if qrc_init&1 else uc.UC_MODE_ARM)

            # load the elf
            with open(binary, "rb") as f2: 
                for x in elf.iter_segments("PT_LOAD"):
                    vaddr, offset, filesz, memsz, flags = x["p_vaddr"], x["p_offset"], x["p_filesz"], x["p_memsz"], x["p_flags"]
                    f2.seek(offset)
                    memsz = memsz + vaddr % 4096
                    memsz = memsz + (4096 - memsz % 4096)
                    vaddr -= vaddr % 4096
                    emu.mem_map(vaddr, memsz, (uc.UC_PROT_EXEC if flags&0b001 else 0) + (uc.UC_PROT_WRITE if flags&0b010 else 0) + (uc.UC_PROT_READ if flags&0b100 else 0))
                    emu.mem_write(vaddr, f2.read(filesz) + bytes([0]*(memsz - filesz)))

            # initialize the stack
            emu.mem_map(0x40000000 - 0x10000, 0x10000)
            emu.reg_write(uca.UC_ARM_REG_SP, 0x40000000)

            # r0, r1, r2, r3 should be overwritten later
            emu.reg_write(uca.UC_ARM_REG_R0, 0xFFFFFFFF)
            emu.reg_write(uca.UC_ARM_REG_R1, 0xFFFFFFFF)
            emu.reg_write(uca.UC_ARM_REG_R2, 0xFFFFFFFF)
            emu.reg_write(uca.UC_ARM_REG_R3, 0xFFFFFFFF)

            # execute until a branch
            def block_hook(emu, address, size, user_data):
                if address != qrc_init&~1:
                    raise Exception(f"branched")
            emu.hook_add(uc.UC_HOOK_BLOCK, block_hook)
            try:
                emu.emu_start(qrc_init, qrc_init+128)
            except Exception as err:
                if str(err) != "branched":
                    raise Exception(f"Failed to emulate") from err

            # get the args to qRegisterResourceData
            qrc_version = emu.reg_read(uca.UC_ARM_REG_R0)
            qrc_tree = emu.reg_read(uca.UC_ARM_REG_R1)
            qrc_names = emu.reg_read(uca.UC_ARM_REG_R2)
            qrc_data = emu.reg_read(uca.UC_ARM_REG_R3)

            # convert the offsets
            if qrc_version == 0xFFFFFFFF or qrc_tree == 0xFFFFFFFF or qrc_names == 0xFFFFFFFF or qrc_data == 0xFFFFFFFF:
                raise Exception("qInitResources didn't set arguments before branching")

            def virt2file(addr):
                for x in elf.iter_segments("PT_LOAD"):
                    vaddr, offset, filesz, memsz, flags = x["p_vaddr"], x["p_offset"], x["p_filesz"], x["p_memsz"], x["p_flags"]
                    if addr >= vaddr and addr < addr+filesz:
                        return addr - vaddr + offset
                raise Exception(f"Failed to find segment for address 0x{addr:X}")
            qrc_tree, qrc_names, qrc_data = virt2file(qrc_tree), virt2file(qrc_names), virt2file(qrc_data)

            print(f"about to call unpack initializer 0x{qrc_init} from QRC with tree at 0x{qrc_tree:x}, data at 0x{qrc_data:x}, names at 0x{qrc_names:x}")
            bundles[qrc_init] = unpack_qrc(open(binary, 'rb').read(), qrc_tree, qrc_data, qrc_names)
    
    return bundles

bundles = extract(sys.argv[1])
for b in bundles:
    if 'printerui/qml/main/SettingsPage.qml' not in bundles[b]:
        continue
    print(f"{b} appears to be the printerui bundle")
    outdir = sys.argv[2]
    files = bundles[b]
    for fn in files:
        ofn = f"{outdir}/{fn}"
        try:
            os.makedirs(os.path.dirname(ofn))
        except FileExistsError:
            pass
        if fn[-3:] == ".qm":
            # convert a QM to a canonicalized TS
            tsxml = subprocess.run(f"lconvert -of ts -if qm -i -", shell=True, check=True, input=files[fn], capture_output = True).stdout.decode()
            with open(ofn[:-3] + '.ts', 'w') as f:
                f.write(xml.etree.ElementTree.canonicalize(tsxml))
        else:
            with open(ofn, 'wb') as f:
                f.write(files[fn])
            
    with open(f"{outdir}/root.qrc", "w") as f:
        f.write("<!DOCTYPE RCC><RCC version=\"1.0\"><qresource>\n")
        nl = list(files.keys())
        nl.sort()
        for n in nl:
            f.write(f"<file>{n}</file>\n")
        f.write("</qresource></RCC>\n")
    print(f"unpacked with qrc file {outdir}/root.qrc, good luck!")
