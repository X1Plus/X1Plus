#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/fcntl.h>
#include <unistd.h>
#include <stdarg.h>

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

typedef struct DBusError {
    const char *name;
    const char *message;
    unsigned int dummy1:1;
    unsigned int dummy2:1;
    unsigned int dummy3:1;
    unsigned int dummy4:1;
    unsigned int dummy5:1;
    void *padding1;
} DBusError;

typedef struct DBusConnection DBusConnection;
typedef struct DBusMessage DBusMessage;

extern "C" void dbus_error_init(DBusError *e);
extern "C" void dbus_error_free(DBusError *e);
extern "C" DBusConnection *dbus_bus_get(int type, DBusError *e);
extern "C" const char *dbus_bus_get_unique_name(DBusConnection *c);
extern "C" DBusMessage *dbus_message_new_signal(const char *path, const char *iface, const char *name);
extern "C" void dbus_message_unref(DBusMessage *msg);
extern "C" bool dbus_connection_send(DBusConnection *c, DBusMessage *msg, uint32_t *serial);
extern "C" bool dbus_message_append_args(DBusMessage *msg, int first_arg_type, ...);

static DBusConnection *_dbus_connection = NULL;

static void _publish_dbus_signal(const char *name, const char *bytes, int len) {
    if (!_dbus_connection) {
        DBusError e;
        dbus_error_init(&e);
        _dbus_connection = dbus_bus_get(1 /* DBUS_BUS_SYSTEM */, &e);
        if (!_dbus_connection) {
            printf("forward_shim: failed to connect to dbus: %s\n", e.message);
            dbus_error_free(&e);
            return;
        }
        printf("forward_shim: connected to dbus (I am %s)\n", dbus_bus_get_unique_name(_dbus_connection));
    }
    
    DBusMessage *msg = dbus_message_new_signal("/x1plus/forward", "x1plus.forward", name);
    if (bytes) {
        dbus_message_append_args(msg, (int) 'a' /* DBUS_TYPE_ARRAY */, (int) 'y' /* DBUS_TYPE_BYTE */, &bytes, len, (int) '\0' /* DBUS_TYPE_INVALID */);
    }
    dbus_connection_send(_dbus_connection, msg, NULL);
    dbus_message_unref(msg);
}

static int ttyS1_fd = -1;

SWIZZLE(int, open64, const char *s, int flag, ...)
    va_list ap;
    va_start(ap, flag);
    int mode = va_arg(ap, int);
    va_end(ap);

    int fd = next(s, flag, mode);
    if (!strcmp(s, "/dev/ttyS1")) {
        printf("forward_shim: opened /dev/ttyS1 as %d\n", fd);
        _publish_dbus_signal("MCSerialPortOpened", NULL, 0);
        ttyS1_fd = fd;
    }
    return fd;
}

SWIZZLE(ssize_t, write, int fd, const void *buf, size_t count)
    if (fd == ttyS1_fd) {
        _publish_dbus_signal("MCSerialPortWrite", (const char *) buf, count);
    }
    return next(fd, buf, count);
}