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

#define MODULE_NAME "kexec_mod_arm64"
#define pr_fmt(fmt) MODULE_NAME ": " fmt

#include <asm/pgtable.h>
#include <asm/mmu_context.h>

#include "idmap.h"

#ifdef CONFIG_ARM64_64K_PAGES
#define IDMAP_BLOCK_SHIFT	PAGE_SHIFT
#define IDMAP_BLOCK_SIZE	PAGE_SIZE
#define IDMAP_TABLE_SHIFT	PMD_SHIFT
#else
#define IDMAP_BLOCK_SHIFT	SECTION_SHIFT
#define IDMAP_BLOCK_SIZE	SECTION_SIZE
#define IDMAP_TABLE_SHIFT	PUD_SHIFT
#endif

#define block_index(addr) (((addr) >> IDMAP_BLOCK_SHIFT) & (PTRS_PER_PTE - 1))
#define block_align(addr) (((addr) >> IDMAP_BLOCK_SHIFT) << IDMAP_BLOCK_SHIFT)

/*
 * Initial memory map attributes.
 */
#ifndef CONFIG_SMP
#define PTE_FLAGS	PTE_TYPE_PAGE | PTE_AF
#define PMD_FLAGS	PMD_TYPE_SECT | PMD_SECT_AF
#else
#define PTE_FLAGS	PTE_TYPE_PAGE | PTE_AF | PTE_SHARED
#define PMD_FLAGS	PMD_TYPE_SECT | PMD_SECT_AF | PMD_SECT_S
#endif

#ifdef CONFIG_ARM64_64K_PAGES
#define MM_MMUFLAGS	PTE_ATTRINDX(MT_NORMAL) | PTE_FLAGS
#else
#define MM_MMUFLAGS	PMD_ATTRINDX(MT_NORMAL) | PMD_FLAGS
#endif

pgd_t kexec_idmap_pg_dir[PTRS_PER_PGD] __attribute__ ((aligned (4096)));
pte_t kexec_idmap_pt[2 * PTRS_PER_PTE] __attribute__ ((aligned (4096)));

extern void __cpu_soft_restart(unsigned el2_switch,
	unsigned long entry, unsigned long arg0, unsigned long arg1,
	unsigned long arg2);

void kexec_idmap_setup(void)
{
	int i;
	unsigned long pa, pdx;
	pte_t *pmd, *next_pmd = kexec_idmap_pt;
	void *ptrs[4] = {kexec_idmap_pg_dir,
			 kexec_idmap_pt,
			 kexec_idmap_pt + PTRS_PER_PTE,
			 __cpu_soft_restart};

	/* Clear the idmap page table */
	memset(kexec_idmap_pg_dir, 0, sizeof(kexec_idmap_pg_dir));
	memset(kexec_idmap_pt, 0, sizeof(kexec_idmap_pt));

	for (i = 0; i < sizeof(ptrs) / sizeof(ptrs[0]); i++) {
		pa = kexec_pa_symbol(ptrs[i]);
		pdx = pgd_index(pa);

		if (pgd_val(kexec_idmap_pg_dir[pdx])) {
			pmd = (void *) phys_to_virt(pgd_val(kexec_idmap_pg_dir[pdx]) & ~0xFFF);
		} else {
			pr_info("Created new idmap page table for 0x%lx\n", pa);

			pmd = next_pmd;
			next_pmd += PTRS_PER_PTE;
			kexec_idmap_pg_dir[pdx] = __pgd(kexec_pa_symbol(pmd) | PMD_TYPE_TABLE);
		}

		pmd[block_index(pa)] = __pte(block_align(pa) | MM_MMUFLAGS);
	}
}

void kexec_idmap_install(void)
{
	cpu_set_reserved_ttbr0();
	flush_tlb_all();
	cpu_set_idmap_tcr_t0sz();

	cpu_do_switch_mm(kexec_pa_symbol(kexec_idmap_pg_dir), &init_mm);
}

/**
 * Resolve the physical address of the specified pointer.
 * We cannot use __pa_symbol for symbols defined in our kernel module, so we need to walk
 * the page manually.
 */
phys_addr_t kexec_pa_symbol(void *ptr)
{
	unsigned long va = (unsigned long) ptr;
	unsigned long page_offset;
	pgd_t *pgd;
	pud_t *pud;
	pmd_t *pmd;
	pte_t *ptep, pte;
	struct page *page = NULL;

	pgd = pgd_offset_k(va);
	if (pgd_none(*pgd) || pgd_bad(*pgd)) {
		return 0;
	}

	pud = pud_offset(pgd , va);
	if (pud_none(*pud) || pud_bad(*pud)) {
		return 0;
	}

	pmd = pmd_offset(pud, va);
	if (pmd_none(*pmd) || pmd_bad(*pmd)) {
		return 0;
	}

	ptep = pte_offset_map(pmd, va);
	if (!ptep) {
		return 0;
	}

	pte = *ptep;
	pte_unmap(ptep);
	page = pte_page(pte);
	page_offset = va & ~PAGE_MASK;
	return page_to_phys(page) | page_offset;
}
