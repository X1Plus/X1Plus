import QtQuick 2.0
import QtQuick.Layouts 1.12
import UIBase 1.0
import Printer 1.0
import X1PlusNative 1.0
import "qrc:/uibase/qml/widgets"
import "../dialog"
import "../X1Plus.js" as X1Plus

Item {
    property alias name: textConfirm.objectName
    property var module: ""
    property var friendly: ""
    property var version: ""
    property var url: ""
    property var md5: ""
    property var fileName: url.substring(url.lastIndexOf("/") + 1)
    property var localPath: `/sdcard/x1plus/firmware/${fileName}`
    property var isDownloaded: false
    property var md5Failed: false
    property var downloadInProgress: false
    property var downloadStatus: ""
    property var isInstalling: false
    property var didInstall: false

    property var updater: DeviceManager.updater
    property var phonyProgress: 0.0
    property var phonyBusy: false
    property var updaterBusy: X1PlusNative.getenv("EMULATION_WORKAROUNDS") == "" ? (updater.status > Updater.IDLE && updater.status != Updater.UPGRADE_FAIL) : phonyBusy
    property var progress: X1PlusNative.getenv("EMULATION_WORKAROUNDS") == "" ? updater.progress : phonyProgress
    property var otaFile: "/userdata/firmware/ota-v99.00.00.00-00000000000000.json";

    
    property var buttons: SimpleItemModel {
        DialogButtonItem {
            name: "download"; title:  qsTr("Download %1").arg(version)
            isDefault: defaultButton == 0
            keepDialog: true
            onClicked: { downloadToCache(); }
            visible: !isDownloaded && !downloadInProgress && !isInstalling
        }
        DialogButtonItem {
            name: "install"; title: qsTr("Install %1").arg(version)
            isDefault: defaultButton == 0
            keepDialog: true
            onClicked: { install(); }
            visible: isDownloaded && !isInstalling && (!didInstall || updater.status == Updater.UPGRADE_FAIL)
        }
        DialogButtonItem {
            name: "no"; title: qsTr("Cancel")
            isDefault: defaultButton == 1
            visible: !isInstalling && !didInstall
            onClicked: { X1Plus.DDS.requestVersions(); }
        }
        DialogButtonItem {
            name: "postno"; title:qsTr("Return")
            isDefault: defaultButton == 1
            visible: didInstall
            onClicked: { X1Plus.DDS.requestVersions(); }
        }
    }

    function verifyCache() {
        let path = X1PlusNative.getenv("EMULATION_WORKAROUNDS") + localPath;
        let response = X1PlusNative.readFile(path);
        if (response.byteLength != 0) {
            isDownloaded = false;
            md5Failed = true;
            var calcmd5 = X1PlusNative.md5(response);
            console.log(`[x1p] ${path}: expected md5 ${md5}, calculated ${calcmd5} for on disk cache`);
            if (md5 == calcmd5) {
                isDownloaded = true;
                md5Failed = false;
            }
        } else {
            console.log(`[x1p] ${path}: not found on disk`);
            isDownloaded = false;
            md5Failed = false;
        }
    }

    function downloadToCache() {
        downloadInProgress = true;
        let xhr = new XMLHttpRequest();
        console.log(`[x1p] downloadToCache downloading ${url} to ${localPath}`);
        xhr.open("GET", url, /* async = */ true);
        xhr.responseType = "arraybuffer";
        xhr.send();
        downloadStatus = "connecting...";
        xhr.onreadystatechange = function() {
            if (xhr.readyState == xhr.DONE) {
                if (xhr.status == 200) {
                    downloadStatus = `downloaded ${xhr.response.byteLength} bytes`;
                    X1PlusNative.system("mkdir -p " + X1PlusNative.getenv("EMULATION_WORKAROUNDS") + "/sdcard/x1plus/firmware")
                    X1PlusNative.saveFile(X1PlusNative.getenv("EMULATION_WORKAROUNDS") + localPath, xhr.response);
                    console.log(`[x1p] downloaded ${xhr.response.byteLength} bytes and saved`);
                    downloadInProgress = false;
                    verifyCache();
                } else {
                    console.log(`[x1p] download failed (${xhr.status})`);
                    downloadStatus = `download failed (remote server returned ${xhr.status})`;
                }
            } else if (xhr.readyState == xhr.HEADERS_RECEIVED || xhr.readyState == xhr.LOADING) {
                downloadStatus = `receiving data...`;
            }
        };
    }
    
    Timer {
        id: phonyProgressTicker
        running: false
        interval: 50
        repeat: true
        onTriggered: {
            phonyProgress += 0.01;
            if (phonyProgress >= 1.0) {
                phonyProgressTicker.running = false;
                phonyBusy = false;
            }
        }
    }
    
    function install() {
        didInstall = false;
        isInstalling = true;
        screenSaver.overrideUpdater = true; /* screenSaver is actually a SettingsListener; tell it that we'll handle UpdateManager info */
        if (0 && X1PlusNative.getenv("EMULATION_WORKAROUNDS") != "") {
            phonyBusy = true;
            phonyProgress = 0.0;
            phonyProgressTicker.running = true;
        } else if (module == "xm") {
            // xm can only be updated with an ota.json consistency check --
            // the "command": "start" interface cannot trigger an xm update. 
            // So, we have to modify the on-disk ota.json to make this
            // happen.  I guess we don't ever have to put it back...
            X1Plus.saveJson(otaFile, {
                "version": "99.00.00.00",
                "xm": {
                    "sig": md5,
                    "url": `http://127.0.0.1:8888/${fileName}`,
                    "version": version,
                }
            });
            X1PlusNative.system(`cp /sdcard/x1plus/firmware/${fileName} /userdata/firmware/${fileName}`);
            X1PlusNative.system(`chmod -x /userdata/firmware/${fileName}`);
            X1Plus.DDS.publish("device/request/upgrade", {
                "command": "consistency_confirm",
                "sequence_id": "0"
            });
        } else {
            // thttpd looks in /tmp/firmware, not /sdcard/x1plus/firmware,
            // because sdcard file modes have +x, and thttpd will die from
            // that, so copy the file.  We could do this with XHRs, but, ...
            //
            // If we were trying to be actually secure about this, we'd use
            // the version that we verified the md5 of earlier to avoid a
            // TOCTTOU issue (trivium: I used this to exploit HTC Incredible
            // aeons ago!).  Luckily we don't care.
            // X1PlusNative.system(`cp /sdcard/x1plus/firmware/${fileName} /tmp/firmware/${fileName}`);
            // X1PlusNative.system(`chmod -x /tmp/firmware/${fileName}`);
            
            // Wolf On Air says that the printer can actually grab an
            // upgrade straight from /userdata/firmware, even with no httpd
            // running!  So we do that.
            X1PlusNative.system(`cp /sdcard/x1plus/firmware/${fileName} /userdata/firmware/${fileName}`);
            X1PlusNative.system(`chmod -x /userdata/firmware/${fileName}`);

            X1Plus.DDS.publish("device/request/upgrade", {
                "command": "start",
                "sequence_id": "0",
                "module": module.split("/")[0], /* ams/0 -> ams */
                "version": version,
                "url": `http://127.0.0.1:8888/${fileName}`
            });
        }
    }

    onUpdaterBusyChanged: {
        console.log(`update progress has changed ${progress}, busy ${updaterBusy}`);
        if (isInstalling && !updaterBusy) {
            screenSaver.overrideUpdater = false;
            didInstall = true;
            isInstalling = false;
        }
    }

    Component.onCompleted: {
        verifyCache();
    }

    id: textConfirm
    width: 800
    height: layout.height
    
    RowLayout {
        id: layout
        width: 800
        spacing: 0
        
        Image {
            id: moduleIcon
            Layout.preferredWidth: 128
            Layout.preferredHeight: 128
            Layout.rightMargin: 24
            Layout.alignment: Qt.AlignTop | Qt.AlignLeft
            fillMode: Image.PreserveAspectFit
            source: "../../icon/up_arrow.svg" // I guess?
        }
        
        GridLayout {
            rowSpacing: 6
            columnSpacing: 12
            columns: 2
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignLeft | Qt.AlignTop
            Layout.maximumWidth: 1000
            
            Text {
                Layout.columnSpan: 2
                Layout.fillWidth: true
                Layout.bottomMargin: 18
                font: Fonts.body_36
                color: Colors.gray_100
                wrapMode: Text.Wrap
                text: qsTr("%1 update %2").arg(friendly).arg(version)
            }


            /* Phase: pre-download. */
            Text {
                Layout.columnSpan: 2
                Layout.fillWidth: true
                font: Fonts.body_26
                color: Colors.gray_200
                wrapMode: Text.Wrap
                visible: !isDownloaded && !downloadInProgress && !md5Failed
                text: qsTr("Version %1 does not exist on the SD card. Download it now?<br><br>This requires an active Internet connection, and will connect to Bambu Lab servers.").arg(version)
            }

            Text {
                Layout.columnSpan: 2
                Layout.fillWidth: true
                font: Fonts.body_26
                color: Colors.gray_200
                wrapMode: Text.Wrap
                visible: !isDownloaded && !downloadInProgress && md5Failed
                text: qsTr("Version %1 exists on the SD card, but appears to be corrupt. Redownload it now?<br><br>This requires an active Internet connection, and will connect to Bambu Lab servers.").arg(version)
            }

            /* Phase: download. */
            Text {
                Layout.columnSpan: 2
                Layout.fillWidth: true
                font: Fonts.body_26
                color: Colors.gray_200
                wrapMode: Text.Wrap
                visible: !isDownloaded && downloadInProgress
                text: qsTr("Downloading version %1 from Bambu Lab: %2").arg(version).arg(downloadStatus)
            }
            
            /* Phase: pre-install. */
            Text {
                Layout.columnSpan: 2
                Layout.fillWidth: true
                font: Fonts.body_26
                color: Colors.gray_200
                wrapMode: Text.Wrap
                visible: isDownloaded && !isInstalling && !didInstall
                text: qsTr("Version %1 is available on the SD card and ready to install. Install it now?").arg(version)
            }
            
            /* Phase: installing. */
            Text {
                Layout.columnSpan: 2
                Layout.fillWidth: true
                font: Fonts.body_26
                color: Colors.gray_200
                wrapMode: Text.Wrap
                visible: isInstalling
                text: qsTr("Installing version %1.  Do not power off your printer.").arg(version)
            }
            
            ZProgressBar {
                Layout.columnSpan: 2
                Layout.fillWidth: true
                Layout.topMargin: 12
                type: ZProgressBarAppearance.Secondary
                size: ZProgressBarAppearance.Middle
                id: progressBar
                value: progress
                backgroundColor: StateColors.get("gray_600")
                progressColor: Colors.brand
                visible: isInstalling
            }
            
            Text {
                Layout.columnSpan: 2
                Layout.fillWidth: true
                Layout.topMargin: 5
                horizontalAlignment: Text.AlignHCenter
                font: Fonts.body_26
                color: Colors.gray_200
                wrapMode: Text.Wrap
                visible: isInstalling
                text: `${(progress * 100).toFixed()}%${updater.message != '' ? ' (' : ''}${updater.message}${updater.message != '' ? ')' : ''}`
            }

            /* Phase: post-install. */
            Text {
                Layout.columnSpan: 2
                Layout.fillWidth: true
                font: Fonts.body_26
                color: Colors.gray_200
                wrapMode: Text.Wrap
                visible: didInstall && updater.status != Updater.UPGRADE_FAIL
                text: qsTr("Successfully installed version %1.").arg(version)
            }

            Text {
                Layout.columnSpan: 2
                Layout.fillWidth: true
                font: Fonts.body_26
                color: Colors.gray_200
                wrapMode: Text.Wrap
                visible: didInstall && updater.status == Updater.UPGRADE_FAIL
                text: qsTr("Version %1 failed to install. Consider trying again, or power cycling your printer.").arg(version) +
                    (updater.message != '' ? qsTr(" (Updater message \"%1\".)").arg(updater.message) : '')
            }
        }
    }
}
