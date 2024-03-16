# X1Plus

## Installation instructions

*Welcome to X1Plus!*  If you're a user, you probably want to [go straight to
the wiki](https://github.com/X1Plus/X1Plus/wiki), which tells you everything
you need to know about installing and using X1Plus on your printer.

The rest of this file has boring stuff for really big nerds who want to
develop X1Plus.

## Development instructions

Ok, don't say I didn't warn you.  Anyway, hi!  Glad you're interested in
contributing to X1Plus!  Here is a bunch of information on how to build it,
how it's structured internally, and various things you might need to know
about how to make changes and how to contribute back.  X1Plus is the result
of a year or so of vaguely-structured work; it started life as a fairly
frumious hack, and over the past few months, we've been working hard to try
to clean it up for release to the outside world.  All that said, there are
parts that you will find are still a mess, and for that, we're truly sorry! 
We hope you'll come play around with it anyway.  There's a lot of fun stuff
to be done, and we have only barely scratched the surface so far.

### How do I get started?

Probably the easiest way to get started building X1Plus is in a Docker
container.  If you're adventurous, you can probably build X1Plus on any old
Linux machine (I do), but if you do that and it breaks, we really don't want
to hear about it, so you really should just build it in Docker.  You'll need
the filesystem decryption key from a live printer (running either X1Plus or
the Official Rootable Firmware) in order to build X1Plus; try something
like:

```
$ git clone ...
$ cd X1Plus
$ docker build -t x1plusbuild scripts/docker/
$ docker run -u `id -u` -v `pwd`:/work x1plusbuild bash -c 'git config --global --add safe.directory /work'
$ docker run -u `id -u` -v `pwd`:/work x1plusbuild make scripts
$ scp scripts/getkey root@bambu:/tmp
$ ssh root@bambu /tmp/getkey >> localconfig.mk
$ docker run -u `id -u` -v `pwd`:/work x1plusbuild make
```

With some luck, you should get a `.x1p` file in your working directory!  You
can copy that to your SD card (`scp` it over -- never remove an SD card from
a live X1Plus system, you goofball), reboot your printer, and install it
from the menu.

If you're going to make changes to any of the UI files, you should really
read the rest of this document...  otherwise you might be in for a nasty
surprise next time you `git pull`.

### How does X1Plus work, from the printer's perspective?

The core concept of X1Plus is that we build an overlay on top of the Bambu
Lab firmware, and replace only the parts that we need in order to launch
X1Plus.  We are very careful not to redistribute any of Bambu Lab's IP
directly; when it's necessary to use or patch Bambu Lab binaries, we
download them directly from Bambu Lab servers, and then patch them onboard
the printer.  We also try to be pretty careful to leave the printer in a
"fail-safe" state by modifying as little of the on-printer flash as
possible.  Below is a rough flow of how X1Plus works, from installer through
to normal boot.

**Host-side installer.**  The host-side installer is an Electron app that
wraps all the logic to check whether the printer is running a supported
version of the base firmware, and that wraps the mechanics of logging into
the printer over MQTT, over FTP, and over SSH.  (In development versions of
X1Plus that relied on exploits to install, the PC-side installer was
somewhat more complicated!)  Roughly, this is implemented in
`installer-clientside/install-gui/src/index.ts`.

The installer copies an `.x1p` image to the SD card, as well as a small
tarball containing the on-printer install GUI stub.  It SSHes to the
printer, unpacks the tarball into `/userdata` on the printer, and runs a
first-stage installer launch script that it (hopefully) unpacked; then, it
waits for MQTT messages that indicate the progress of the installation.

**First-stage install scripts.**  The first-stage installer (implemented in
`installer-clientside/stage1/x1plus/launch.sh`) first shuts down the
printer's service checker (otherwise, the GUI would get restarted!), and
then shuts down the GUI.  It drops a marker for the host-side installer to
indicate that it has started up, and then relaunches the printer's GUI
engine with X1Plus's setup GUI injected into it to replace the normal
printer GUI.

**X1Plus setup GUI.** The precise mechanism by which we inject code into the
GUI is interesting, but it is somewhat getting ahead of ourselves to discuss
it exactly at this moment :) I'll talk about that in a moment.  For now, all
you really need to know is that this is implemented in QML, with
`bbl_screen-patch/kexec_ui/printerui/qml/Screen.qml` as the initial item
(the C++ native components live in `bbl_screen-patch/interpose.cpp`).  As
you might suspect from the name, this GUI is also part of the X1Plus boot
process, but the first-stage installer launches it in such a way that the
GUI goes straight into the installer screen.  The installer mechanism, the
`SelectX1pPage`, looks for `.x1p` images on the SD card, and asks the user
which `x1p` to install.  (An `x1p` is just a zip file that has an
`info.json` and a `payload.tar.gz` in it.) Once the user chooses an `x1p`
file, `InstallingPage` unpacks the `payload.tar.gz` into `/userdata`,
invokes the Python-based install backend, and begins listening for DDS
messages with status updates.  (DDS is an internal pubsub message bus.)

**Python install backend.** The mechanics of what the Python installer does
is probably better served by reading the code for it, which is in
`installer/install.py`.  We drop a precompiled version of Python into
`/userdata`, and to communicate with the DDS message bus, we use `ctypes` to
talk to the DDS system libraries.  Roughly, the Python installer:

* checks to make sure that the printer's device tree is known and
  compatible;
* backs up a few printer configuration objects to the SD card;
* downloads an original firmware from Bambu Lab;
* decrypts it and decompresses it, unpacks the ext2 filesystem image, and
  then repacks that filesystem as a squashfs on the SD card;
* creates an ext4 loopback file on the SD card;
* copies an overlay squashfs and a kernel to the SD card;
* writes a bootloader stub to the printer's internal filesystem;
* and reports success, and offers to reboot.

(You can read the details of each of those in the Python installer itself.)
When installation is complete, the printer reboots into the slightly
modified internal filesystem.

**On boot: SD card check and GUI display.** When the printer powers up, it
boots first into the onboard eMMC installation, as normal.  We inject a
shell script into `/etc/init.d/S75kexec`, which subsequently launches
`/opt/kexec/check_kexec`.  (Both of these scripts live in `internal-fs/` in
this tree.) This script checks an "emergency override" (engaged by pressing
and holding the POWER and ESTOP buttons while powering the printer up), and
if those buttons are pressed, it quits as quickly as possible to return
control to the internal printer firmware.  Otherwise, it launches the same
GUI as was used in the X1Plus Setup process above, and offers to either boot
into SD card firmware or run advanced options.  (Because it was launched
from the actual boot process, the `dialog/KexecDialog` is presented, rather
than the `SelectX1pPage`.)  If the user chooses to boot from the SD card,
the shell script `/opt/kexec/boot` runs and prepares to boot the printer
into the new kernel.

**kexec'ing into the new world.**  Things start getting weird here, and
fast.  The net result of this stage is that we are going to reboot the
printer into a custom-compiled kernel.  The process of doing so is rather
unusual; because we can't convince the first-stage bootloader on the system
to do our bidding (the kernel is signed from that perspective), we need to
hot-reboot.  We perform the following steps in order to do this.

* First, we hash the running kernel's device tree (or, at least, keys of it
  that we care about) to make sure that we have an appropriate device tree
  for the kernel that we are going to jump into.  We have a somewhat
  modified device tree; since we want to patch in the printer's serial
  number and similar things, we compile it at runtime using a `dtc` that we
  have on the printer.  (This also chooses the correct includes to make sure
  we light up the correct one of four possible LCD panels that the printer
  could come with.)
* We prepare a few other parameters for the new kernel, and its userspace,
  including what we currently think the printer's serial number is, and
  which filesystems we will want to mount when we come back up.
* Now we start getting a little bit creative.  We want to use `kexec`, but
  the Bambu Lab kernel does not have `kexec` built in; worse, `kexec` is
  nominally only available as a compiled-in option, so we can't compile a
  module for it from kernel sources.  Luckily for us, there have been a
  series of attempts to make this work -- originally, [amonakov's
  `kexec-module`](https://github.com/amonakov/kexec-module), and
  subsequently, [fabianishere's
  `kexec-mod-arm64`](https://github.com/fabianishere/kexec-mod)!  We build
  on this work in `kexec-mod/`, where we port this kernel module to ARM32. 
  Much of the Rockchip SoC gets astonishingly angry if hot-rebooted; we very
  carefully reset large chunks of the SoC's state in
  `kexec-mod/kernel/arch/arm/machine_kexec_drv.c`.  To get access to many of
  the symbols we need, even if they are not `EXPORT_SYMBOL`, we bootstrap
  with `kallsyms_lookup_name` (which we, uh, grab from `/proc/kallsyms`).
* We load a kernel from the SD card, load our compiled device tree, load an
  initramfs from the SD card, and then have `kexec` do its thing; away we
  go, sailing into the New World.

**Setting up the overlays in the initramfs.**  Once the new kernel boots,
the first userspace code that executes is an initramfs, with init being a
shellscript that lives, oddly enough, in `initramfs/init`.  We start off by
painting a cute logo, and setting a larger font on screen.  Then, roughly,
we:

* Mount the SD card.  It should be FAT32; with particularly slow SD cards,
  it might take a bit to enumerate.
* Mount each of the base layers.  At compile and install time, we build a
  bunch of squashfses: a Bambu Lab base image, a custom firmware overlay,
  and a GUI patch overlay.
* Mount the persistent overlay storage layer, which is an ext4fs that lives
  in a file on the FAT32 partition.
* Create an overlay that stacks up each of these into a single root
  partition.  Bind the overlay around as needed, and then...
* Transfer control to the "real" `init` process.

At the moment that `init` gets control, the filesystem looks like this:

```
/             # Combined root filesystem, including all layers.
/mnt/sdcard   # SD card mount moved to be a subtree of the new root.
/mnt/rootfs   # Access to the "real" root filesystem, so that kernel drivers can see it if needed.
/mnt/overlay  # tmpfs containing individual overlay layers, including:
/mnt/overlay/00.00.28.55.squashfs    # Repacked Bambu base filesystem
/mnt/overlay/1.0.squashfs            # Precompiled X1Plus filesystem
/mnt/overlay/bbl_screen-1.0.squashfs # Patched bbl_screen image
```

**Booting the OS.**  OS boot is mostly unremarkable, but we do override some
components of the base system.  See `images/cfw/etc/init.d/` for bits and
pieces that we override.

**Launching the patched GUI.**  Here is the other sort of "interesting and
creative" bit of X1Plus: how we patch the GUI.  Our general goal is that we
wish to redistribute as little of Bambu Lab's IP as possible, and instead,
only redistribute our own modifications to it.  The mechanics of this is all
handled by `bbl_screen-patch/`, which ultimately spits out a `printer_ui.so`
that gets `LD_PRELOAD`ed into `bbl_screen`.  Here is the rough process from
start to finish of how that happens; most of it happens at build time:

* We start by extracting all of the Qt resources from the original
  `bbl_screen`.  We do this by statically looking up all of the callsites of
  `qInitResources`, and then using the Unicorn Engine to emulate the
  instructions leading up to them.  Once we know the arguments to each call
  of `qInitResources`, we know the in-memory locations of each resource
  bundle, and we traverse the Qt resource bundle hierarchy to extract each
  bundle to its constituent files, and a `root.qrc` that can be later used
  to recompile a resource bundle.  This all happens in `extract_qrc.py`.
* Once we have unpacked the resource bundle to the `printer_ui-orig`
  directory, we copy it to a new directory, and apply all of the patches in
  the `patches/` folder, using `patcher.py`.  This creates a `printer_ui/`
  with our new GUI bundle.
* We then compile a resource bundle with `rcc`.  We also compile an
  interposer that will intercept the appropriate call to `qInitResources`
  and replace it with our resource bundle, as well as adding a handful of
  other helpful C++ classes; this lives in `interpose.cpp`, which is at
  least lightly commented.  All of these get linked together into a
  `printer_ui.so`.
* Because the `printer_ui.so` has a meaningful amount of original Bambu Lab
  IP in it, we do not want to redistribute this directly; instead, we
  distribute an `xdelta`-encoded patch from the original `bbl_screen`, which
  we reassemble into a `printer_ui.so` at install time.

At last, you have a beautiful X1Plus splash screen!

### How does the X1Plus build system work?

This probably could use a fair bit more discussion, but in short, you should
be able to just `make`.  I would describe it better, but it is really quite
embarrassing.  The Electron installer app really is not integrated into the
build system yet, and if you intend to hack on that, you should probably ask
about it if you cannot decipher it already.

One thing to think about is that, by default, `bbl_screen-patch/Makefile`
will overwrite the `printer_ui` directory if it believes that the `patches`
directory has changed.  This is great if you are just building from git, but
if you are actually trying to make changes to the `printer_ui`, this is
rather surprising behavior.  To avoid this, you can put `NO_AUTO_PATCH=yes`
in your `localconfig.mk`.

You almost certainly want to build in Docker.

### How do I contribute?

For better or for worse, we do most of our development discussion in
Discord.  Because of how much of a pain it is to merge `printer_ui` patches,
please let other people know what you're working on!

We work with pull requests and bug reports on GitHub.  Please reserve bug
reports for actually triaged -- or, if not triaged, triageable -- bugs; if
you have usage questions, please talk about those in "Discussions"!

Please be reasonable human beings to each other.  It is just a 3D printer. 
If you have a problem, please chat with some of the maintainers and we will
try to help you resolve it.

### Who is X1Plus?

X1Plus was written by a small number of people, not all of whom wish to be
publicly identified.  You might see a handful names around the code from
people who don't mind sharing their identity, but there were many more
people behind the scenes who have contributed over time!

### Miscellaneous stuff

This probably ought go into a wiki page, but, you know, here we are.

#### Building a kernel

As of writing, it's not necessary to build a kernel image yourself as there's one present in
`prebuilt`. But you can! This might be desirable to enable other kernel features for development, 
or to build a kernel module against.

* Install prerequestites, including `lz4` for compressing the final image.
* Install the appropriate toolchain.
* Grab the latest kernel source from [our
repository](https://github.com/X1Plus/x1-linux-kernel).
* Ensure the toolchain is on your PATH, and add LDFLAGS/CCFLAGS to point to the toolchain (unsure
how necessary this is):
  ```
  export LDFLAGS="-L$TOOLCHAIN/gcc/linux-x86/arm/gcc-linaro-6.3.1-2017.05-x86_64_arm-linux-gnueabihf \
  -Larm-linux-gnueabihf/libc/usr/lib/ -L/usr/arm-linux-gnueabihf/lib/"
  export CCFLAGS="-I$TOOLCHAIN/include -I/usr/include"
  ```
* From the root of kernel folder, run `make ARCH=arm CROSS_COMPILE=arm-linux-gnueabihf- 
O=build x1plus_defconfig`
* Run `make mrproper`
* CD into `build`
* Run `sed -i 's/YYLTYPE yylloc/extern YYLTYPE yylloc/' ./scripts/dtc/dtc-lexer.lex.c`
* Run `make ARCH=arm CROSS_COMPILE=arm-linux-gnueabihf- zImage` to build the kernel.
  * You probably want to add `-jn` where `n` is the number of threads (logical cores) you have available
  to dramatically speed up building (using all threads may slow down OS).
  * Build output file is `arch/arm/boot/zImage` you can copy this over `prebuilt/kernel` to use it with this repo.
