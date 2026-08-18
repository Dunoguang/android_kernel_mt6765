# Redmi 9A (dandelion, MT6762G) 自定义内核构建指南

## 环境

- 树: `/home/yang/项目/kernel/mt6765-4.19` (4.19.275 + 5.x 特性移植)
- 工具链: `/home/yang/项目/kernel/toolchain/bin` (clang 16.0.6 + LLD 16.0.6, ZyC)
- 系统依赖: bison 3.8.2 / bc / libssl-dev (手动安装)
- ld.lld 依赖 libxml2.so.2: 软链接
  `tools/xml2/libxml2.so.2 -> /usr/lib/x86_64-linux-gnu/libxml2.so.16`
  (build_full.sh 已 export LD_LIBRARY_PATH)

## 构建流程(四步)

```bash
cd /home/yang/项目/kernel/mt6765-4.19

# 1. 配置: merge fragment(基线 out/.config 首次由 stock_defconfig 生成)
scripts/kconfig/merge_config.sh -O /home/yang/项目/kernel/out -m \
    /home/yang/项目/kernel/out/.config /home/yang/项目/kernel/fix11.config

# 2. 刷新并断言(防级联污染:ION 教训)
export PATH="/home/yang/项目/kernel/toolchain/bin:/usr/bin:/bin"
make ARCH=arm64 O=/home/yang/项目/kernel/out CC=clang \
    CROSS_COMPILE=aarch64-linux-gnu- LD=ld.lld olddefconfig
bash /home/yang/项目/kernel/tools/check_config.sh   # 26 must-y + 11 must-n,失败即停

# 3. 构建
bash /home/yang/项目/kernel/tools/build_full.sh    # 产物 out/arch/arm64/boot/Image.gz

# 4. 打包(自动: 移除 kpti=off,追加 secretmem.enable=1)
python3 /home/yang/项目/kernel/tools/repack.py /home/yang/项目/kernel/boot-4.19.275-full-v11.img
```

刷机: `adb reboot bootloader && fastboot flash boot boot-4.19.275-full-v11.img`

## 配置策略(fix11.config)

- **不动的基线**: stock_defconfig(MTK 驱动生态必需)
- **必须保留**: TEE 全家(Microtrust 300,Keymaster/DRM 依赖;CONFIG_TEE
  不能关,teei/Kconfig 被 `if TEE` 包裹,关闭会级联清掉整个 TEE 栈)
- **必须保留**: ION secure heap 链(MTK_SECURE_MEM_SUPPORT +
  MTK_SEC_VIDEO_PATH_SUPPORT,Widevine L1;非默认 y,merge 后要断言)
- **已关闭**: DEBUG_PREEMPT / DEBUG_INFO / KASAN / UBSAN / KALLSYMS_ALL
  / PAGE_POISONING(生产化)
- **已关闭(无硬件)**: 指纹(FPC + FOCALTECH + MICROTRUST_FP_DRIVER)、
  NFC、IKHEADERS

## 关键源码修改(移植记录)

| 文件 | 修改 |
|---|---|
| kernel/Makefile | config_data.gz 数据源 stock_defconfig -> $(objtree)/.config(/proc/config.gz 显示真实配置) |
| drivers/tee/teei/300/tee/Makefile | 模块改名 tee.o -> teei_tee.o(消除与主线 /module/tee 撞名) |
| drivers/tee/teei/300/tz_driver/switch_queue.c | teei_bind_current_cpu 用 preempt_disable/enable 包裹(4.19 无 migration_disable) |
| drivers/tee/teei/300/tz_driver/sysfs.c | wake_up(&__wait_spi_wq) 加 #ifdef CONFIG_MICROTRUST_FP_DRIVER |
| drivers/misc/mediatek/cam_cal/src/common/v1/eeprom_driver.c | driver4 .name 改为 CAM_CAL_I2C_DEV4_NAME(消除重名 -EBUSY) |
| drivers/misc/mediatek/lens/mtk/{main,main2,main3,sub,sub2}/*_lens.c | AF_probe 仅对自有 g_stAF_device 注册 i2c(消除 dts 共享 compatible 导致的重复注册) |
| fs/ntfs3/ 全套 | 5.15 NTFS3 移植(mnt_userns 15 处去参/ACL 4.19 化/submit_bh 三参/BIO_MAX_PAGES 等) |
| fs/io_uring.c 等 | 5.4 io_uring 移植 |
| mm/memfd_secret.c | 5.14 memfd_secret 移植(cmdline 需 secretmem.enable=1) |

## 验证命令(设备侧)

```bash
adb shell su -c "zcat /proc/config.gz | grep -E 'IO_URING|SECRETMEM|NTFS3|FORTIFY|ARM64_SW_TTBR0_PAN'"
adb shell su -c "dmesg | grep -iE 'BUG|WARNING|already registered|smp_processor_id' | head"
adb shell cat /proc/version
```

## 版本历史

- v7: memfd_secret + NTFS3 移植完成
- v8: /proc/config.gz 数据源修复(真实配置)
- v9: KPTI/PAN 双开、TEEI BUG 修复、teei_tee 改名、CAM_CAL_DRV 重名修复
- v10: ION secure heap 恢复(TEE 级联污染)、5 个 lens 驱动重复注册修复
- v11: 关闭无硬件噪音项(指纹/NFC/IKHEADERS),最终版

镜像: /home/yang/项目/kernel/boot-4.19.275-full-v11.img