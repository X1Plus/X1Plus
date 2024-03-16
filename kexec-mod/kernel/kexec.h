
#undef CONFIG_FTRACE_SYSCALLS
#include <linux/syscalls.h>

#define CONFIG_KEXEC 1
#define CONFIG_KEXEC_CORE 1
#include <linux/kexec.h>

#undef  VMCOREINFO_SYMBOL
#define VMCOREINFO_SYMBOL(_) do {} while (0)

long sys_kexec_load(unsigned long entry, unsigned long nr_segments,
				struct kexec_segment __user *segments,
				unsigned long flags);
