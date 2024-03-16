/*
 * Arch-specific compatibility layer for enabling kexec as loadable kernel
 * module.
 *
 * Copyright (C) 2021 Fabian Mastenbroek.
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 */

#define pr_fmt(fmt) "kexec_mod_arm64: " fmt

#include <linux/version.h>
#include <linux/mm_types.h>
#include <linux/kexec.h>
#include <linux/kallsyms.h>
#include <linux/slab.h>
#include <asm/uaccess.h>
#include <asm/virt.h>

/* These kernel symbols need to be dynamically resolved at runtime
 * using kallsym due to them not being exposed to kernel modules */
static void (*cpu_do_switch_mm_ptr)(unsigned long, struct mm_struct *);
static void (*__flush_dcache_area_ptr)(void *, size_t);
static void (*__hyp_set_vectors_ptr)(phys_addr_t);

void cpu_do_switch_mm(unsigned long pgd_phys, struct mm_struct *mm)
{
	cpu_do_switch_mm_ptr(pgd_phys, mm);
}

void __flush_dcache_area(void *addr, size_t len)
{
	__flush_dcache_area_ptr(addr, len);
}

void __hyp_set_vectors(phys_addr_t phys_vector_base)
{
	__hyp_set_vectors_ptr(phys_vector_base);
}

void __hyp_set_vectors_nop(phys_addr_t phys_vector_base)
{}


/* These kernel symbols are stubbed since they are not available
 * in the host kernel */
bool cpus_are_stuck_in_kernel(void)
{
	return false;
}

#if LINUX_VERSION_CODE >= KERNEL_VERSION(4,12,0)
struct kimage *kexec_crash_image;

bool smp_crash_stop_failed(void)
{
	return false;
}

void crash_save_cpu(struct pt_regs *regs, int cpu)
{}

int set_memory_valid(unsigned long addr, int numpages, int enable)
{
	return 0;
}
#endif

#if LINUX_VERSION_CODE >= KERNEL_VERSION(4,14,0)
void crash_smp_send_stop(void)
{}
#elif LINUX_VERSION_CODE >= KERNEL_VERSION(4,12,0)
void smp_send_crash_stop(void)
{}
#endif

/* These symbols need to be resolved using by extracting their
 * addresses from symbols that are exposed to kernel modules */
u64 idmap_t0sz = TCR_T0SZ(VA_BITS);
u32 __boot_cpu_mode[2];

/**
 * This function initializes the __boot_cpu_mode variable with that from the kernel.
 * Since it is not exported, this requires some hacks.
 */
static int __init_cpu_boot_mode(void)
{
	extern phys_addr_t kexec_pa_symbol(void *ptr);
	/*
	 * Hack to obtain pointer to __boot_mode_cpu
	 * Our approach is to decode the address to __boot_mode_cpu from the instructions
	 * of set_cpu_boot_mode_flag which is exported and references __boot_mode_cpu.
	 */
	u32 *set_cpu_boot_mode_flag_ptr = (void *)kallsyms_lookup_name("set_cpu_boot_mode_flag");
	void *page = (void *) (((u64)set_cpu_boot_mode_flag_ptr) & ~0xFFF);
	u16 lo = (set_cpu_boot_mode_flag_ptr[0] >> 29) & 0x3;
	u16 hi = (set_cpu_boot_mode_flag_ptr[0] >> 4) & 0xFFFF;
	u16 off = (set_cpu_boot_mode_flag_ptr[1] >> 10) & 0xFFF;
	u32 *__boot_cpu_mode_ptr = page + ((hi << 13) | (lo << 12)) + off;

	/* Verify whether address actually exists */
	if (kexec_pa_symbol(__boot_cpu_mode_ptr)) {
		__boot_cpu_mode[0] = __boot_cpu_mode_ptr[0];
		__boot_cpu_mode[1] = __boot_cpu_mode_ptr[1];

		pr_info("Detected boot CPU mode: 0x%x 0x%x.\n", __boot_cpu_mode[0], __boot_cpu_mode[1]);
		return 0;
	}

	return -1;
}

static void *__hyp_shim;

/**
 * This function allocates a page which will contain the hypervisor shim.
 *
 * Previously, we set vbar_el2 to point directly to __hyp_shim_vectors.
 * However, we found that sometimes, the shim vectors would span two
 * non-consecutive physical pages, which would cause it to jump into unknown
 * memory.
 *
 * Our solution is to allocate a single page on which we place the hypervisor
 * shim in order to ensure that relative jumps without the MMU still work
 * properly.
 */
static int __init_hyp_shim(void)
{
	extern const u32 __hyp_shim_size;
	extern void __hyp_shim_vectors(void);

	__hyp_shim = alloc_pages_exact(__hyp_shim_size, GFP_KERNEL);

	if (!__hyp_shim) {
		return -ENOMEM;
	}

	memcpy(__hyp_shim, __hyp_shim_vectors, __hyp_shim_size);

	pr_info("Hypervisor shim created at 0x%llx [%u bytes].\n", virt_to_phys(__hyp_shim), __hyp_shim_size);
	return 0;
}


struct mm_struct init_mm;

static void __init_mm(void)
{
	/*
	 * Hack to obtain pointer to swapper_pg_dir (since it is not exported).
	 * However, we can find its physical address in the TTBR1_EL1 register
	 * and convert it to a logical address.
	 */
	u32 val;
	asm volatile("mrs %0, ttbr1_el1" : "=r" (val));
	init_mm.pgd = phys_to_virt(val);
}


static void *ksym(const char *name)
{
	return (void *) kallsyms_lookup_name(name);
}

int machine_kexec_compat_load(int detect_el2, int shim_hyp)
{
	if (!(cpu_do_switch_mm_ptr = ksym("cpu_do_switch_mm"))
	    || !(__flush_dcache_area_ptr = ksym("__flush_dcache_area")))
		return -ENOENT;

	/* Find __init_mm */
	__init_mm();

	/* Find boot CPU mode */
	__boot_cpu_mode[0] = BOOT_CPU_MODE_EL1;
	__boot_cpu_mode[1] = BOOT_CPU_MODE_EL1;

	if (!detect_el2) {
		pr_info("EL2 kexec not supported.\n");
	} else if (__init_cpu_boot_mode() < 0) {
		pr_warn("Failed to detect boot CPU mode.\n");
	}

	/* Enable shimming the hypervisor vectors */
	__hyp_set_vectors_ptr = __hyp_set_vectors_nop;
	if (shim_hyp) {
		pr_info("Enabling shim for hypervisor vectors.\n");

		if (__init_hyp_shim() < 0) {
			pr_err("Failed to initialize hypervisor shim.\n");
		} else if (detect_el2 && !(__hyp_set_vectors_ptr = ksym("__hyp_set_vectors"))) {
			pr_err("Not able to shim hypervisor vectors.\n");
			__hyp_set_vectors_ptr = __hyp_set_vectors_nop;
		} else if (!detect_el2) {
			pr_warn("Hypervisor shim unnecessary without EL2 detection.\n");
		}
	} else {
		__hyp_shim = NULL;
	}
	return 0;
}

void machine_kexec_compat_unload(void)
{
	extern const u32 __hyp_shim_size;

	if (__hyp_shim) {
		free_pages_exact(__hyp_shim, __hyp_shim_size);
		__hyp_shim = NULL;
	}
}

void machine_kexec_compat_prereset(void)
{
	__hyp_set_vectors(virt_to_phys(__hyp_shim));
}
