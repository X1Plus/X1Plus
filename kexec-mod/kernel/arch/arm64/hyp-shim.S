/*
 * Hypervisor stub shim
 *
 * Copyright (C) 2012 ARM Ltd.
 * Author:	Marc Zyngier <marc.zyngier@arm.com>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License version 2 as
 * published by the Free Software Foundation.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

#include <linux/init.h>
#include <linux/version.h>
#include <linux/linkage.h>
#include <linux/irqchip/arm-gic-v3.h>

#include <asm/assembler.h>
#include <asm/kvm_asm.h>
#include <asm/esr.h>
#include <asm/ptrace.h>
#include <asm/virt.h>

	.text
	.align 11

ENTRY(__hyp_shim_vectors)
	ventry	el2_sync_invalid		// Synchronous EL2t
	ventry	el2_irq_invalid			// IRQ EL2t
	ventry	el2_fiq_invalid			// FIQ EL2t
	ventry	el2_error_invalid		// Error EL2t

	ventry	el2_sync_invalid		// Synchronous EL2h
	ventry	el2_irq_invalid			// IRQ EL2h
	ventry	el2_fiq_invalid			// FIQ EL2h
	ventry	el2_error_invalid		// Error EL2h

	ventry	el1_sync_shim			// Synchronous 64-bit EL1
	ventry	el1_irq_invalid			// IRQ 64-bit EL1
	ventry	el1_fiq_invalid			// FIQ 64-bit EL1
	ventry	el1_error_invalid		// Error 64-bit EL1

	ventry	el1_sync_invalid		// Synchronous 32-bit EL1
	ventry	el1_irq_invalid			// IRQ 32-bit EL1
	ventry	el1_fiq_invalid			// FIQ 32-bit EL1
	ventry	el1_error_invalid		// Error 32-bit EL1
ENDPROC(__hyp_shim_vectors)

	.align 11

el1_sync_shim:
	mrs	x30, esr_el2
	lsr	x30, x30, #ESR_ELx_EC_SHIFT

	cmp	x30, #ESR_ELx_EC_HVC64
	b.ne	2f				// Not an HVC trap

	cbz	x0, 1f
	msr	vbar_el2, x0			// Set vbar_el2
	b	2f

1:	mrs	x0, vbar_el2			// Return vbar_el2

2:	cmp	x0, #HVC_SOFT_RESTART
	b.ne	3f
	mov	x0, x2
	mov	x2, x4
	mov	x4, x1
	mov	x1, x3
	br	x4				// no return

	/* Someone called kvm_call_hyp() against the hyp-stub... */
#if LINUX_VERSION_CODE < KERNEL_VERSION(4,12,0)
3:	mov	x0, #ARM_EXCEPTION_HYP_GONE
#else
3:	ldr	x0, =HVC_STUB_ERR
#endif

9:	eret
ENDPROC(el1_sync_shim)

.macro invalid_vector	label
\label:
	b \label
ENDPROC(\label)
.endm

	invalid_vector	el2_sync_invalid
	invalid_vector	el2_irq_invalid
	invalid_vector	el2_fiq_invalid
	invalid_vector	el2_error_invalid
	invalid_vector	el1_sync_invalid
	invalid_vector	el1_irq_invalid
	invalid_vector	el1_fiq_invalid
	invalid_vector	el1_error_invalid

/**
 * __hyp_shim_size - Number of bytes to copy to the hyp shim page.
 */
.globl __hyp_shim_size
__hyp_shim_size:
	.quad	__hyp_shim_size - __hyp_shim_vectors
