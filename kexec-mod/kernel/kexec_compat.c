/*
 * Arch-generic compatibility layer for enabling kexec as loadable kernel
 * module.
 *
 * Copyright (C) 2021 Fabian Mastenbroek.
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 */

#include <linux/version.h>
#include <linux/mm_types.h>
#include <linux/kexec.h>
#include <linux/kallsyms.h>
#include <linux/slab.h>
#include <asm/uaccess.h>
#include <asm/virt.h>

#include "kexec_compat.h"

/* These kernel symbols need to be dynamically resolved at runtime
 * using kallsym due to them not being exposed to kernel modules */
static void (*machine_shutdown_ptr)(void);
static void (*kernel_restart_prepare_ptr)(char*);
static void (*migrate_to_reboot_cpu_ptr)(void);
static void (*cpu_hotplug_enable_ptr)(void);

void machine_shutdown(void)
{
	machine_shutdown_ptr();
}

void kernel_restart_prepare(char *cmd)
{
	kernel_restart_prepare_ptr(cmd);
}

void migrate_to_reboot_cpu(void)
{
	migrate_to_reboot_cpu_ptr();
}

void cpu_hotplug_enable(void)
{
	cpu_hotplug_enable_ptr();
}


/* These kernel symbols are stubbed since they are not available
 * in the host kernel or not actually used for kexec */
#if LINUX_VERSION_CODE >= KERNEL_VERSION(4,2,0)
bool crash_kexec_post_notifiers;
#endif

#if LINUX_VERSION_CODE >= KERNEL_VERSION(4,5,0)
atomic_t panic_cpu;
#endif

#if LINUX_VERSION_CODE >= KERNEL_VERSION(4,11,0)
void printk_safe_flush_on_panic(void)
{}
#elif LINUX_VERSION_CODE >= KERNEL_VERSION(4,7,0)
void printk_nmi_flush_on_panic(void)
{}
#endif

#if LINUX_VERSION_CODE >= KERNEL_VERSION(4,12,0)
Elf_Word *append_elf_note(Elf_Word *buf, char *name, unsigned int type,
			              void *data, size_t data_len)
{
	return 0;
}

void final_note(Elf_Word *buf)
{}

void crash_save_vmcoreinfo(void)
{}

void crash_update_vmcoreinfo_safecopy(void *ptr)
{}
#endif

static void *ksym(const char *name)
{
	return (void *)kallsyms_lookup_name(name);
}

int kexec_compat_load()
{
	if (!(machine_shutdown_ptr = ksym("machine_shutdown"))
	    || !(migrate_to_reboot_cpu_ptr = ksym("migrate_to_reboot_cpu"))
	    || !(kernel_restart_prepare_ptr = ksym("kernel_restart_prepare"))
	    || !(cpu_hotplug_enable_ptr = ksym("cpu_hotplug_enable")))
		return -ENOENT;
	return 0;
}

void kexec_compat_unload(void)
{}
