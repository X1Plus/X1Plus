#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/fcntl.h>
#include <unistd.h>
#include <ifaddrs.h>

#ifdef __cplusplus
#define EXTERN_C extern "C"
#else
#define EXTERN_C
#endif

// annoyingly, we cannot just get this from dlfcn.h, because glibc version bad
# define RTLD_NEXT      ((void *) -1l)
extern
#ifdef __cplusplus
"C"
#endif
void *dlsym(void *handle, const char *symbol);

#define SWIZZLE(rtype, name, ...) \
    EXTERN_C rtype name(__VA_ARGS__) { \
        rtype (*next)(__VA_ARGS__) = (rtype(*)(__VA_ARGS__))dlsym(RTLD_NEXT, #name);

static short bogus = 31337;

SWIZZLE(int, getifaddrs, struct ifaddrs **ifap)
    int rv = next(ifap);
    if (rv)
        return rv;
    
    struct ifaddrs *ifa = *ifap;
    while (ifa) {
        if (!ifa->ifa_addr) {
            ifa->ifa_addr = (struct sockaddr *) &bogus;
        }
        ifa = ifa->ifa_next;
    }
    return 0;
}
