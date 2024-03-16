#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <sys/ioctl.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>

#define _ALIGN_UP_MASK(addr, mask)   (((addr) + (mask)) & ~(mask))
#define _ALIGN_DOWN_MASK(addr, mask) ((addr) & ~(mask))

/* align addr on a size boundary - adjust address up/down if needed */
#define _ALIGN_UP(addr, size)	     \
	_ALIGN_UP_MASK(addr, (typeof(addr))(size) - 1)
#define _ALIGN_DOWN(addr, size)	     \
	_ALIGN_DOWN_MASK(addr, (typeof(addr))(size) - 1)

/* align addr on a size boundary - adjust address up if needed */
#define _ALIGN(addr, size)     _ALIGN_UP(addr, size)


#define LINUX_REBOOT_CMD_KEXEC_OLD	0x81726354
#define LINUX_REBOOT_CMD_KEXEC_OLD2	0x18263645
#define LINUX_REBOOT_CMD_KEXEC		0x45584543

struct kexec_segment;

struct kexec_segment {
	const void *buf;
	size_t bufsz;
	const void *mem;
	size_t memsz;
};


static long dev_kexec_ioctl(int cmd, void *arg)
{
	return ioctl(open("/dev/kexec", O_RDONLY), cmd, arg);
}

#define LINUX_REBOOT_CMD_KEXEC 0x45584543

int xreboot(int cmd)
{
	if (cmd != LINUX_REBOOT_CMD_KEXEC)
		abort();
	return dev_kexec_ioctl(cmd, 0);
}

static inline long kexec_load(void *entry, unsigned long nr_segments,
			struct kexec_segment *segments, unsigned long flags)
{
	struct {
		long entry;
		long nsegs;
		void *segs;
		long flags;
	} ap;
	ap.entry = (long)entry;
	ap.nsegs = nr_segments;
	ap.segs  = segments;
	ap.flags = flags;
	return dev_kexec_ioctl(LINUX_REBOOT_CMD_KEXEC - 1, &ap);
}

int main(int argc, char **argv) {
	char *argv0 = argv[0];
	if (argc < 3) {
		fprintf(stderr, "%s: usage: %s ENTRY_POINT (LOAD_ADDR FILE_NAME)+\n", argv0, argv0);
		return 1;
	}
	
	uint32_t entry = strtol(argv[1], NULL, 0);
	argc--;
	argv++;
	
	int nsegs = argc / 2;
	struct kexec_segment *segs = malloc(nsegs * sizeof(struct kexec_segment));
	for (int i = 0; i < nsegs; i++) {
		segs[i].mem = (void *)strtol(argv[1], NULL, 0);
		int fd = open(argv[2], O_RDONLY);
		if (fd < 0) {
			perror("open");
			return 2;
		}
		segs[i].bufsz = lseek(fd, 0, SEEK_END);
		segs[i].memsz = _ALIGN(segs[i].bufsz, getpagesize());
		lseek(fd, 0, SEEK_SET);
		segs[i].buf = malloc(segs[i].bufsz);
		read(fd, (void *)segs[i].buf, segs[i].bufsz);
		close(fd);
		fprintf(stderr, "%s: loaded %ld bytes to %p from %s\n", argv0, segs[i].bufsz, segs[i].mem, argv[2]);
		argc -= 2;
		argv += 2;
	}
	int rv = kexec_load((void *)entry, nsegs, segs, 0);
	if (rv < 0) {
		perror("kexec_load");
		return 1;
	}
}