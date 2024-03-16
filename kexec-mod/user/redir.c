#include <stdarg.h>
#include <stdlib.h>
#include <stdio.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <sys/syscall.h>

#define LINUX_REBOOT_CMD_KEXEC 0x45584543

static long dev_kexec_ioctl(int cmd, void *arg)
{
	return ioctl(open("/dev/kexec", O_RDONLY), cmd, arg);
}

long syscall(long num, ...)
{
	if (num != SYS_kexec_load)
		abort();
	struct {
		long entry;
		long nsegs;
		void *segs;
		long flags;
	} ap;
	va_list va;
	va_start(va, num);
	ap.entry = va_arg(va, long);
	ap.nsegs = va_arg(va, long);
	ap.segs  = va_arg(va, void *);
	ap.flags = va_arg(va, long);
	va_end(va);
	return dev_kexec_ioctl(LINUX_REBOOT_CMD_KEXEC - 1, &ap);
}

int reboot(int cmd)
{
	if (cmd != LINUX_REBOOT_CMD_KEXEC)
		abort();
	return dev_kexec_ioctl(cmd, 0);
}
