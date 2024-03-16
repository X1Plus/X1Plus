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

#ifndef LINUX_KEXEC_COMPAT_H
#define LINUX_KEXEC_COMPAT_H

/**
 * Load the kexec compatibility layer.
 */
int kexec_compat_load(void);

/**
 * Unload the kexec compatbility layer.
 */
void kexec_compat_unload(void);

#endif /* LINUX_KEXEC_COMPAT_H */
