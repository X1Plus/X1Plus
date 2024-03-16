/*
 * kexec_mod_arm64: Kexec driver for ARM64.
 *
 * Copyright (C) 2021 Fabian Mastenbroek.
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 */

#define MODULE_NAME "kexec_mod_arm64"
#define pr_fmt(fmt) MODULE_NAME ": " fmt

#include <linux/module.h>

#include "machine_kexec_compat.h"
#include "idmap.h"

MODULE_LICENSE("GPL v2");
MODULE_AUTHOR("Fabian Mastenbroek <mail.fabianm@gmail.com>");
MODULE_DESCRIPTION("Kexec backport as Kernel Module for ARM64");
MODULE_VERSION("1.1");

static int detect_el2 = 1;
module_param(detect_el2, int, 0);
MODULE_PARM_DESC(detect_el2,
		 "Attempt to detect EL2 mode (default = 1)");

static int shim_hyp = 0;
module_param(shim_hyp, int, 0);
MODULE_PARM_DESC(shim_hyp,
		 "Shim the HYP_SOFT_RESTART call for EL2 mode (default = 0)");

static int __init
kexecmod_arm64_init(void)
{
	int err;

	/* Load compatibility layer */
	if ((err = machine_kexec_compat_load(detect_el2, shim_hyp)) != 0) {
		pr_err("Failed to load: %d\n", err);
		return err;
	}

	/* Build identity map for MMU */
	kexec_idmap_setup();

	return 0;
}

module_init(kexecmod_arm64_init)

static void __exit
kexecmod_arm64_exit(void)
{
	/* Unload compatibility layer */
	machine_kexec_compat_unload();
}

module_exit(kexecmod_arm64_exit);
