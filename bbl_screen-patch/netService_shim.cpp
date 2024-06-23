// ../../gcc-linaro-6.3.1-2017.05-x86_64_arm-linux-gnueabihf/bin/arm-linux-gnueabihf-gcc -shared -fPIC shim.cpp -ldl -o libnetService_shim.so
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <dlfcn.h>
#include <string>
#include <stdarg.h>
#include <link.h>
#include <sys/mman.h>
#include <unistd.h>
#include <syslog.h>

#if 0
extern "C" void syslog(int priority, const char *format, ...)
{
	va_list va;

	va_start(va, format);
	vprintf(format, va);
	printf("\n");
	va_end(va);
}
#endif

void sub_57D50(unsigned int *a1)
{
	printf("!!!!!!!!!!!!!!! sub_57D50 !!!!!!!!!!!!!");
	exit(0);
}

unsigned int eth_vtbl[] =
{
	0x00056A4C,
	0x00056A64,
	(unsigned int) sub_57D50,
	0x00056AD4,
	0x00056AD8
};

static int create_interfaces(int thiz)
{	
	int v3 = thiz + 0x18C;

	syslog(6, "%s", "create_interfaces");

	unsigned int *wlan_ptr = (unsigned int *)operator new(0x380);
	wlan_ptr[0] = 0xA1FA8;
	wlan_ptr[1] = 1;
	wlan_ptr[2] = 1;
	
	{
	std::string iface = "wlan0";
	((void (*)(int, std::string &)) 0x6F988)((int)(wlan_ptr + 4), iface);
	}

	{
	std::string iface = "wlan0";
	unsigned int *v4 = ((unsigned int *(*)(int, std::string &)) 0x5A948)(v3, iface);

	unsigned int *v5 = (unsigned int *)operator new(0x130);
	v5[0] = 0xA1FC4;
	v5[1] = 1;
	v5[2] = 1;

	((void (*)(int)) 0x28F94)((int)(v5 + 4));

	unsigned int *v6 = (unsigned int *)v4[1];
	v4[0] = (unsigned int) (v5 + 4);
	v4[1] = (unsigned int) v5;

	if (v6)
		((void (*)(unsigned int *)) 0x3108C)(v6);
	}

	{
	std::string iface = "wlan0";
	unsigned int v7 = *((unsigned int *(*)(int, std::string &)) 0x5A948)(v3, iface);
	unsigned int *v12[2];
	v12[0] = wlan_ptr + 4;
	v12[1] = wlan_ptr;
	
        __gnu_cxx::__exchange_and_add_dispatch((int *) &wlan_ptr[1], 1);

        ((void (*)(unsigned int, unsigned int **)) 0x2E810)(v7, v12);
	if (v12[1])
		((void (*)(unsigned int *)) 0x3108C)(v12[1]);
	}
	
	{
	std::string iface = "wlan0";
	unsigned int *v10 = ((unsigned int *(*)(int, std::string &)) 0x5A948)(v3, iface);

	((void (*)(unsigned int)) 0x287B0)(*v10);
	}

	(*(void (**)(unsigned int *))(wlan_ptr[4] + 40))(wlan_ptr + 4);
	((void (*)(unsigned int *)) 0x3108C)(wlan_ptr);
	
	syslog(6, "%s", "[NetService::create_interfaces] enable wired network");
	
	unsigned int *eth_ptr = (unsigned int *)operator new(0x218);
	eth_ptr[0] = (unsigned int) eth_vtbl;
	eth_ptr[1] = 1;
	eth_ptr[2] = 1;
	
	{
	std::string iface = "eth0";
	((void (*)(int, std::string &)) 0x875C4)((int)(eth_ptr + 4), iface);
	}

	{
	std::string iface = "eth0";
	unsigned int *v21 = ((unsigned int *(*)(int, std::string &)) 0x5A948)(v3, iface);

	unsigned int *v14 = (unsigned int *)operator new(0x130);
	v14[0] = 0xA1FC4;
	v14[1] = 1;
	v14[2] = 1;
	((void (*)(int)) 0x28F94)((int)(v14 + 4));
	
	unsigned int *v15 = (unsigned int *)v21[1];
	v21[0] = (unsigned int) (v14 + 4);
	v21[1] = (unsigned int) v14;
	
	if (v15)
		((void (*)(unsigned int *)) 0x3108C)(v15);
	}

	{
	std::string iface = "eth0";
	unsigned int v16 = *((unsigned int *(*)(int, std::string &)) 0x5A948)(v3, iface);
	unsigned int *v22[2];
	v22[0] = eth_ptr + 4;
	v22[1] = eth_ptr;
	
        __gnu_cxx::__exchange_and_add_dispatch((int *) &eth_ptr[1], 1);

        ((void (*)(unsigned int, unsigned int **)) 0x2E810)(v16, v22);
	if (v22[1])
		((void (*)(unsigned int *)) 0x3108C)(v22[1]);
	}
	
	{
	std::string iface = "eth0";
	unsigned int *v19 = ((unsigned int *(*)(int, std::string &)) 0x5A948)(v3, iface);

	((void (*)(unsigned int)) 0x287B0)(*v19);
	}

	(*(void (**)(unsigned int *))(eth_ptr[4] + 40))(eth_ptr + 4);

	((void (*)(unsigned int *)) 0x3108C)(eth_ptr);	
	
	return 0;
}

extern "C" void __attribute__ ((constructor)) init() {
	unsetenv("LD_PRELOAD");
	
	/* expected prologue to 0x49d3c */
	uint32_t expect_insns[] = {
		0xe92d4ff0,
		0xe3019ce8,
		0xe340900c
	};
	if (memcmp((void *)0x49d3c, expect_insns, 12)) {
		fprintf(stderr, "*** NETSERVICE DOES NOT HAVE EXPECTED BYTE SEQUENCE.  FIRMWARE HAS CHANGED; YOU MUST UPDATE netService_shim.cpp.\n");
		abort();
	}

	mprotect((void *)((long)0x00049D3C & ~(sysconf(_SC_PAGESIZE) - 1)), sysconf(_SC_PAGESIZE), PROT_READ | PROT_WRITE | PROT_EXEC);
	
	*(uint32_t *) 0x00049D3C = 0xE59F1000;
	*(uint32_t *) 0x00049D40 = 0xE12FFF11;
	*(uint32_t *) 0x00049D44 = (uint32_t)create_interfaces;
}
