<!-- SPDX-License-Identifier: GPL-2.0 -->
# Redmi 9A 干净基线内核 (stock_defconfig, 4.19.275-perf) — 构建与排障记录

- 仓库: https://github.com/plmzaq2112/android_kernel_mt6765
- 路线: 与 build-tools/../BUILD.md 的 blossom 定制路线互补; 本目录为
        **stock_defconfig 原厂基线**路线: 源码不动功能、仅修复可编译性与可开机性,
        产出无 magisk / init_su / KernelSU 痕迹的干净 boot.img。
- 状态: 实机验证通过 (Redmi 9A / M2006C3LI / Android 14, 内核 4.19.275-perf #3)。

## 目录

| 路径 | 说明 |
|---|---|
| patch/ | 15 个源码修复补丁 (对应本仓库已应用的修改, 可追溯) |
| boot-4.19.275-perf-v2.config-fragment | blossom 对齐 fragment (NR_CPUS=8, 关 MTK sched 扩展) |
| verify-boot-v2.txt | v2 交付镜像各部分 md5 校验 |
| script/build_kernel.sh | 编译命令 (clang 18 + LLD, O=out/kbuild-stock, -j8) |
| script/pack_boot.py | boot.img 重打包 (仅替换 kernel, 保留 ramdisk/dtb/cmdline) |
| script/dump_boot.py | boot.img 结构拆分查看 (读 ramdisk/dtb/cmdline) |

## 编译环境

- 工具链: clang 18.1.8 + ld.lld 18.1.8 + aarch64-linux-gnu-gcc (GNU 交叉汇编器) + llvm 工具箱
- 构建目录: `O=out/kbuild-stock`
- 命令: `make O=out/kbuild-stock ARCH=arm64 CC=clang CROSS_COMPILE=aarch64-linux-gnu- LD=ld.lld
  NM=llvm-nm OBJCOPY=llvm-objcopy OBJDUMP=llvm-objdump STRIP=llvm-strip AR=llvm-ar
  KCFLAGS=-Wno-error -j8 Image.gz`
- 注: 子目录 Makefile 的 `-Werror` 会覆盖 KCFLAGS; MTK 子树已在这些修改中批量移除。

## 内核版本串

- v1 (#2): `Linux version 4.19.275-perf ... #2 SMP PREEMPT ... 09:59:30 2026` — 开机崩溃
- v2 (#3): `Linux version 4.19.275-perf ... #3 SMP PREEMPT ... 12:42:38 2026` — 实机验证通过

## 产物 (v2, 交付)

- boot-4.19.275-perf-v2.img (67108864 bytes, md5 `5e945a47af934200492a62d29524b7f9`)
- 基底: boot-4.19.275-mt6765-ksu25.img (实机验证可开机) — 仅替换 kernel, 保留
  ramdisk=737009B (v11_clean1-rd.gz, md5 `75776100...`, 与 KSU25 一致),
  dtb=126985B (md5 `cd51d73f...`, 有效 FDT), cmdline 原样, header v2/page 2048。

## 排障记录

### 1. 首次刷机无限重启 — stock_boot.img 坏 dtb
- 现象: 基于 boot-stock-base.img (= stock_boot.img) 打包, 刷入后 bootloop、无动画。
- 根因: stock_boot.img 的 dtb 区 (113703B) 首 4 字节 `d7 b7 ab 1e`, 非标准 FDT magic
  (`d0 0d fe ed`)。内核引导读取坏 dtb → 硬件树错误 → 秒重启。
- 结论: stock_boot.img 仅作参考; 打包底座必须用有效 dtb 的镜像。

### 2. v1 刷入后仍不开机 — sched/cpufreq 配置组合崩溃
- 现象: v1 (dtb 有效 + 新内核) 开机约 1.08s 内核 Oops, 无限重启。
- pstore: `idle_cpu+0x2c/0x64` ← `cpufreq_acct_update_power.cold.1+0x68/0xc8`
  (account_system_time → account_process_tick → cpufreq_acct_update_power,
  内 `for_each_possible_cpu(cpu) if (!idle_cpu(cpu))...`; 崩溃地址为非法 per-cpu 指针)。
- 根因: stock_defconfig 的 `CONFIG_NR_CPUS=64 + MTK_SCHED_CPU_PREFER /
  MTK_SCHED_BIG_TASK_MIGRATE / MTK_SCHED_INTEROP =y` 与实机成功开机组合不同
  (参考 out_blossom/KSU25: NR_CPUS=8, 三者全关)。
- 修复 (v2): 按 fragment 对齐成功组合 `CONFIG_NR_CPUS=8`, 关闭三项 MTK sched 扩展。
- 结果: 实机正常进系统, 无 panic/oops, SELinux enforcing, Android 14 稳定。

## 配置变更 (相对 stock_defconfig)

1. `CONFIG_TRACE_PRINTK=y` — mmp/src/mmprofile.c 无条件用 event_trace_printk, 依赖
   该配置导出的 __trace_bprintk/__trace_printk 声明。
2. `CONFIG_WLAN_DRV_BUILD_IN=y` — 否则 wmt_drv 编为模块, GPS 内建引用 mtk_wcn_*/mtk_wmt_*
   链接 undefined (blossom_defconfig 亦为 =y)。
3. CONFIG_CUSTOM_KERNEL_LCM 移除源码 zip 缺失条目: ili9882n_vdo_hdp_xinli, td4160_vdo_hdp_boe_xinli
4. CONFIG_CUSTOM_KERNEL_IMGSENSOR 移除 zip 缺失条目: hynix_hi556_ii

## 源码修复 (patch/ 目录)

- **缺失 TRACE_EVENT**: include/trace/events/sched.h 补 trace_sched_set_cpuprefer /
  trace_sched_big_task_rotation / trace_sched_big_task_migration;
  kernel/sched/extension/tuning.c 调用时传 prefer_type。
- **mrdump**: kernel/module.c 初始化 struct module_sect_attr (.name → .battr.attr.name, 2处);
  drivers/misc/mediatek/aee/mrdump/mrdump_helper.c 补 aee_wdt_zap_locks weak 空桩。
- **杂项**: virtgpu_vq.c kmalloc_array(nents) → obj->pages->nents;
  include/linux/cpumask.h 的 `1UL<<64` UB (NR_CPUS==64==BITS_PER_LONG) 改 ULONG_MAX 分支;
  devapc/mt6765.c 补 #include <linux/sched/clock.h>。
- **连接性子系统**: fw_log_gps.c 等放开被 `#if 0` 包裹的 connsys_debug_utility.h include;
  connectivity/common/Makefile 恢复 debug_utility 的 ccflags 与 {ring,ring_emi,
  connsys_debug_utility}.o (否则 connsys_log_deinit 等链接 undefined); wlan/adaptor/fw_log_wifi.c 同类。
- **图像传感器**: kd_imgsensor.h 补 gc02m10_SENSOR_ID 0x0210、OV02B_V_SENSOR_ID 0x2d。
- **-Werror 移除**: drivers/misc/mediatek/{Makefile,base/power/mcdi{,/mcdi_v1},
  connectivity/{common,conninfra,wlan/core/gen4m},geniezone,met_drv,pmic/mt6370,
  rt-regmap,trusted_mem,typec/tcpc}/Makefile。

## 校验

- make 全程 BUILD_RC=0; Image.gz 产出。
- dump_boot.py 对比: 仅 kernel 替换, ramdisk/dtb/cmdline/header 一致。
- 内核字符串扫描: magisk / init_su / KernelSU 均 clean。

## 刷机参考 (风险自负)

```bash
adb push out/boot-4.19.275-perf-v2.img /data/local/tmp/
adb shell su -c "dd if=/data/local/tmp/boot-4.19.275-perf-v2.img of=/dev/block/mmcblk0p33 bs=4096 conv=fsync"
adb reboot
```