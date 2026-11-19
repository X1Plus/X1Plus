import QtQuick 2.12
import QtQuick.Controls 2.5
import QtQuick.Shapes 1.12
import UIBase 1.0
import Printer 1.0

import ".."
import "../X1Plus.js" as X1Plus
import "qrc:/uibase/qml/widgets"

Item {
    property string selectedPath: ""
    property var selectedMeta: null

    signal backClicked()
    signal printClicked(var payload)

    property int selectedPlate: 1
    property var selectedTrays: []
    property bool useAms: PrintManager.feeder.hasAms
    property bool bedLeveling: true
    property bool flowCali: true
    property bool timelapse: false
    property int pickerFilamentIdx: 0
    property bool pickerOpen: false

    property var currentPlateData: {
        if (!selectedMeta) return null;
        var plates = selectedMeta.plates;
        if (!plates || plates.length === 0) return selectedMeta;
        var idx = selectedPlate - 1;
        return (idx >= 0 && idx < plates.length) ? plates[idx] : selectedMeta;
    }

    // Remembers the trays you picked for each filament so they stay when you switch plates
    property var userTrayPicks: ({})

    onSelectedMetaChanged: {
        userTrayPicks = {};
        selectedPlate = 1;
        selectedTrays = autoAssignTrays(selectedMeta);
        pickerOpen = false;
    }

    onSelectedPlateChanged: {
        if (!selectedMeta) return;
        var plates = selectedMeta.plates;
        var plate = (plates && selectedPlate >= 1 && selectedPlate <= plates.length)
                    ? plates[selectedPlate - 1] : selectedMeta;
        var trays = autoAssignTrays(plate);
        var slotMap = plate.filamentSlotMap || [];
        for (var k = 0; k < slotMap.length; k++)
            if (slotMap[k] >= 0 && userTrayPicks[k] !== undefined) trays[slotMap[k]] = userTrayPicks[k];
        selectedTrays = trays;
    }

    function trayLabel(idx) {
        return ["A","B","C","D"][Math.floor(idx / 4)] + (idx % 4 + 1);
    }

    function findMatchingTray(filament, usedTrays, needColor) {
        if (!filament) return null;
        var targetType = (filament.type || "").toLowerCase();
        if (!targetType || targetType === "?") return null;
        var trays = PrintManager.feeder.amsTrays;
        for (var i = 0; i < trays.length; i++) {
            var td = trays[i];
            if (!td.exist || usedTrays.indexOf(td.index) >= 0) continue;
            if (!typeMatches(td.typeName + "", targetType)) continue;
            if (!needColor || (filament.color && td.colored && Qt.colorEqual(filament.color, td.color)))
                return td;
        }
        return null;
    }

    function typeMatches(trayTypeName, filamentType) {
        if (!filamentType || filamentType === "?") return true;
        var tray = (trayTypeName + "").toLowerCase();
        var req  = filamentType.toLowerCase();
        return tray === req || tray.indexOf(req) >= 0 || req.indexOf(tray) >= 0;
    }

    // Each tray only gets used once like the SD card page, color matches first then just the type.
    // Anything left over shows "--" and has to be picked by hand
    function autoAssignTrays(meta) {
        if (!meta || !meta.filaments) return [];
        var result = meta.filaments.map(function() { return null; });
        var used = [];
        [true, false].forEach(function(needColor) {
            for (var i = 0; i < meta.filaments.length; i++) {
                if (result[i]) continue;
                var td = findMatchingTray(meta.filaments[i], used, needColor);
                if (td) { result[i] = td; used.push(td.index); }
            }
        });
        return result;
    }

    function baseName(path) {
        var idx = path.lastIndexOf("/");
        return idx >= 0 ? path.substring(idx + 1) : path;
    }

    // ── Checks before printing ───────────────────────────────────────────────
    function _plateFilaments() {
        return (currentPlateData && currentPlateData.filaments) ? currentPlateData.filaments : [];
    }

    function checkIdle() {
        if (X1Plus.isIdle()) return null;
        return { name: "printer busy", type: 0,
                 text: qsTr("The printer is currently busy. Wait for the current job to finish before printing.") };
    }

    function checkNull() {
        if (!useAms) return null;
        var ff = _plateFilaments();
        if (ff.length === 0) return null;
        for (var i = 0; i < ff.length; i++) {
            if (!selectedTrays[i])
                return { name: "AMS mapping confirm", type: 0,
                         text: qsTr("Please manually set AMS slots for the filaments marked with \"--\".") };
        }
        for (var j = 0; j < ff.length; j++) {
            var t = selectedTrays[j];
            if (t && !t.ready)
                return { name: "AMS mapping ready",
                         text: qsTr("Some AMS filaments are not fully loaded. Continue anyway?") };
        }
        return null;
    }

    function checkTPU() {
        if (!useAms) return null;
        for (var i = 0; i < selectedTrays.length; i++) {
            var t = selectedTrays[i];
            if (t && (t.typeName + "").toUpperCase() === "TPU")
                return { name: "ams tpu", type: 0,
                         text: qsTr("TPU filament is not supported by AMS.") };
        }
        return null;
    }

    function checkProhibitCF() {
        if (!useAms) return null;
        for (var i = 0; i < selectedTrays.length; i++) {
            var t = selectedTrays[i];
            if (!t) continue;
            var fid = (t.filamentId || "").toString();
            if (fid === "GFT50" || fid === "GFN05")
                return { name: "AMS unsupport PET-CF/PA6-CF filament", type: 0,
                         text: qsTr("Bambu PET-CF/PA6-CF is not supported by AMS.") };
        }
        return null;
    }

    function checkPVA() {
        if (!useAms) return null;
        for (var i = 0; i < selectedTrays.length; i++) {
            var t = selectedTrays[i];
            if (t && (t.typeName + "").toUpperCase() === "PVA")
                return { name: "ams pva",
                         text: qsTr("Damp PVA will become flexible and may get stuck in AMS. Make sure it is thoroughly dried before use.") };
        }
        return null;
    }

    function checkCF() {
        if (!useAms) return null;
        for (var i = 0; i < selectedTrays.length; i++) {
            var t = selectedTrays[i];
            if (!t || !t.thirdparty) continue;
            var tn = (t.typeName + "").toUpperCase();
            if (tn.indexOf("_CF") >= 0 || tn.indexOf("-CF") >= 0)
                return { name: "ams cf",
                         text: qsTr("CF filaments are hard and brittle and may break or get stuck in AMS. Use with caution.") };
        }
        return null;
    }

    function checkFilamentTypes() {
        if (!useAms || selectedTrays.length === 0) return null;
        var ff = _plateFilaments();
        var mismatch = false, unknown = false;
        for (var i = 0; i < ff.length && i < selectedTrays.length; i++) {
            var tray = selectedTrays[i];
            var req = (ff[i].type || "").toLowerCase();
            if (!req || req === "?") { unknown = true; continue; }
            var got = (tray.typeName + "").toLowerCase();
            if (!got || got === "?") { unknown = true; continue; }
            if (got !== req && got.indexOf(req) < 0 && req.indexOf(got) < 0)
                mismatch = true;
        }
        if (mismatch) return { name: "filament mismatch", type: 0,
            text: qsTr("The selected AMS tray filament type does not match the file. Please check your filament selection.") };
        if (unknown) return { name: "filament unknown",
            text: qsTr("Some filament types are unknown. Make sure they are compatible with this print.") };
        return null;
    }

    function checkPrinterModel() {
        if (!currentPlateData || !currentPlateData.printerModelId) return null;
        var result = PrintManager.currentTask.printerModelCheck(currentPlateData.printerModelId);
        if (result === PrintTask.Prohibit)
            return { name: "printer model", type: 0,
                     text: qsTr("This file is not compatible with the current printer model and cannot be printed.") };
        if (result === PrintTask.Warning)
            return { name: "printer model warning",
                     text: qsTr("This file was sliced for a different printer model. Print anyway?") };
        return null;
    }

    function checkNozzleDiameters() {
        if (!currentPlateData || !currentPlateData.nozzleDiameters) return null;
        var result = PrintManager.currentTask.nozzleDiametersCheck(currentPlateData.nozzleDiameters);
        if (result === PrintTask.Prohibit)
            return { name: "nozzle diameter", type: 0,
                     text: qsTr("The nozzle diameter in this file does not match the current nozzle and cannot be printed.") };
        return null;
    }

    function runPreflightChecks(checks, onAllPassed) {
        if (checks.length === 0) { onAllPassed(); return; }
        var check = checks[0];
        var remaining = checks.slice(1);
        var res = check();
        if (res === null) { runPreflightChecks(remaining, onAllPassed); return; }
        if (res.type === 0) {
            res.onConfirm = function() {}; // This one blocks printing, OK just closes the warning
        } else {
            var _remaining = remaining, _onAllPassed = onAllPassed;
            res.onYes = function() { runPreflightChecks(_remaining, _onAllPassed); };
        }
        dialogStack.popupDialog("TextConfirm", res);
    }

    function executePrint() {
        var path = selectedPath;
        var is3mf = path.slice(-4).toLowerCase() === ".3mf";
        var amsMapping = (function() {
            if (!useAms || selectedTrays.length === 0) return [];
            var anyAssigned = false;
            for (var i = 0; i < selectedTrays.length; i++)
                if (selectedTrays[i]) { anyAssigned = true; break; }
            if (!anyAssigned) return [];
            var slotMap = currentPlateData && currentPlateData.filamentSlotMap;
            if (slotMap && slotMap.length > 0)
                return slotMap.map(function(di) { if (di < 0) return -1; var t = selectedTrays[di]; return t ? t.index : 0; });
            return selectedTrays.map(function(t) { return t ? t.index : 0; });
        })();
        // Same fields the SD card page sends. Sending bed_type "auto" made the printer think it was a cool plate
        printClicked(is3mf ? {
            command: "project_file",
            param: "Metadata/plate_" + selectedPlate + ".gcode",
            plate: selectedPlate - 1,
            url: "file://" + path,
            subtask_name: baseName(path),
            timelapse: timelapse, bed_leveling: bedLeveling, flow_cali: flowCali,
            ams_mapping: amsMapping, use_ams: useAms,
            sequence_id: "0"
        } : {
            command: "gcode_file",
            param: path, sequence_id: 0, subtask_name: baseName(path),
            use_ams: useAms, bed_leveling: bedLeveling,
            flow_cali: flowCali, timelapse: timelapse
        });
        if (currentPlateData && currentPlateData.bedTooHot)
            dialogStack.popupDialog("ErrorPrompt", {
                level: PrintModule.Notice,
                name: "bed temp over vitrification",
                errorMsg: qsTr("High bed temperature may lead to filament clogging in the nozzle. You may open the chamber door.") + " [1000 c001 201215]"
            });
    }

    // ── Left side: plate picture ─────────────────────────────────────────────
    MarginPanel {
        id: confirmPoster
        width: 680
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        leftMargin: 24
        topMargin: 20
        bottomMargin: 20
        color: Colors.gray_600

        Image {
            anchors.fill: parent
            visible: currentPlateData !== null && currentPlateData.thumbnail && currentPlateData.thumbnail.length > 0
            source: (currentPlateData !== null && currentPlateData.thumbnail && currentPlateData.thumbnail.length > 0)
                ? "data:image/png;base64," + currentPlateData.thumbnail : ""
            fillMode: Image.PreserveAspectFit
            cache: false
        }

        Text {
            anchors.centerIn: parent
            visible: currentPlateData === null || !currentPlateData.thumbnail || currentPlateData.thumbnail.length === 0
            font.pixelSize: 100
            color: Colors.gray_400
            text: "≡"
        }

        Text {
            anchors.top: parent.top
            anchors.right: parent.right
            anchors.topMargin: 10
            anchors.rightMargin: 10
            color: Colors.gray_500
            font: Fonts.body_24
            visible: selectedMeta !== null && (selectedMeta.plateCount || 1) > 1
            text: selectedPlate + " / " + (selectedMeta ? (selectedMeta.plateCount || 1) : 1)
        }

        ZButton {
            // Hidden on the first plate like the SD card page
            visible: selectedMeta !== null && selectedPlate > 1
            x: 32
            height: width
            anchors.verticalCenter: parent.verticalCenter
            type: ZButtonAppearance.Secondary
            iconSize: 0
            cornerRadius: width / 2
            rotation: -90
            icon: "../../icon/up.svg"
            onClicked: selectedPlate--
        }

        ZButton {
            // Hidden on the last plate like the SD card page
            visible: selectedMeta !== null && selectedPlate < (selectedMeta.plateCount || 1)
            height: width
            anchors.right: parent.right
            anchors.rightMargin: 32
            anchors.verticalCenter: parent.verticalCenter
            type: ZButtonAppearance.Secondary
            iconSize: 0
            cornerRadius: width / 2
            rotation: 90
            icon: "../../icon/up.svg"
            onClicked: selectedPlate++
        }

        Shape {
            id: posterInfoBar
            width: parent.width
            height: 112
            anchors.bottom: parent.bottom
            property real barRadius: 15

            ShapePath {
                fillColor: "#66000000"
                strokeColor: "transparent"
                startX: 0; startY: 0
                PathLine { x: posterInfoBar.width; y: 0 }
                PathLine { x: posterInfoBar.width; y: posterInfoBar.height - posterInfoBar.barRadius }
                PathArc  { radiusX: posterInfoBar.barRadius; radiusY: posterInfoBar.barRadius
                           x: posterInfoBar.width - posterInfoBar.barRadius; y: posterInfoBar.height }
                PathLine { x: posterInfoBar.barRadius; y: posterInfoBar.height }
                PathArc  { radiusX: posterInfoBar.barRadius; radiusY: posterInfoBar.barRadius
                           x: 0; y: posterInfoBar.height - posterInfoBar.barRadius }
                PathLine { x: 0; y: 0 }
            }

            Text {
                id: posterTitle
                anchors.left: parent.left
                anchors.leftMargin: 15
                anchors.top: parent.top
                anchors.topMargin: 10
                width: parent.width - 30
                font: Fonts.head_30
                color: Colors.white_900
                elide: Text.ElideRight
                clip: true
                text: baseName(selectedPath)
            }

            ZLineSplitter {
                id: posterInfoSplit
                alignment: Qt.AlignTop
                anchors.top: posterTitle.bottom
                anchors.topMargin: 10
                padding: 20
                color: Colors.brand
            }

            ListView {
                height: 47
                anchors.left: posterInfoSplit.left
                anchors.right: posterInfoSplit.right
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 5
                orientation: ListView.Horizontal
                boundsBehavior: ListView.StopAtBounds
                model: {
                    var items = [];
                    if (currentPlateData && currentPlateData.timeEstimate > 0)
                        items.push({ key: "time",   value: Printer.durationString(currentPlateData.timeEstimate) });
                    if (currentPlateData && currentPlateData.weightEstimate > 0)
                        items.push({ key: "weight", value: currentPlateData.weightEstimate.toFixed(1) + qsTr("g") });
                    return items;
                }
                delegate: Item {
                    width: ListView.view.width / 3
                    height: ListView.view.height
                    Image {
                        id: posterInfoIcon
                        anchors.left: parent.left
                        anchors.leftMargin: 20
                        anchors.verticalCenter: parent.verticalCenter
                        source: "../../icon/" + modelData.key + ".svg"
                        cache: false
                    }
                    Text {
                        anchors.left: posterInfoIcon.right
                        anchors.leftMargin: 5
                        anchors.verticalCenter: parent.verticalCenter
                        font: Fonts.body_30
                        color: Colors.gray_100
                        text: modelData.value
                    }
                }
            }
        }
    }

    // ── Right side: filaments and print options ──────────────────────────────
    MarginPanel {
        id: infoPanel
        anchors.left: confirmPoster.right
        anchors.leftMargin: 23
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        leftMargin: 23
        rightMargin: 21
        topMargin: confirmPoster.topMargin
        bottomMargin: confirmPoster.bottomMargin
        color: Colors.gray_800

        Text {
            anchors.top: parent.top
            anchors.topMargin: 30
            anchors.left: parent.left
            anchors.leftMargin: 40
            anchors.right: parent.right
            anchors.rightMargin: 20
            visible: selectedMeta !== null && selectedMeta.hasPrintableGcode !== true
            font: Fonts.body_26
            color: Colors.gray_400
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            text: qsTr("Model only\nCannot print directly")
        }

        Text {
            id: filamentHeader
            visible: selectedMeta !== null && selectedMeta.hasPrintableGcode === true
            anchors.top: parent.top
            anchors.topMargin: 15
            anchors.left: parent.left
            anchors.leftMargin: 40
            font: Fonts.body_24
            color: Colors.gray_300
            text: pickerOpen
                ? qsTr("Select AMS tray")
                : (swatchContainer.amsActive ? qsTr("Filament selection") : qsTr("Filament"))
        }

        Item {
            id: swatchContainer
            visible: filamentHeader.visible
            anchors.top: filamentHeader.bottom
            anchors.topMargin: 10
            anchors.left: parent.left
            anchors.leftMargin: 40
            anchors.right: parent.right
            anchors.rightMargin: 40
            height: swatchFlow.height

            property bool amsActive: useAms && PrintManager.feeder.hasAms

            Flow {
                id: swatchFlow
                width: parent.width
                spacing: 10

                Repeater {
                    model: (currentPlateData && currentPlateData.filaments)
                           ? currentPlateData.filaments : []

                    delegate: Item {
                        id: swatchItem
                        width: (swatchFlow.width - swatchFlow.spacing) / 2
                        height: 110

                        property int filamentIdx: index
                        property var assignedTray: filamentIdx < selectedTrays.length
                                                   ? selectedTrays[filamentIdx] : null
                        property color swatchColor: modelData ? modelData.color : "#808080"
                        property color swatchTextColor: {
                            var c = swatchItem.swatchColor;
                            var lum = 0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b;
                            return lum > 0.5 ? "#000000" : "#ffffff";
                        }
                        property string swatchType: modelData ? (modelData.type || "?") : "?"

                        Rectangle {
                            anchors.fill: parent
                            radius: 10
                            color: swatchItem.swatchColor

                            Text {
                                anchors.fill: parent
                                anchors.margins: 5
                                anchors.bottomMargin: swatchContainer.amsActive ? 22 : 5
                                font: Fonts.body_24
                                minimumPixelSize: 8
                                fontSizeMode: Text.Fit
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                                color: swatchItem.swatchTextColor
                                text: swatchItem.swatchType
                            }

                            Rectangle {
                                id: trayBadge
                                visible: swatchContainer.amsActive
                                width: parent.width
                                height: 22
                                anchors.bottom: parent.bottom
                                color: (swatchItem.assignedTray && swatchItem.assignedTray.colored)
                                       ? swatchItem.assignedTray.color : Qt.rgba(0, 0, 0, 0.55)
                                radius: 10
                                property color badgeTextColor: {
                                    var c = trayBadge.color;
                                    var lum = 0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b;
                                    return lum > 0.5 ? "#000000" : "#ffffff";
                                }
                                Rectangle {
                                    width: parent.width
                                    height: 10
                                    anchors.top: parent.top
                                    color: parent.color
                                }
                                Text {
                                    anchors.centerIn: parent
                                    font: Fonts.body_16
                                    color: trayBadge.badgeTextColor
                                    text: swatchItem.assignedTray
                                          ? trayLabel(swatchItem.assignedTray.index) : "--"
                                }
                            }

                            Rectangle {
                                anchors.fill: parent
                                anchors.margins: -3
                                color: "transparent"
                                radius: 13
                                border.width: (pickerOpen && pickerFilamentIdx === swatchItem.filamentIdx)
                                              || (swatchContainer.amsActive && !swatchItem.assignedTray) ? 2 : 0
                                border.color: (pickerOpen && pickerFilamentIdx === swatchItem.filamentIdx) ? Colors.brand : Colors.warning
                            }
                        }

                        TapHandler {
                            gesturePolicy: TapHandler.ReleaseWithinBounds
                            enabled: swatchContainer.amsActive
                            onTapped: {
                                if (pickerOpen && pickerFilamentIdx === swatchItem.filamentIdx) {
                                    pickerOpen = false;
                                } else {
                                    pickerFilamentIdx = swatchItem.filamentIdx;
                                    pickerOpen = true;
                                }
                            }
                        }
                    }
                }
            }
        }

        Text {
            anchors.top: swatchContainer.bottom
            anchors.topMargin: 20
            anchors.left: swatchContainer.left
            anchors.right: swatchContainer.right
            visible: swatchContainer.visible && swatchContainer.amsActive
                     && _plateFilaments().some(function(f, i) { return !selectedTrays[i]; })
            wrapMode: Text.WordWrap
            font: Fonts.body_20
            color: Colors.warning
            text: qsTr("Please manually set AMS slots for the filaments marked with \"--\".")
        }

        Rectangle {
            id: usbTrayPicker
            visible: pickerOpen && swatchContainer.amsActive
            z: 5
            anchors.top: swatchContainer.bottom
            anchors.topMargin: 8
            anchors.left: parent.left
            anchors.leftMargin: 30
            anchors.right: parent.right
            anchors.rightMargin: 30
            height: Math.ceil((PrintManager.feeder.hasAms ? PrintManager.feeder.amsTrays.length : 0) / 4) * 68 + 16
            radius: 12
            color: Colors.gray_500

            GridView {
                x: 8; y: 8
                width: parent.width - 16
                height: parent.height - 16
                cellWidth: Math.floor(width / 4)
                cellHeight: 68
                interactive: false
                model: PrintManager.feeder.hasAms ? PrintManager.feeder.amsTrays : []

                delegate: Item {
                    property var td: modelData
                    width: GridView.view.cellWidth - 8
                    height: GridView.view.cellHeight - 8
                    property bool compatible: {
                        if (!td.exist) return false;
                        var filaments = currentPlateData ? currentPlateData.filaments : null;
                        if (!filaments || pickerFilamentIdx >= filaments.length) return true;
                        return typeMatches(td.typeName + "", filaments[pickerFilamentIdx].type || "?");
                    }
                    opacity: compatible ? 1.0 : 0.3

                    Rectangle {
                        id: trayCell
                        anchors.fill: parent
                        radius: 10
                        color: td.exist && td.colored ? td.color : Colors.gray_600
                        border.width: 1
                        border.color: Colors.gray_400
                        property color cellTextColor: {
                            var c = trayCell.color;
                            var lum = 0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b;
                            return lum > 0.5 ? "#000000" : "#ffffff";
                        }

                        Text {
                            anchors.top: parent.top
                            anchors.topMargin: 3
                            anchors.horizontalCenter: parent.horizontalCenter
                            font: Fonts.body_16
                            color: trayCell.cellTextColor
                            text: trayLabel(td.index)
                        }

                        Text {
                            anchors.fill: parent
                            anchors.topMargin: 20
                            anchors.margins: 4
                            font: Fonts.body_20
                            minimumPixelSize: 8
                            fontSizeMode: Text.Fit
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            color: trayCell.cellTextColor
                            text: td.exist ? (td.typeName + "") : "—"
                        }
                    }

                    TapHandler {
                        gesturePolicy: TapHandler.ReleaseWithinBounds
                        enabled: compatible
                        onTapped: {
                            var copy = selectedTrays.slice();
                            copy[pickerFilamentIdx] = td;
                            selectedTrays = copy;
                            var slotMap = (currentPlateData && currentPlateData.filamentSlotMap) || [];
                            for (var k = 0; k < slotMap.length; k++)
                                if (slotMap[k] === pickerFilamentIdx) userTrayPicks[k] = td;
                            pickerOpen = false;
                        }
                    }
                }
            }
        }

        ListView {
            id: switchList
            anchors.bottom: infoSplit.top
            anchors.bottomMargin: 15
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.margins: 30
            height: contentHeight
            visible: selectedMeta !== null && selectedMeta.hasPrintableGcode === true
            spacing: 8
            model: [
                { text: qsTr("Use AMS"),          checked: useAms,      vis: PrintManager.feeder.hasAms, key: "ams" },
                { text: qsTr("Bed Leveling"),     checked: bedLeveling, vis: true,                       key: "bed" },
                { text: qsTr("Flow Calibration"), checked: flowCali,    vis: true,                       key: "flow" },
                { text: qsTr("Timelapse"),        checked: timelapse,   vis: true,                       key: "tl" }
            ]
            delegate: Item {
                width: parent.width
                height: modelData.vis ? checkBox.height : 0
                visible: modelData.vis
                ZCheckBox {
                    id: checkBox
                    font: Fonts.body_28
                    textColor: StateColors.get("gray_100")
                    text: modelData.text
                    tapMargin: 5
                    checked: modelData.checked
                    onCheckedChanged: {
                        if (modelData.key === "ams")        useAms      = checked;
                        else if (modelData.key === "bed")   bedLeveling = checked;
                        else if (modelData.key === "flow")  flowCali    = checked;
                        else if (modelData.key === "tl")    timelapse   = checked;
                    }
                }
            }
        }

        ZLineSplitter {
            id: infoSplit
            alignment: Qt.AlignBottom
            padding: 30
            offset: 122
            color: Colors.brand
        }

        ZButton {
            id: backBtn
            width: 131
            anchors.left: infoSplit.left
            anchors.top: infoSplit.bottom
            anchors.topMargin: 29
            paddingX: 15
            verticalTapMargin: 10
            text: qsTr("Back")
            onClicked: backClicked()
        }

        ZButton {
            width: 200
            anchors.right: infoSplit.right
            anchors.top: backBtn.top
            verticalTapMargin: 10
            checked: true
            visible: selectedMeta !== null && selectedMeta.hasPrintableGcode === true
            text: qsTr("Print now")
            onClicked: {
                runPreflightChecks([checkIdle, checkNull, checkTPU, checkProhibitCF, checkPVA, checkCF, checkFilamentTypes, checkPrinterModel, checkNozzleDiameters], executePrint);
            }
        }
    }
}
