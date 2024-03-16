#include "kexec.h"

#include <linux/version.h>
#include <linux/module.h>
#undef  module_init
#define module_init(initfn) __attribute__((unused)) static int initfn(void);

#undef pr_fmt
#include "orig/kexec.c"

#if LINUX_VERSION_CODE >= KERNEL_VERSION(4,3,0)
#undef pr_fmt
#include "orig/kexec_core.c"
#endif

#if LINUX_VERSION_CODE >= KERNEL_VERSION(4,20,0)
long sys_kexec_load(unsigned long entry, unsigned long nr_segments,
				struct kexec_segment __user *segments,
				unsigned long flags)
{
	return __do_sys_kexec_load(entry, nr_segments, segments, flags);
}
#endif

int panic_on_oops;

int insert_resource(struct resource *parent, struct resource *res) { return 0; }
