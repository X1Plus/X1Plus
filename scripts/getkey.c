#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <dlfcn.h>

int main(int argc, char **argv)
{
    void *handle = dlopen("/usr/lib/libbbl_verify.so", RTLD_LAZY);
    if (!handle)
    {
        printf("%s\n", dlerror());
        return -1;
    }

    uint8_t *aes_key = dlsym(handle, "aes_key");
    if (!aes_key)
    {
        printf("%s\n", dlerror());
        return -1;
    }
    
    printf("UPDATE_KEY_MATERIAL=");
    for (int i = 0; i < 16; i++)
         printf("%02x", aes_key[i]);
     printf("\n");

    dlclose(handle);
        
    return 0;
}
