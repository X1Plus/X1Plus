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

#if defined(FIRMWARE_00_00_32_18)
#  define OFS_ETH_VTABLE   0xA1FA8
#  define OFS_ETH_VTABLE_0 0x56A4C
#  define OFS_ETH_VTABLE_1 0x56A64
#  define OFS_ETH_VTABLE_2 0x63434 /* not for us? */
#  define OFS_ETH_VTABLE_3 0x56AD4
#  define OFS_ETH_VTABLE_4 0x56AD8
#  define OFS_CREATE_INTERFACES 0x49D3C
#  define CREATE_INTERFACES_SIZE_1 0x380
#  define OFS_CTOR_INTERFACE 0x6F988
#  define OFS_SET_ADD_STRING_MAYBE 0x5A948
#  define OFS_VTABLE_NETINTERFACECARD 0xA1FC4
#  define OFS_CTOR_NETINTERFACECARD 0x28F94
#  define OFS_SpCountedBase_M_RELEASE 0x3108c
#  define OFS_NIC_init_dev 0x2E810
#  define OFS_create_net_thread 0x287B0
#  define OFS_ctor_size_218 0x5a948
#elif defined(FIRMWARE_00_00_32_39)
#  define OFS_ETH_VTABLE    0xA2734
#  define OFS_ETH_VTABLE_0  0x56B5C
#  define OFS_ETH_VTABLE_1  0x56B74
#  define OFS_ETH_VTABLE_2  0x63608 /* not for us? */
#  define OFS_ETH_VTABLE_3  0x56BE4
#  define OFS_ETH_VTABLE_4  0x56BE8
#  define OFS_CREATE_INTERFACES 0x49e4c
#  define CREATE_INTERFACES_SIZE_1 0x380
#  define OFS_CTOR_INTERFACE  0x6fb60
#  define OFS_SET_ADD_STRING_MAYBE 0x5aa58
#  define OFS_VTABLE_NETINTERFACECARD 0xA2750
#  define OFS_CTOR_NETINTERFACECARD 0x28F94
#  define OFS_SpCountedBase_M_RELEASE 0x31170
#  define OFS_NIC_init_dev 0x2e8f4
#  define OFS_create_net_thread 0x287b0
#  define OFS_ctor_size_218 0x8779c
#else
#  error no offsets defined for this firmware?
#endif

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
	OFS_ETH_VTABLE_0,
	OFS_ETH_VTABLE_1,
	(unsigned int) sub_57D50,
	OFS_ETH_VTABLE_3,
	OFS_ETH_VTABLE_4
};

static int create_interfaces(int thiz)
{	
	int v3 = thiz + 0x18C;

	syslog(6, "%s", "create_interfaces");

	unsigned int *wlan_ptr = (unsigned int *)operator new(CREATE_INTERFACES_SIZE_1);
	wlan_ptr[0] = OFS_ETH_VTABLE;
	wlan_ptr[1] = 1;
	wlan_ptr[2] = 1;
	
	{
	std::string iface = "wlan0";
	((void (*)(int, std::string &)) OFS_CTOR_INTERFACE)((int)(wlan_ptr + 4), iface);
	}

	{
	std::string iface = "wlan0";
	unsigned int *v4 = ((unsigned int *(*)(int, std::string &)) OFS_SET_ADD_STRING_MAYBE)(v3, iface);

	unsigned int *v5 = (unsigned int *)operator new(0x130);
	v5[0] = OFS_VTABLE_NETINTERFACECARD;
	v5[1] = 1;
	v5[2] = 1;

	((void (*)(int)) OFS_CTOR_NETINTERFACECARD)((int)(v5 + 4));

	unsigned int *v6 = (unsigned int *)v4[1];
	v4[0] = (unsigned int) (v5 + 4);
	v4[1] = (unsigned int) v5;

	if (v6)
		((void (*)(unsigned int *)) OFS_SpCountedBase_M_RELEASE)(v6);
	}

	{
	std::string iface = "wlan0";
	unsigned int v7 = *((unsigned int *(*)(int, std::string &)) OFS_SET_ADD_STRING_MAYBE)(v3, iface);
	unsigned int *v12[2];
	v12[0] = wlan_ptr + 4;
	v12[1] = wlan_ptr;
	
        __gnu_cxx::__exchange_and_add_dispatch((int *) &wlan_ptr[1], 1);

        ((void (*)(unsigned int, unsigned int **)) OFS_NIC_init_dev)(v7, v12);
	if (v12[1])
		((void (*)(unsigned int *)) OFS_SpCountedBase_M_RELEASE)(v12[1]);
	}
	
	{
	std::string iface = "wlan0";
	unsigned int *v10 = ((unsigned int *(*)(int, std::string &)) OFS_SET_ADD_STRING_MAYBE)(v3, iface);

	((void (*)(unsigned int)) OFS_create_net_thread)(*v10);
	}

	(*(void (**)(unsigned int *))(wlan_ptr[4] + 40))(wlan_ptr + 4);
	((void (*)(unsigned int *)) OFS_SpCountedBase_M_RELEASE)(wlan_ptr);
	
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
	unsigned int *v21 = ((unsigned int *(*)(int, std::string &)) OFS_ctor_size_218)(v3, iface);

	unsigned int *v14 = (unsigned int *)operator new(0x130);
	v14[0] = OFS_VTABLE_NETINTERFACECARD;
	v14[1] = 1;
	v14[2] = 1;
	((void (*)(int)) OFS_CTOR_NETINTERFACECARD)((int)(v14 + 4));
	
	unsigned int *v15 = (unsigned int *)v21[1];
	v21[0] = (unsigned int) (v14 + 4);
	v21[1] = (unsigned int) v14;
	
	if (v15)
		((void (*)(unsigned int *)) OFS_SpCountedBase_M_RELEASE)(v15);
	}

	{
	std::string iface = "eth0";
	unsigned int v16 = *((unsigned int *(*)(int, std::string &)) OFS_SET_ADD_STRING_MAYBE)(v3, iface);
	unsigned int *v22[2];
	v22[0] = eth_ptr + 4;
	v22[1] = eth_ptr;
	
        __gnu_cxx::__exchange_and_add_dispatch((int *) &eth_ptr[1], 1);

        ((void (*)(unsigned int, unsigned int **)) OFS_NIC_init_dev)(v16, v22);
	if (v22[1])
		((void (*)(unsigned int *)) OFS_SpCountedBase_M_RELEASE)(v22[1]);
	}
	
	{
	std::string iface = "eth0";
	unsigned int *v19 = ((unsigned int *(*)(int, std::string &)) OFS_ctor_size_218)(v3, iface);

	((void (*)(unsigned int)) OFS_create_net_thread)(*v19);
	}

	(*(void (**)(unsigned int *))(eth_ptr[4] + 40))(eth_ptr + 4);

	((void (*)(unsigned int *)) OFS_SpCountedBase_M_RELEASE)(eth_ptr);	
	
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
	if (memcmp((void *)OFS_CREATE_INTERFACES, expect_insns, 12)) {
		fprintf(stderr, "*** NETSERVICE DOES NOT HAVE EXPECTED BYTE SEQUENCE.  FIRMWARE HAS CHANGED; YOU MUST UPDATE netService_shim.cpp.\n");
		abort();
	}

	mprotect((void *)((long)OFS_CREATE_INTERFACES & ~(sysconf(_SC_PAGESIZE) - 1)), sysconf(_SC_PAGESIZE), PROT_READ | PROT_WRITE | PROT_EXEC);
	
	((uint32_t *)OFS_CREATE_INTERFACES)[0] = 0xE59F1000;
	((uint32_t *)OFS_CREATE_INTERFACES)[1] = 0xE12FFF11;
	((uint32_t *)OFS_CREATE_INTERFACES)[2] = (uint32_t)create_interfaces;
}
