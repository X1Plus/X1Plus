/*
 * Identity paging setup for kexec_mod.
 *
 * Copyright (C) 2021 Fabian Mastenbroek.
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 */

#ifndef KEXEC_IDMAP_H
#define KEXEC_IDMAP_H

phys_addr_t kexec_pa_symbol(void *ptr);

void kexec_idmap_setup(void);

void kexec_idmap_install(void);

#endif /* KEXEC_IDMAP_H */
