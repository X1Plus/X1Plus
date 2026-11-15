import QtQuick 2.12
import QtQuick.Controls 2.12
import UIBase 1.0
import Printer 1.0
import X1PlusNative 1.0

import ".."
import "../models"
import "qrc:/uibase/qml/widgets"
import "../X1Plus.js" as X1Plus

BaseTabPage {
    property bool hadVisible: false
    onVisibleChanged: {
        DeviceManager.activeDeviceInfos(DeviceManager.DI_Storage, visible)
        if (!visible) return
        if (stack.depth === 1 && !hadVisible) {
            activePage = keys[ModelManager.perferSource]
            hadVisible = true
        }
    }
    id: tab
    subdir: "models"
    // USB drives only plug into an Expander, so only show the USB tab when there is one
    pages: [
        { name: "Preset", title: qsTr("Internal") },
        { name: "Sdcard", title: qsTr("SD Card") },
    ].concat(X1Plus.Expansion.hardware() !== null ? [{ name: "Usb", title: qsTr("USB") }] : [])
     .concat([{ name: "SdcardCache", title: qsTr("Print Cache") }])
    property var keys: UIBase.enumKeys("ModelManager", "Source")
    pageHandler: function handle() {
        if (activePage === "Usb") {
            usbOverlay.visible = true;
            if (stack) stack.enabled = false;
            if (usbCurrentPath !== "") usbNavigateTo(usbCurrentPath);
            return true;
        }
        usbOverlay.visible = false;
        if (stack) stack.enabled = true;
        usbSelectedPath = "";
        usbSelectedMeta = null;
        if (stack.depth == 1)
            ModelManager.source = keys.indexOf(tab.activePage)
        if (stack && stack.depth === 2)
           stack.pop();
    }
    Component.onCompleted: {
        activePage = "ModelList"
        pageIndicator.currentIndex = -1
    }

    // ── USB state ──────────────────────────────────────────────────────────
    property var _usbState: X1Plus.Expansion.usb()
    property var usbMounts: {
        var m = (_usbState && _usbState.mounts) ? _usbState.mounts.slice() : [];
        m.sort(function(a, b) {
            var pa = (a.usb_port || a.mount_point || "").toUpperCase();
            var pb = (b.usb_port || b.mount_point || "").toUpperCase();
            return pa < pb ? -1 : pa > pb ? 1 : 0;
        });
        return m;
    }
    property string usbCurrentPath: ""
    property string usbRootPath: ""
    property var usbEntries: []
    property var usbMetaCache: ({})
    property string usbSelectedPath: ""
    property var usbSelectedMeta: null

    // UsbChanged also fires when free space changes, so only refresh when a drive is plugged in or pulled
    property string _usbMountKey: ""
    onUsbMountsChanged: {
        var key = usbMounts.map(function(m) { return m.mount_point; }).join("|");
        if (key === _usbMountKey) return;
        _usbMountKey = key;
        if (usbMounts.length === 0) {
            usbCurrentPath = "";
            usbRootPath = "";
            usbEntries = [];
            usbMetaCache = {};
            usbSelectedPath = "";
            usbSelectedMeta = null;
        } else if (usbRootPath === "" || usbMounts.findIndex(function(m) { return m.mount_point === usbRootPath; }) < 0) {
            usbMetaCache = {};
            // Pick the first drive with a print on it, the other one might just be for SD offload
            var pick = usbMounts.find(function(m) { return usbHasPrintable(m.mount_point, 3); }) || usbMounts[0];
            usbRootPath = pick.mount_point;
            usbNavigateTo(pick.mount_point);
        } else {
            usbMetaCache = {};
            usbNavigateTo(usbCurrentPath);
        }
    }

    function usbIsPrintable(e) {
        return !e.isDir && e.name.charAt(0) !== '.' && e.name.toLowerCase().endsWith('.gcode.3mf');
    }

    // Only show folders that have a print in them (up to 2 levels down), this hides empty
    // folders and the SD offload ones
    function usbHasPrintable(path, depth) {
        try {
            return JSON.parse(X1PlusNative.listDir(path)).some(function(e) {
                if (usbIsPrintable(e)) return true;
                return e.isDir && depth > 0 && e.name.charAt(0) !== '.' && e.name !== "System Volume Information"
                    && usbHasPrintable(path + "/" + e.name, depth - 1);
            });
        } catch(e) {
            return false;
        }
    }

    // Remembers which folders have prints so the 5s refresh doesn't rescan everything,
    // cleared when you change folders
    property var usbDirHasPrints: ({})

    function usbNavigateTo(path, refresh) {
        if (!refresh) usbDirHasPrints = {};
        usbCurrentPath = path;
        usbSelectedPath = "";
        usbSelectedMeta = null;
        try {
            usbEntries = JSON.parse(X1PlusNative.listDir(path)).filter(function(e) {
                if (e.isDir) {
                    if (e.name.charAt(0) === '.' || e.name === "System Volume Information") return false;
                    var dir = path + "/" + e.name;
                    if (!(dir in usbDirHasPrints)) usbDirHasPrints[dir] = usbHasPrintable(dir, 2);
                    return usbDirHasPrints[dir];
                }
                return usbIsPrintable(e);
            });
        } catch(e) {
            usbEntries = [];
        }
    }

    // Print again from the finish dialog opens the same file and plate back up
    property var usbReprint: X1Plus.usbReprint()
    onUsbReprintChanged: {
        if (!usbReprint) return;
        var req = usbReprint;
        X1Plus.setUsbReprint(null);
        var mount = usbMounts.find(function(m) { return req.path.indexOf(m.mount_point + "/") === 0; });
        if (!mount) return; // Drive was unplugged, just show the list
        usbRootPath = mount.mount_point;
        var dir = req.path.substring(0, req.path.lastIndexOf("/"));
        usbNavigateTo(dir);
        if (!usbEntries.some(function(e) { return dir + "/" + e.name === req.path; })) return; // File is gone, just show the list
        usbSelectedPath = req.path;
        usbSelectedMeta = usbGetMeta(req.path);
        usbDetail.selectedPlate = req.plate;
    }

    function usbGetMeta(fullPath) {
        if (usbMetaCache[fullPath] !== undefined)
            return usbMetaCache[fullPath];
        var meta = { thumbnail: "", timeEstimate: 0, weightEstimate: 0.0 };
        try {
            meta = JSON.parse(X1PlusNative.parseGcodeMetadata(fullPath));
        } catch(e) {}
        usbMetaCache[fullPath] = meta;
        return meta;
    }

    Timer {
        interval: 5000
        running: usbOverlay.visible && usbSelectedPath === ""
        repeat: true
        onTriggered: { if (usbCurrentPath !== "") usbNavigateTo(usbCurrentPath, true); }
    }

    // ── USB overlay ────────────────────────────────────────────────────────
    Item {
        id: usbOverlay
        visible: false
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.topMargin: barHeight
        anchors.bottom: parent.bottom
        z: 10

        Rectangle {
            anchors.fill: parent
            color: Colors.gray_700
        }

        UsbListPage {
            anchors.fill: parent
            anchors.margins: 16
            visible: usbSelectedPath === ""
            drives: tab.usbMounts
            rootPath: tab.usbRootPath
            currentPath: tab.usbCurrentPath
            entries: tab.usbEntries
            getMeta: function(p) { return tab.usbGetMeta(p); }
            onNavigateTo: function(path) { tab.usbNavigateTo(path); }
            onRootSelected: function(path) { tab.usbRootPath = path; tab.usbNavigateTo(path); }
            onFileSelected: function(path) {
                tab.usbSelectedPath = path;
                tab.usbSelectedMeta = tab.usbGetMeta(path);
            }
        }

        UsbDetailPage {
            id: usbDetail
            anchors.fill: parent
            visible: usbSelectedPath !== ""
            selectedPath: tab.usbSelectedPath
            selectedMeta: tab.usbSelectedMeta
            dialogStack: dialogStack
            onBackClicked: {
                tab.usbSelectedPath = "";
                tab.usbSelectedMeta = null;
            }
            onPrintClicked: function(payload) {
                X1Plus.lastUsbPrint = { path: tab.usbSelectedPath, plate: usbDetail.selectedPlate, subtask: payload.subtask_name };
                X1Plus.DDS.publish("device/request/print", payload);
                navigator.activePage = "Home";
            }
        }
    }
}
