#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/fcntl.h>
#include <unistd.h>

// annoyingly, we cannot just get this from dlfcn.h, because glibc version bad
# define RTLD_NEXT      ((void *) -1l)
extern void *dlsym(void *handle, const char *symbol);

#define SWIZZLE(rtype, name, ...) \
    rtype name(__VA_ARGS__) { \
        rtype (*next)(__VA_ARGS__) = (rtype(*)(__VA_ARGS__))dlsym(RTLD_NEXT, #name);

SWIZZLE(int, open64, const char *s, int flag, int mode)
    if (!strcmp(s, "/dev/input/event3")) {
        s = "/dev/input/by-path/platform-gpio-keys-event";
    }
    return next(s, flag, mode);
}
