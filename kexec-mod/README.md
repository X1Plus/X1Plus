# kexec-mod-arm64
Kexec as loadable kernel module for Linux ARM64 kernels based on
[kexec-module](https://github.com/amonakov/kexec-module).

## Purpose
This loadable kernel module enables users of Linux kernels without built-in
Kexec support to still make use of Kexec functionality. For instance, you may
use this module to boot to a more recent kernel if you are unable to replace
the boot image.

## Building
The project is comprised of two parts:

- `kernel/` contains the Linux kernel module that exposes Kexec functionality
via `/dev/kexec`.
- `user/` contains a helper library that allows the use of an unpatched
`kexec-tools`.

### Pre-requisites
Make sure you have installed the necessary packages for building Linux kernel
modules on your system (e.g., `make` and `gcc`).

### Kernel module
Enter the `kernel` directory and export the path to the Linux kernel sources
against you wish to build:

```bash
cd kernel/
```
Then, build the module using `make`:
```bash
make KDIR=/path/to/linux
```
This will build `kexec_mod.ko` and `kexec_mod_$ARCH.ko` which can be loaded
into the Linux kernel.

### User-space helper
Enter the `user` directory and build the helper as follows:
```bash
make
```
This will build `redir.so` that acts as an `LD_PRELOAD` interposer for Kexec
syscalls, allowing the use of unpatched `kexec-tools`.

## Usage
Make sure you have built the module and user-space helper. Also check whether you
have installed `kexec-tools`. Then, you can use `kexec-tools` as follows:

```bash
LD_PRELOAD=/root/redir.so kexec -l /boot/vmlinuz --reuse-cmdline
LD_PRELOAD=/root/redir.so kexec -e
```

## License
The code is released under the GPLv2 license. See [COPYING.txt](/COPYING.txt).
