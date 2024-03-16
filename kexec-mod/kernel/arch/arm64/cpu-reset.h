/*
 * CPU reset routines
 *
 * Copyright (C) 2015 Huawei Futurewei Technologies.
 * Copyright (C) 2021 Fabian Mastenbroek.
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License version 2 as
 * published by the Free Software Foundation.
 */

#ifndef _ARM64_CPU_RESET_H
#define _ARM64_CPU_RESET_H

#include <linux/version.h>

#include <asm/pgtable.h>
#include <asm/sysreg.h>
#include <asm/virt.h>

#include "idmap.h"
#include "machine_kexec_compat.h"

void __cpu_soft_restart(unsigned el2_switch,
	unsigned long entry, unsigned long arg0, unsigned long arg1,
	unsigned long arg2);

#if LINUX_VERSION_CODE < KERNEL_VERSION(4,19,0)
static void __noreturn cpu_soft_restart(unsigned long el2_switch,
	unsigned long entry, unsigned long arg0, unsigned long arg1,
	unsigned long arg2)
{
#else
static void __noreturn cpu_soft_restart(unsigned long entry,
					unsigned long arg0,
					unsigned long arg1,
					unsigned long arg2)
{
	/* arm64: kexec: always reset to EL2 if present (76f4e2da) */
	unsigned long el2_switch = 1;
#endif
	typeof(__cpu_soft_restart) *restart;

	el2_switch = el2_switch && !is_kernel_in_hyp_mode() &&
		is_hyp_mode_available();

	restart = (void *)kexec_pa_symbol(__cpu_soft_restart);

	/* Shim the hypervisor vectors for HYP_SOFT_RESTART support if enabled */
	machine_kexec_compat_prereset();

	/* Install identity mapping */
	kexec_idmap_install();

	restart(el2_switch, entry, arg0, arg1, arg2);
	unreachable();
}

#endif
