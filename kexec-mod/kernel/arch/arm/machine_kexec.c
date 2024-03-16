#include "../../kexec.h"
#include "orig/machine_kexec.c"

EXPORT_SYMBOL_GPL(machine_kexec);
EXPORT_SYMBOL_GPL(machine_kexec_prepare);
EXPORT_SYMBOL_GPL(machine_kexec_cleanup);
EXPORT_SYMBOL_GPL(machine_crash_shutdown);
