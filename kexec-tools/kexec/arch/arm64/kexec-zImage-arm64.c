/*
 * ARM64 kexec zImage (Image.gz) support.
 *
 * Several distros use 'make zinstall' rule inside
 * 'arch/arm64/boot/Makefile' to install the arm64
 * Image.gz compressed file inside the boot destination
 * directory (for e.g. /boot).
 *
 * Currently we cannot use kexec_file_load() to load vmlinuz
 * (or Image.gz).
 *
 * To support Image.gz, we should:
 * a). Copy the contents of Image.gz to a temporary file.
 * b). Decompress (gunzip-decompress) the contents inside the
 *     temporary file.
 * c). Pass the 'fd' of the temporary file to the kernel space.
 *
 * So basically the kernel space still gets a decompressed
 * kernel image to load via kexec-tools.
 */

#define _GNU_SOURCE

#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <stdlib.h>
#include "crashdump-arm64.h"
#include "image-header.h"
#include "kexec.h"
#include "kexec-arm64.h"
#include "kexec-syscall.h"
#include "kexec-zlib.h"
#include "arch/options.h"

#define FILENAME_IMAGE		"/tmp/ImageXXXXXX"

/* Returns:
 * -1 : in case of error/invalid format (not a valid Image.gz format.
 * fd : File descriptor of the temp file containing the decompressed
 *      Image.
 */
int zImage_arm64_probe(const char *kernel_buf, off_t kernel_size)
{
	int ret = -1;
	int fd = 0;
	int kernel_fd = 0;
	char *fname = NULL;
	char *kernel_uncompressed_buf = NULL;
	const struct arm64_image_header *h;

	if (!is_zlib_file(kernel_buf, &kernel_size)) {
		dbgprintf("%s: Not an zImage file (Image.gz).\n", __func__);
		return -1;
	}

	if (!(fname = strdup(FILENAME_IMAGE))) {
		dbgprintf("%s: Can't duplicate strings %s\n", __func__,
				fname);
		return -1;
	}

	if ((fd = mkstemp(fname)) < 0) {
		dbgprintf("%s: Can't open file %s\n", __func__,
				fname);
		ret = -1;
		goto fail_mkstemp;
	}

	kernel_uncompressed_buf =
		(char *) calloc(kernel_size, sizeof(off_t));
	if (!kernel_uncompressed_buf) {
		dbgprintf("%s: Can't calloc %ld bytes\n",
				__func__, kernel_size);
		ret= -ENOMEM;
		goto fail_calloc;
	}

	/* slurp in the input kernel */
	dbgprintf("%s: ", __func__);
	kernel_uncompressed_buf = slurp_decompress_file(kernel_buf,
							&kernel_size);

	/* check for correct header magic */
	if (kernel_size < sizeof(struct arm64_image_header)) {
		dbgprintf("%s: No arm64 image header.\n", __func__);
		ret = -1;
		goto fail_bad_header;
	}

	h = (const struct arm64_image_header *)(kernel_uncompressed_buf);

	if (!arm64_header_check_magic(h)) {
		dbgprintf("%s: Bad arm64 image header.\n", __func__);
		ret = -1;
		goto fail_bad_header;
	}

	if (write(fd, kernel_uncompressed_buf,
				kernel_size) != kernel_size) {
		dbgprintf("%s: Can't write the uncompressed file %s\n",
				__func__, fname);
		ret = -1;
		goto fail_bad_header;
	}

	close(fd);

	/* Open the tmp file again, this time in O_RDONLY mode, as
	 * opening the file in O_RDWR and calling kexec_file_load()
	 * causes the kernel to return -ETXTBSY
	 */
	kernel_fd = open(fname, O_RDONLY);
	if (kernel_fd == -1) {
		dbgprintf("%s: Failed to open file %s\n",
				__func__, fname);
		ret = -1;
		goto fail_bad_header;
	}

	unlink(fname);

	free(kernel_uncompressed_buf);
	free(fname);

	return kernel_fd;

fail_bad_header:
	free(kernel_uncompressed_buf);

fail_calloc:
	if (fd >= 0)
		close(fd);

	unlink(fname);

fail_mkstemp:
	free(fname);

	return ret;
}

int zImage_arm64_load(int argc, char **argv, const char *kernel_buf,
	off_t kernel_size, struct kexec_info *info)
{
	const struct arm64_image_header *header;
	unsigned long kernel_segment;
	int result;

	if (info->file_mode) {
		if (arm64_opts.initrd) {
			info->initrd_fd = open(arm64_opts.initrd, O_RDONLY);
			if (info->initrd_fd == -1) {
				fprintf(stderr,
					"Could not open initrd file %s:%s\n",
					arm64_opts.initrd, strerror(errno));
				result = EFAILED;
				goto exit;
			}
		}

		if (arm64_opts.command_line) {
			info->command_line = (char *)arm64_opts.command_line;
			info->command_line_len =
					strlen(arm64_opts.command_line) + 1;
		}

		return 0;
	}

	header = (const struct arm64_image_header *)(kernel_buf);

	if (arm64_process_image_header(header))
		return EFAILED;

	kernel_segment = arm64_locate_kernel_segment(info);

	if (kernel_segment == ULONG_MAX) {
		dbgprintf("%s: Kernel segment is not allocated\n", __func__);
		result = EFAILED;
		goto exit;
	}

	dbgprintf("%s: kernel_segment: %016lx\n", __func__, kernel_segment);
	dbgprintf("%s: text_offset:    %016lx\n", __func__,
		arm64_mem.text_offset);
	dbgprintf("%s: image_size:     %016lx\n", __func__,
		arm64_mem.image_size);
	dbgprintf("%s: phys_offset:    %016lx\n", __func__,
		arm64_mem.phys_offset);
	dbgprintf("%s: vp_offset:      %016lx\n", __func__,
		arm64_mem.vp_offset);
	dbgprintf("%s: PE format:      %s\n", __func__,
		(arm64_header_check_pe_sig(header) ? "yes" : "no"));

	/* create and initialize elf core header segment */
	if (info->kexec_flags & KEXEC_ON_CRASH) {
		result = load_crashdump_segments(info);
		if (result) {
			dbgprintf("%s: Creating eflcorehdr failed.\n",
								__func__);
			goto exit;
		}
	}

	/* load the kernel */
	add_segment_phys_virt(info, kernel_buf, kernel_size,
			kernel_segment + arm64_mem.text_offset,
			arm64_mem.image_size, 0);

	/* load additional data */
	result = arm64_load_other_segments(info, kernel_segment
		+ arm64_mem.text_offset);

exit:
	if (result)
		fprintf(stderr, "kexec: load failed.\n");
	return result;
}

void zImage_arm64_usage(void)
{
	printf(
"     An ARM64 zImage, compressed, big or little endian.\n"
"     Typically an Image.gz or Image.lzma file.\n\n");
}
