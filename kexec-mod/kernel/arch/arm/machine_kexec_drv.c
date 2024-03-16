/*
 * kexec_mod_arm: Kexec driver for ARM, heavily hacked for a Bambu Lab printer
 *
 * Copyright (C) 2021 Fabian Mastenbroek.
 * Copyright (c) 2022 - 2024 Joshua Wise
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 */

#define MODULE_NAME "kexec_mod_arm"
#define pr_fmt(fmt) MODULE_NAME ": " fmt

#include <linux/module.h>
#include <linux/clk.h>
#include <asm/patch.h>
#undef CONFIG_BBL_IOTRACE
#include <linux/io.h>
#include <linux/delay.h>
#include <linux/amba/bus.h>

static unsigned int ptr_kallsyms_lookup_name = 0;

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Joshua Wise <joshua@joshuawise.com>");
MODULE_DESCRIPTION("Kexec backport as Kernel Module for ARM");
MODULE_VERSION("1.1");

void crash_save_cpu(struct pt_regs *regs, int cpu) {}

#define WRAP(rv, what, params, names) \
static rv (*ptr_##what) params; \
rv what params { return ptr_##what names; }

WRAP(bool, memblock_is_region_memory, (phys_addr_t base, phys_addr_t size), (base, size));
WRAP(int, platform_can_cpu_hotplug, (void), ());
WRAP(void, soft_restart, (unsigned long addr), (addr));
static long long *ptr_arch_phys_to_idmap_offset;
long long arch_phys_to_idmap_offset;
WRAP(int, platform_can_secondary_boot, (void), ());
//WRAP(void, set_kernel_text_rw, (void), ());
WRAP(void, set_all_modules_text_rw, (void), ());
WRAP(void, patch_text, (void *addr, uint32_t insn), (addr, insn));
WRAP(void, pl330_remove, (struct amba_device *dev), (dev));

static void (*ptr_set_kernel_text_rw)(void);
void set_kernel_text_rw(void) {
	ptr_set_kernel_text_rw();
	set_all_modules_text_rw();
}

extern void (*kexec_reinit)(void);

#define RV1126_SOFTRST_CON(x)		((x) * 0x4 + 0x300)
#define RV1126_PMU_SOFTRST_CON(x)       ((x) * 0x4 + 0x200)
#define RV1126_PMU_CLKGATE_CON(x)	((x) * 0x4 + 0x180)
#define RV1126_CLKGATE_CON(x)           ((x) * 0x4 + 0x280)
#define RV1126_CLKSEL_CON(x)            ((x) * 0x4 + 0x100)
#define RV1126_PMU_CLKSEL_CON(x)            ((x) * 0x4 + 0x100)

static uint32_t kexecmod_resets[] = {
//	0x8001, 0x3, /* PMU_CRU_SOFTRST_CON1: GPIO0 */
//	4, 0xFFFF, /* timer, intmux, gpios 1-4 */
//	5, 0x7FFF, /* do not reset SGRF */
//	6, 0xFFFF,
//	7, 0xFFFF,
//	8, 0xFFFF,
//	9, 0xFFFF,
	/* no 10: that's storage, seems like we don't really need to shoot that */
	11, (0x1 << 6) | (1 << 8), /* usbphy_otg usbphypor_otg */
	/* no 12: DDR stuff seems sketchy */
//	13, 0xFFFF,
	0, 0,
};

extern void rv1126_dump_cru(void);

static void _shutdown_dmac(void) {
	struct amba_device *adev = amba_find_device(NULL, NULL, 0x00041330, 0x000fffff);

	/* This will cause a warning, but we do really need to do it,
	 * otherwise the DMA controller will get very upset on reset and
	 * start scribbling all over the place.
	 */
	pl330_remove(adev);
}

/* printk goes through the late-UART, not the early-UART, and the late-UART
 * uses the DMA controller.  Once we shut down the DMA controller, things
 * rapidly start to go awry if we try to use printk again!  So we build a
 * PIO UART of our own here.
 */
static uint8_t buf[512];
static void __iomem *uart_base;
static void _putc(int c) {
	writel(c, uart_base);
	while ((readl(uart_base + 0x14) & 0x60) != 0x60)
		udelay(1);
}

static void _printf(const char *s, ...) {
	int i,n;

	va_list ap;
	va_start(ap, s);
	n = vsnprintf(buf, 512, s, ap);
	va_end(ap);
	
	for (i = 0; i < n; i++) {
		if (buf[i] == '\n')
			_putc('\r');
		_putc(buf[i]);
	}
}

#define CRU_CLKSEL_CON02	0x108
#define CRU_CLKSEL_CON03	0x10c
#define CRU_CLKSEL_CON27	0x16c
#define CRU_CLKSEL_CON31	0x17c
#define CRU_CLKSEL_CON33	0x184
#define CRU_CLKSEL_CON40	0x1a0
#define CRU_CLKSEL_CON49	0x1c4
#define CRU_CLKSEL_CON50	0x1c8
#define CRU_CLKSEL_CON51	0x1cc
#define CRU_CLKSEL_CON54	0x1d8
#define CRU_CLKSEL_CON61	0x1f4
#define CRU_CLKSEL_CON63	0x1fc
#define CRU_CLKSEL_CON65	0x204
#define CRU_CLKSEL_CON67	0x20c
#define CRU_CLKSEL_CON68	0x210
#define CRU_CLKSEL_CON69	0x214

#define PMU_NOC_AUTO_CON0	(0xe0)
#define PMU_NOC_AUTO_CON1	(0xe4)


static void kexec_reinit_bambu(void) {
	uint32_t *adp;
	int i, timeout;
	void __iomem *rv1126_pmu_base = ioremap(0xff3e0000, 0x1000);
	void __iomem *rv1126_pmucru_base = ioremap(0xff480000, 0x1000);
	void __iomem *rv1126_cru_base = ioremap(0xff490000, 0x1000);
	
	uart_base = ioremap(0xff570000, 0x1000);
	
	rv1126_dump_cru();

	_shutdown_dmac();
	// We can't print anything now through printk, because the DMAC is hooked up to the serial port.

	local_irq_disable();

	_printf("BAMBU REINIT: mapped PMU at 0x%08x, CRU at 0x%08x\n", (uint32_t) rv1126_pmu_base, (uint32_t) rv1126_cru_base);

	/* make npu aclk and sclk less then 300MHz when reset */
	writel(0x00ff0055, rv1126_cru_base + CRU_CLKSEL_CON65);
	writel(0x00ff0055, rv1126_cru_base + CRU_CLKSEL_CON67);

	_printf("BAMBU REINIT: turning clocks back on\n");
	// Remember: CLKGATE 1 means turn the clock off, not turn the clock on!
	for (i = 0; i < 3; i++) {
		writel(0xffff0000, rv1126_pmucru_base + RV1126_PMU_CLKGATE_CON(i));
	}
	
	writel(0xffff0017, rv1126_cru_base + RV1126_CLKSEL_CON(1));
	for (i = 0; i < 24; i++) {
		writel(0xffff0000, rv1126_cru_base + RV1126_CLKGATE_CON(i));
	}
	
	writel(0xffff0800, rv1126_pmucru_base + RV1126_PMU_CLKSEL_CON(4) /* uart1 */);
	writel(0xffff0000, rv1126_pmucru_base + RV1126_PMU_CLKSEL_CON(5) /* uart1 */);
	writel(0x10000000, rv1126_cru_base + RV1126_CLKSEL_CON(67)); /* clk_core_npu */

	/* turn on all the PDs */
#define PMU_PWR_GATE_SFTCON     (0x110)
#define PMU_PWR_DWN_ST          (0x108)
#define PMU_BUS_IDLE_SFTCON(n)  (0xc0 + (n) * 4)
#define PMU_BUS_IDLE_ACK        (0xd0)
#define PMU_BUS_IDLE_ST         (0xd8)
	_printf("BAMBU REINIT: turning on PDs\n");
	writel(0xffffffff, rv1126_pmu_base + PMU_NOC_AUTO_CON0);
	writel(0xffffffff, rv1126_pmu_base + PMU_NOC_AUTO_CON1);

	writel(0xffff0000, rv1126_pmu_base + PMU_PWR_GATE_SFTCON);
	while (readl(rv1126_pmu_base + PMU_PWR_DWN_ST))
		udelay(1);
	writel(0xffff0000, rv1126_pmu_base + PMU_BUS_IDLE_SFTCON(0));
	writel(0xffff0000, rv1126_pmu_base + PMU_BUS_IDLE_SFTCON(1));
	while (readl(rv1126_pmu_base + PMU_BUS_IDLE_ACK))
		udelay(1);
	while (readl(rv1126_pmu_base + PMU_BUS_IDLE_ST))
		udelay(1);

	*(volatile uint32_t *)(rv1126_cru_base + 0x0404) = 0xffff0051; /* ??? */

#if 0
	/* uboot does this, we don't seem to need to: mux clocks to none-cpll */
	writel(0x00ff0003, rv1126_cru_base + CRU_CLKSEL_CON02);
	writel(0x00ff0005, rv1126_cru_base + CRU_CLKSEL_CON03);
	writel(0xffff8383, rv1126_cru_base + CRU_CLKSEL_CON27);
	writel(0x00ff0083, rv1126_cru_base + CRU_CLKSEL_CON31);
	writel(0x00ff0083, rv1126_cru_base + CRU_CLKSEL_CON33);
	writel(0xffff4385, rv1126_cru_base + CRU_CLKSEL_CON40);
	writel(0x00ff0043, rv1126_cru_base + CRU_CLKSEL_CON49);
	writel(0x00ff0003, rv1126_cru_base + CRU_CLKSEL_CON50);
	writel(0x00ff0003, rv1126_cru_base + CRU_CLKSEL_CON51);
	writel(0xff000300, rv1126_cru_base + CRU_CLKSEL_CON54);
	writel(0xff008900, rv1126_cru_base + CRU_CLKSEL_CON61);
	writel(0x00ff0089, rv1126_cru_base + CRU_CLKSEL_CON63);
	writel(0x00ff0045, rv1126_cru_base + CRU_CLKSEL_CON68);
	writel(0x00ff0043, rv1126_cru_base + CRU_CLKSEL_CON69);
#endif

	for (adp = kexecmod_resets; adp[1]; adp += 2) {
		void *adr;
		_printf("BAMBU REINIT: resetting %04x = %04x\n", adp[0], adp[1]);
		if (adp[0] & 0x8000) {
			adr = rv1126_pmucru_base + RV1126_PMU_SOFTRST_CON(adp[0] & 0x7FFF);
		} else {
			adr = rv1126_cru_base + RV1126_SOFTRST_CON(adp[0]);
		}
		for (i = 0; i < 16; i++) {
			if (((1 << i) & adp[1]) == 0) {
				continue;
			}
			writel(0x10001 << i, adr);
			udelay(50);
			writel(0x10000 << i, adr);
		}
	}

	_printf("BAMBU REINIT: actually going to go boot now, goodbye\n");
}

static int __init
kexecmod_arm_init(void)
{
	void *(*kallsyms_lookup_name)(const char *name) = (void *)ptr_kallsyms_lookup_name;
	
	if (!kallsyms_lookup_name) {
		printk(KERN_ERR "no kallsyms_lookup_name provided\n");
		return -ENOENT;
	}
	
#define DO_LOOKUP(s) \
	ptr_##s = kallsyms_lookup_name(#s); \
	if (!ptr_##s) { \
		printk(KERN_ERR "failed to kallsyms_lookup_name(" #s ")\n"); \
		return -ENOENT; \
	}
	
	DO_LOOKUP(memblock_is_region_memory);
	DO_LOOKUP(platform_can_cpu_hotplug);
	DO_LOOKUP(soft_restart);
	DO_LOOKUP(arch_phys_to_idmap_offset);
	arch_phys_to_idmap_offset = *ptr_arch_phys_to_idmap_offset;
	DO_LOOKUP(platform_can_secondary_boot);
	DO_LOOKUP(set_kernel_text_rw);
	DO_LOOKUP(set_all_modules_text_rw);
	DO_LOOKUP(patch_text);
	DO_LOOKUP(pl330_remove);
	
	kexec_reinit = kexec_reinit_bambu;
	
	return 0;
}

module_init(kexecmod_arm_init)

static void __exit
kexecmod_arm_exit(void)
{
}

module_exit(kexecmod_arm_exit);

module_param(ptr_kallsyms_lookup_name, uint, 0);
