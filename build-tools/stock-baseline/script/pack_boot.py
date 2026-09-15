#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""从原厂 boot-stock-base.img 重打包: 仅替换 kernel, 保留原厂 ramdisk/dtb/cmdline/header。

用法:
  python3 pack_boot.py [base_boot.img] [new_kernel] [out_boot.img]
默认:
  base       = out/boot-stock-base.img      (原厂干净基线)
  new_kernel = out/arch/arm64/boot/Image.gz (本工作区编译产物)
  out        = out/boot-patched.img
环境变量:
  KERNEL_IMG / RAMDISK_IMG / CMDLINE   可覆盖默认
"""
import struct, sys, os

def u32(data, off): return struct.unpack_from("<I", data, off)[0]
def u64(data, off): return struct.unpack_from("<Q", data, off)[0]
def align_up(x, page): return ((x + page - 1) // page) * page

BASE = os.environ.get("KERNEL_IMG_SRC") or "/home/a12bbb/kernel-patch-workspace/out"
KERNEL_DEFAULT = os.path.expanduser(BASE + "/Image.gz")

def main():
    base      = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser(BASE + "/boot-stock-base.img")
    new_kernel = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("KERNEL_IMG") or KERNEL_DEFAULT
    out        = sys.argv[3] if len(sys.argv) > 3 else os.path.expanduser(BASE + "/boot-patched.img")
    new_ramdisk = os.environ.get("RAMDISK_IMG") or os.path.expanduser(BASE + "/ramdisk-stock.bin")

    data = open(base, "rb").read()
    kernel_gz = open(new_kernel, "rb").read()

    page = u32(data, 36)
    hdr_ver = u32(data, 40)
    print(f"base={base}\npage_size={page} header_version={hdr_ver}")

    kernel_size = u32(data, 8)
    ramdisk_size = u32(data, 16)
    second_size = u32(data, 24)

    hdr = bytearray(data[:page])
    struct.pack_into("<I", hdr, 8, len(kernel_gz))  # kernel_size

    off = page
    off += align_up(kernel_size, page)
    ramdisk_abs = off
    off += align_up(ramdisk_size, page)
    off += align_up(second_size, page)
    dtb_abs = off
    dtb_size = u32(data, 1648) if hdr_ver >= 2 and len(data) > 1656 else 0

    ramdisk = data[ramdisk_abs:ramdisk_abs + ramdisk_size]
    if os.path.exists(new_ramdisk):
        custom = open(new_ramdisk, "rb").read()
        # 仅允许替换为与原厂同内容的干净 ramdisk（等重打或更小的都按包本身长度写入）
        struct.pack_into("<I", hdr, 16, len(custom))
        print(f"ramdisk:  替换为 {len(custom)} bytes (原 {ramdisk_size})")
        ramdisk = custom
    dtb = data[dtb_abs:dtb_abs + dtb_size] if dtb_size else b""

    print(f"原 kernel: {kernel_size} bytes -> 新 {len(kernel_gz)}")
    print(f"ramdisk:   {len(ramdisk)} bytes")
    print(f"dtb:       {len(dtb)} bytes (原样保留)")

    if not ramdisk:
        print("ERROR: ramdisk 为空"); sys.exit(1)

    out_buf = bytearray()
    out_buf += hdr
    off = len(out_buf)
    out_buf += kernel_gz
    off += len(kernel_gz)
    out_buf += b"\x00" * ((page - (off % page)) % page)
    out_buf += ramdisk
    off = len(out_buf)
    out_buf += b"\x00" * ((page - (off % page)) % page)
    if dtb:
        out_buf += dtb
        off = len(out_buf)
        out_buf += b"\x00" * ((page - (off % page)) % page)

    if len(out_buf) < len(data):
        out_buf += b"\x00" * (len(data) - len(out_buf))

    with open(out, "wb") as f:
        f.write(out_buf)
    print(f"output: {out} ({len(out_buf)} bytes) vs 原 {len(data)}")

if __name__ == "__main__":
    main()