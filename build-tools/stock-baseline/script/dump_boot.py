#!/usr/bin/env python3
import struct, sys, os

def u32(d, o): return struct.unpack_from("<I", d, o)[0]

for path in sys.argv[1:]:
    data = open(path, "rb").read()
    page = u32(data, 36)
    hdr_ver = u32(data, 40)
    ksz = u32(data, 8)
    rsz = u32(data, 16)
    ssz = u32(data, 24)
    off = page + ((ksz + page - 1)//page)*page
    ramdisk_abs = off
    off += ((rsz + page - 1)//page)*page
    off += ((ssz + page - 1)//page)*page
    dtb_size = u32(data, 1648) if hdr_ver >= 2 and len(data) > 1656 else 0
    dtb_abs = off
    print(f"{os.path.basename(path)}: page={page} hdr_v={hdr_ver} kern={ksz} ramdisk={rsz}@{ramdisk_abs} dtb={dtb_size}@{dtb_abs}")
    # dump ramdisk + dtb to workspace for inspection
    base = "/home/a12bbb/kernel-patch-workspace/out"
    open(f"{base}/rd_{os.path.basename(path).replace('.img','')}.bin", "wb").write(data[ramdisk_abs:ramdisk_abs+rsz])
    if dtb_size:
        open(f"{base}/dtb_{os.path.basename(path).replace('.img','')}.bin", "wb").write(data[dtb_abs:dtb_abs+dtb_size])
    cmd = data[64:64+512].split(b"\x00",1)[0].decode(errors="replace")
    print(f"    cmdline: {cmd}")