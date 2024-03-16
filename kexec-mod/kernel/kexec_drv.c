/*
 * kexec_mod: Kexec functionality as loadable kernel module.
 *
 * Copyright (C) 2021 Fabian Mastenbroek.
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 */

#define MODULE_NAME "kexec_mod"
#define pr_fmt(fmt) MODULE_NAME ": " fmt

#include <linux/module.h>
#include <linux/err.h>
#include <linux/fs.h>
#include <linux/sysfs.h>
#include <linux/device.h>
#include <linux/reboot.h>

#include <uapi/linux/stat.h>

#include "kexec_compat.h"
#include "kexec.h"

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Fabian Mastenbroek <mail.fabianm@gmail.com>");
MODULE_DESCRIPTION("Kexec backport as Kernel Module");
MODULE_VERSION("1.1");

static unsigned int ptr_kallsyms_lookup_name = 0;
static long long *ptr_arch_phys_to_idmap_offset;
long long arch_phys_to_idmap_offset;

unsigned long kallsyms_lookup_name(const char *name) {
	unsigned long (*xkallsyms_lookup_name)(const char *name) = (void *)ptr_kallsyms_lookup_name;
	return xkallsyms_lookup_name(name);
}

static ssize_t kexecmod_loaded_show(struct kobject *kobj,
		  		    struct kobj_attribute *attr, char *buf)
{
	extern struct kimage *kexec_image;
	return sprintf(buf, "%d\n", !!kexec_image);
}

static struct kobj_attribute kexec_loaded_attr = __ATTR(kexec_loaded, S_IRUGO, kexecmod_loaded_show, NULL);

static long kexecmod_ioctl(struct file *file, unsigned req, unsigned long arg)
{
	struct {
		unsigned long entry;
		unsigned long nr_segs;
		struct kexec_segment *segs;
		unsigned long flags;
	} ap;
	switch (req) {
	case LINUX_REBOOT_CMD_KEXEC - 1:
		if (copy_from_user(&ap, (void*)arg, sizeof ap))
			return -EFAULT;
		return sys_kexec_load(ap.entry, ap.nr_segs, ap.segs, ap.flags);
	case LINUX_REBOOT_CMD_KEXEC:
		return kernel_kexec();
	}
	return -EINVAL;
}

static const struct file_operations fops = {
	.owner = THIS_MODULE,
	.unlocked_ioctl = kexecmod_ioctl,
};

int kexec_maj;
struct class *kexec_class;
struct device *kexec_device;
dev_t kexec_dev;

static int __init
kexecmod_init(void)
{
	int err;

	if (!ptr_kallsyms_lookup_name) {
		printk(KERN_ERR "no kallsyms_lookup_name provided\n");
		return -ENOENT;
	}
#define DO_LOOKUP(s) \
	ptr_##s = (void *)kallsyms_lookup_name(#s); \
	if (!ptr_##s) { \
		printk(KERN_ERR "failed to kallsyms_lookup_name(" #s ")\n"); \
		return -ENOENT; \
	}
	DO_LOOKUP(arch_phys_to_idmap_offset);
	arch_phys_to_idmap_offset = *ptr_arch_phys_to_idmap_offset;
	
	/* Load compatibility layer */
	if ((err = kexec_compat_load()) != 0) {
		pr_err("Failed to load: %d\n", err);
		return err;
	}

	/* Register character device at /dev/kexec */
	kexec_maj = register_chrdev(0, "kexec", &fops);
	if (kexec_maj < 0)
		return kexec_maj;
	kexec_class = class_create(THIS_MODULE, "kexec");
	if (IS_ERR(kexec_class))
		return PTR_ERR(kexec_class);
	kexec_dev = MKDEV(kexec_maj, 0);
	kexec_device = device_create(kexec_class, 0, kexec_dev, 0, "kexec");
	if (IS_ERR(kexec_device))
		return PTR_ERR(kexec_device);

	/* Register sysfs object */
	err = sysfs_create_file(kernel_kobj, &(kexec_loaded_attr.attr));

	pr_info("Kexec functionality now available at /dev/kexec.\n");

	return 0;
}

module_init(kexecmod_init)

static void __exit
kexecmod_exit(void)
{
	pr_info("Stopping...\n");

	/* Unload compatibility layer */
	kexec_compat_unload();

	/* Destroy character device */
	device_destroy(kexec_class, kexec_dev);
	class_destroy(kexec_class);
	unregister_chrdev(kexec_maj, "kexec");

	/* Remove sysfs object */
	sysfs_remove_file(kernel_kobj, &(kexec_loaded_attr.attr));
}

module_exit(kexecmod_exit);
module_param(ptr_kallsyms_lookup_name, uint, 0);
