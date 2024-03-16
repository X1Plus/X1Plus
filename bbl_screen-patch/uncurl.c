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

struct curl_slist {
    char *data;
    struct curl_slist *next;
};

SWIZZLE(int, curl_easy_setopt, void *hnd, int opt, void *p)
    if (opt == 10002) {
        printf("uncurl: request for url %s\n", p);
        if (strstr(p, "api.bambulab.com")) {
            printf("uncurl: disallowing request to api.bambulab.com\n");
            p = "http://localhost/";
        }
    }
    
    return next(hnd, opt, p);
}

SWIZZLE(FILE *, popen, const char *command, const char *type)
    if (strstr(command, "updateEngine")) {
        printf("uncurl: call to updateEngine is disallowed\n");
        return NULL;
    }
    return next(command, type);
}

int _Z15is_factory_modev() {
    return 1;
}
