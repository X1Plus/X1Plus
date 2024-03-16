/*
 * ppc64 fdt fixups
 *
 * Copyright 2015 Freescale Semiconductor, Inc.
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation (version 2 of the License).
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 */

#include <arch/fdt.h>
#include <libfdt.h>
#include <stdio.h>
#include <stdlib.h>

/*
 * Let the kernel know it booted from kexec, as some things (e.g.
 * secondary CPU release) may work differently.
 */
static int fixup_kexec_prop(void *fdt)
{
	int err, nodeoffset;

	nodeoffset = fdt_subnode_offset(fdt, 0, "chosen");
	if (nodeoffset < 0)
		nodeoffset = fdt_add_subnode(fdt, 0, "chosen");
	if (nodeoffset < 0) {
		printf("%s: add /chosen %s\n", __func__,
		       fdt_strerror(nodeoffset));
		return -1;
	}

	err = fdt_setprop(fdt, nodeoffset, "linux,booted-from-kexec",
			  NULL, 0);
	if (err < 0) {
		printf("%s: couldn't write linux,booted-from-kexec: %s\n",
		       __func__, fdt_strerror(err));
		return -1;
	}

	return 0;
}


/*
 * For now, assume that the added content fits in the file.
 * This should be the case when flattening from /proc/device-tree,
 * and when passing in a dtb, dtc can be told to add padding.
 */
int fixup_dt(char **fdt, off_t *size)
{
	int ret;

	*size += 4096;
	*fdt = realloc(*fdt, *size);
	if (!*fdt) {
		fprintf(stderr, "%s: out of memory\n", __func__);
		return -1;
	}

	ret = fdt_open_into(*fdt, *fdt, *size);
	if (ret < 0) {
		fprintf(stderr, "%s: fdt_open_into: %s\n", __func__,
			fdt_strerror(ret));
		return -1;
	}

	ret = fixup_kexec_prop(*fdt);
	if (ret < 0)
		return ret;

	return 0;
}
