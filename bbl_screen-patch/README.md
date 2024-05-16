## Design guidelines

Here are some rough guidelines that we seem to be converging on:

* For icons, 128x128 SVGs with 8px wide lines seem about right.  I'm not
  sure what this ends up in screen space, someone can put it here if they
  figure it out.
* Info pages should be:
  * Pane edges should be 26px from the side of the screen
  * If they are two panes (info and buttons on left, detail on the right),
    the pane on the left should be 382px wide.
  * Panes should use the MarginPanel component, with their implicit radius.
  * Pane-to-pane margins should be 14px.
* Back buttons: ZButton with a 40px x 40px icon `../../icon/return.svg`
  * Arrow in the upper left corner of the page.  Refer to `BedMesh.qml` for proper positioning.
  * iconSize: 40, height,width: 80, cornerRadius:width/2
  * For pages with sub-pages, it is necessary to check pageStack.depth to ensure that the back
  button takes the user to the correct page. See `VibrationComp.qml` or `BedMesh.qml for examples`
* Scrollable items should have a scroll bar to show it.  Refer to
  `instrItem` in `VibrationComp.qml` for an example.

## Building it

You can build this with `make printer_ui.so` from the Docker environment; if
you want to do it outside of Docker, you're on your own.  If you're just
building it, the default configuration is probably what you want, but
otherwise, if you're doing heavy development, you probably want to set
`NO_AUTO_PATCH=yes` in your `localconfig.mk` to keep the patcher from
blowing away your changes; if you do that, after you `git pull`, do a `make
patch_printer_ui` to blow away the `printer_ui/` directory and regenerate it
from patches.

You should edit in `printer_ui/`, and then run `./patcher.py -g`, something like:
* `bbl_screen-patch$ ./patcher.py -g`
* edit patch diffs in your favorite editor to make sure you get
  what you actually want in there
* check into git

If you need to merge diffs, well, pray for mercy, and make sure that what
you have actually makes something coherent later.  After you merge
everything, you probably should run `./patcher.py -g` again to make sure
that the diffs actually line up.

There's a preset configuration in `.vscode` to use the
[Run on Save](https://marketplace.visualstudio.com/items?itemName=emeraldwalk.RunOnSave) extension
to automatically generate the patches to be checked into git on save.

## Testing it on a non-ARM host

This is sort of a mess too!  You should first get a rootfs from your
printer, and either extract it or mount it somewhere; I will call that place
`$ROOTFS`.  I will also call the checkout of your `x1plus` folder
`$X1PLUS`.

The first thing you will want to do is create a fake `/config`.  Try
something like:

```
X1PLUS$ mkdir -p fakeroot/config/screen
X1PLUS$ cat > fakeroot/config/screen/printer.json
{
    "carbon": false,
    "carbonStartup": false,
    "dryFilament": "TPU",
    "lang": "en",
    "license_approved": true,
    "night": true,
    "power_mode": 1,
    "preset_history": [
    ],
    "screws": false,
    "sdcard_history": [
    ],
    "version_info": {
        "ahb_new_version_number": "",
        "ams_new_version_number": "",
        "force_upgrade": false,
        "hasPendingNotify": false,
        "new_version_state": 2,
        "ota_new_version_number": ""
    },
    "wizard": true
}
```

Now you can con `bbl_screen` into letting you get past initial setup.

Then, build a `printer_ui.so` (hope you got that working above!), and cd
into your rootfs's /usr/bin folder, and run:

```
EMULATION_WORKAROUNDS=$X1PLUS/fakeroot/ \
QML2_IMPORT_PATH=$ROOTFS/usr/qml \
qemu-arm \
-E LD_PRELOAD=$X1PLUS/bbl_screen-patch/printer_ui.so \
-E LD_LIBRARY_PATH=$X1PLUS/images/cfw/usr/lib/ \
-L $ROOTFS \
./bbl_screen -platform vnc:size=1280x720
```

Finally, once `bbl_screen` starts, you can `vncviewer localhost` in another
window to talk to your emulated `bbl_screen`.

