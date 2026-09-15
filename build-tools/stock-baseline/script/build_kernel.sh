#!/bin/bash
export PATH=/usr/lib/llvm-18/bin:$PATH
K=/home/a12bbb/kernel-patch-workspace/android_kernel_mt6765-main
O=/home/a12bbb/kernel-patch-workspace/out/kbuild-stock
LOG=/home/a12bbb/kernel-patch-workspace/out/build-stock.log

make -C "$K" O="$O" ARCH=arm64 CC=clang CROSS_COMPILE=aarch64-linux-gnu- \
  LD=ld.lld NM=llvm-nm OBJCOPY=llvm-objcopy OBJDUMP=llvm-objdump STRIP=llvm-strip AR=llvm-ar \
  KCFLAGS=-Wno-error -j8 Image.gz 2>&1 | tee "$LOG" | tail -1
echo "BUILD_RC=${PIPESTATUS[0]}"

echo "=== 产物 ==="
ls -la "$O/arch/arm64/boot/Image" "$O/arch/arm64/boot/Image.gz" 2>/dev/null

echo "=== 最近 error/fatal ==="
grep -iE '^error:|fatal|Error' "$LOG" | tail -10

echo "=== 内核版本串 ==="
strings "$O/vmlinux" 2>/dev/null | grep -m1 'Linux version 4\.'