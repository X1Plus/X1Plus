import QtQuick 2.0
import UIBase 1.0
import Printer 1.0
import QtQuick.Controls 2.12
import QtQuick.Layouts 1.12
import UIBase 1.0
import QtQuick.VirtualKeyboard 2.1
import X1PlusNative 1.0

import "qrc:/uibase/qml/widgets"
import "../printer"
import ".."
import "../X1Plus.js" as X1Plus


Rectangle {
    property var nozzleType: [[qsTr("Stainless steel"), qsTr("Hardened steel")], ["stainless_steel", "hardened_steel"]]
    property var nozzleSize: [["0.2mm", "0.4mm"], ["0.4mm", "0.6mm", "0.8mm"]]
    property var fan: [qsTr("Not installed"), qsTr("Installed")]
    color: Colors.gray_700
    property var maintain: DeviceManager.maintain
    property var brightness: DeviceManager.getSetting("cfw_brightness", 100.0)
    property var toolheadLED: DeviceManager.getSetting("cfw_toolhead_led", false)

    Timer {
        id: dispBrightnessChangeTimer
        interval: 300; running: false; repeat: false
        onTriggered: DeviceManager.putSetting("cfw_brightness", dispBrightnessAdj.value);
    }
    Timer {
        id: myTime
        interval: 5000
        repeat: true
        running: visible
        onTriggered: {
            DeviceManager.maintain.getAccessories()
        }
    }
    // function pathDialog(inputtxt,inputtitle){
    //         dialogStack.push("InputPage.qml", {
    //                             input_head_text : inputtitle,
    //                             input_text : inputtxt,
    //                             max_input_num : 50,
    //                             isUsePassWord : false,
    //                             isInputShow : true,
    //                             isInputting_obj : rect_isInputting_obj,
    //                             output_obj : inputText});    
    //     }
        
    // // function fileExist(path){
    // //     var exist = X1PlusNative.popen(`test -f ${path} && echo 1`);
    // //     return (exist == 1);
    // // }
    // // function fileDate(path){
    // //     return X1PlusNative.popen(`stat -c %Y ${path}`);
    // // }
    // QtObject {
    //     id: rect_isInputting_obj
    //     property bool isInputting: false
    //     property string setType:""
    //     onIsInputtingChanged: {
    //         if(!isInputting){
    //             if (setType == "temp"){
    //                 let splitKey = inputText.text.trim().split(' ');
    //                 if (splitKey.length < 2){
    //                     return;
    //                 } else {
    //                     let setT = splitKey[1]; 
    //                     if (splitKey[0] == "bed") {
    //                         if (setT > 110){
    //                             setT=35;
    //                             console.log("[x1p] invalid set temperature input");
    //                         }
    //                     } else if (splitKey[0] == "nozzle"){
    //                         if (setT > 300){
    //                             setT=100;
    //                             console.log("[x1p] invalid set temperature input");
    //                         }
    //                     } else {
    //                         return;
    //                     }
    //                     DeviceManager.putSetting(dialog_jsonKey, `1 ${splitKey[0]} ${setT}`);
    //                 }
    //             } else {
    //                 macroFile = inputText.text;         
    //                 console.log("[x1p]",macroFile);
    //                 if (macroFile.endsWith(".py")){
    //                     DeviceManager.putSetting(dialog_jsonKey, `6 ${macroFile}`);
    //                 } else if (macroFile.endsWith(".gcode")){
    //                     DeviceManager.putSetting(dialog_jsonKey, `6 ${macroFile}`);
    //                 } else {
    //                     DeviceManager.putSetting(dialog_jsonKey, "0"); //incorrect filetype entered.. lazy way to error handle
    //                 }
    //             }
    //             setType = "";
    //         }
    //     }
    // }
    // Text {
    //     id: inputText
    //     visible: false
    //     text: macroFile
    // }


    
    MarginPanel {
        id: accessoriesMP
        anchors.top: printMP.top
        anchors.left: printMP.right
        anchors.leftMargin: 14
        anchors.right: parent.right
        anchors.rightMargin: 10 // 16px outer, adds up to 26px to match BedMesh.qml
        anchors.bottom: printMP.bottom
        radius: 15
        color: Colors.gray_800

        Text {
            id: accessoriesTx
            anchors.top: parent.top
            anchors.topMargin: 30
            anchors.left: parent.left
            anchors.leftMargin: 32
            color: Colors.gray_100
            font: Fonts.body_40
            text: qsTr("Accessories")
        }

        ZButton {
            anchors.verticalCenter: accessoriesTx.verticalCenter
            anchors.left: accessoriesTx.right
            anchors.leftMargin: -5
            backgroundColor: StateColors.get("transparent")
            borderColor: StateColors.get("transparent")
            icon: "../../icon/helpIcon.svg"
            iconSize: 34
            onClicked: {
                accessoriesHelpPad.popup()
            }
        }

        ZLineSplitter{
            id: line1
            alignment: Qt.AlignTop
            y: 95
            padding: 24
            color: Colors.gray_600
        }
        Text {
            id: nozzleTx
            anchors.top: parent.top
            anchors.topMargin: 115
            anchors.left: accessoriesTx.left
            color: Colors.gray_400
            font: Fonts.body_30
            text: qsTr("Nozzle")
        }
        Choise {
            id: typeCB
            width: 290
            height: 68
            anchors.top: line1.bottom
            anchors.topMargin: 63
            anchors.left: nozzleTx.left
            model: nozzleType[0]
            backgroundColor: Colors.gray_600
            onCurrentTextChanged: {
                if(!down) return
                maintain.nozzleType = nozzleType[1][currentIndex]
            }
            Binding on currentIndex{
                value: nozzleType[1].indexOf(maintain.nozzleType)
            }
        }

        Choise {
            id: sizeCB
            height: 68
            anchors.top: typeCB.top
            anchors.left: typeCB.right
            anchors.right: parent.right
            anchors.rightMargin: 32
            anchors.leftMargin: 9
            model: typeCB.currentText === "" ? [] : nozzleSize[typeCB.currentIndex]
            backgroundColor: Colors.gray_600
            onCurrentTextChanged: {
                if(!down) return
                maintain.nozzleDiameter = currentText.replace("mm", "")
            }
            Binding on currentIndex{
                value: sizeCB.model.indexOf(maintain.nozzleDiameter + "mm")
            }
        }
        

        
        ZLineSplitter{
            id: line2
            alignment: Qt.AlignTop
            y: 253
            padding: 24
            color: Colors.gray_600
        }
        ZText {
            id: fanTx
            anchors.top: line2.bottom
            anchors.topMargin: 26
            anchors.left: accessoriesTx.left
            maxWidth: line2.width
            color: Colors.gray_400
            font: Fonts.body_30
            text: qsTr("Auxiliary Part Cooling Fan")
        }
        Choise {
            id: fanCB
            width: 240
            height: 68
            anchors.top: line2.bottom
            anchors.topMargin: 79
            anchors.left: typeCB.left
            textFont: Fonts.body_26
            listTextFont: Fonts.body_24
            textColor: currentIndex ? Colors.brand : Colors.warning
            padding: 20
            model: fan
            backgroundColor: Colors.gray_600
            currentIndex: maintain.auxPartCoolFan
            onCurrentTextChanged: {
                if(!down) return
                maintain.auxPartCoolFan = currentIndex
            }
            Binding on currentIndex{
                value: maintain.auxPartCoolFan
            }

            ZImage {
                anchors.left: parent.left
                anchors.leftMargin: 8
                width: 24
                tintColor: parent.currentIndex ? Colors.brand : Colors.warning
                anchors.verticalCenter: parent.verticalCenter
                originSource: "../../icon/roundHook.svg"
            }
        }
        Image {
            anchors.top: line2.bottom
            anchors.topMargin: 82
            anchors.right: parent.right
            anchors.rightMargin: 32
            fillMode: Image.Pad
            cache: false
            source: "../../icon/auxPartCoolFan_"+ fanCB.currentIndex +".svg"
        }
    }
    
    MarginPanel {
        id: printMP
        width: 585
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 10 // 16px outer, adds up to 26px to match BedMesh.qml
        anchors.left: parent.left
        anchors.leftMargin: 10
        radius: 15
        color: Colors.gray_800
        
        Text {
            id: interfaceTx
            anchors.top: parent.top
            anchors.topMargin: 30
            anchors.left: parent.left
            anchors.leftMargin: 32
            color: Colors.gray_100
            font: Fonts.body_40
            text: qsTr("Interface")
        }
        ZButton {
            anchors.verticalCenter: interfaceTx.verticalCenter
            anchors.topMargin: 20
            anchors.left: interfaceTx.right
            anchors.leftMargin: -5
            backgroundColor: StateColors.get("transparent")
            borderColor: StateColors.get("transparent")
            icon: "../../icon/helpIcon.svg"
            iconSize: 34
            onClicked: {
                buttonHelpPad.popup()
            }
        }
      
        ZButton {
            id: reloadgpio
            anchors.top: parent.top
            property bool isChanged: false
            anchors.topMargin: 10
            anchors.right: printMP.right
            anchors.rightMargin: 15
            type: ZButtonAppearance.Secondary
            icon: isChanged ? "../../icon/components/refresh_color.svg" : "../../icon/refresh.svg"
            height: width
            width: 69
            visible:true
            cornerRadius: width / 2
            iconSize: -1
            onClicked:{
                if (isChanged) {isChanged = (!isChanged)};
                dialogStack.popupDialog(
                                "TextConfirm", {
                                    name: "reset to defaults",
                                    text: qsTr("Reset button mapping to default settings?"),
                                    type: TextConfirm.YES_NO,
                                    defaultButton: 1,
                                    onYes: function() {
                                        buttonGrid.resetComboBoxDefaults();
                                        console.log("[x1p] Resetting button mappings to defaults (power button: short = toggle lcd, long = reboot; estop button: short = pause print, long = abort print)");
                                    },
                                })
        
            }
        }
        
        ZLineSplitter {
            id: line3
            alignment: Qt.AlignTop
            y: 95
            padding: 24
            color: Colors.gray_600
        }
        
        Text {
            id: buttonsTx
            anchors.top: line3.bottom
            anchors.topMargin: 24
            anchors.left: interfaceTx.left
            color: Colors.gray_400
            font: Fonts.body_30
            text: qsTr("Buttons")
        }

        GridLayout {
            id: buttonGrid
            
            anchors.top: buttonsTx.bottom
            anchors.topMargin: 14 /* we can shrink this a little for the text separation above */
            anchors.leftMargin: 32
            anchors.rightMargin: 32
            rowSpacing: 20
            columnSpacing: 20
            anchors.left: parent.left
            anchors.right: parent.right
            columns: 3
            property var imageHeight: 25
            function resetComboBoxDefaults() {
                var defaults = X1Plus.GpioKeys.resetToDefaultActions(); 
                
                for (var i = 0; i < buttonGrid.children.length; i++) {
                    var loader = buttonGrid.children[i];
                    if (loader.item) { 
                        loader.item.defaultSelection = X1Plus.GpioKeys.getDefault(loader.item.btn, loader.item.pressType);
                        loader.item.currentIndex = loader.item.defaultSelection;
                    }
                }
            }
            Text {
                Layout.row: 0
                Layout.column: 1
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignHCenter
                font: Fonts.body_24
                color: Colors.gray_100
                text: qsTr("Short Press")
            }
            
            Text {
                Layout.row: 0
                Layout.column: 2
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignHCenter
                font: Fonts.body_24
                color: Colors.gray_100
                text: qsTr("Long Press")
            }
            
            Image {
                Layout.row: 1
                Layout.column: 0
                Layout.preferredWidth: 56
                Layout.preferredHeight: 56
                source: "../../icon/components/power.svg"
            }
            
            Component {
                id: choiceMenu
                Choise {
                    property var pressType: ""
                    property var btn: ""
                    property var defaultSelection
                    textFont: Fonts.body_24
                    listTextFont: Fonts.body_24
                    width: 115
                    model: X1Plus.GpioKeys.buttonActions.map(a => a.name)
                    placeHolder:""
                    currentIndex: defaultSelection
                    onCurrentTextChanged: { 
                        if(!down) return;
                        let actionVal = X1Plus.GpioKeys.buttonActions.find(a => a.name === currentText).val;
                        if (actionVal !== undefined) {
                            console.log(`[x1p] {item.btn} {item.pressType} - {actionaVal}`);
                            X1Plus.GpioKeys.updateButtonAction(item.btn, item.pressType, actionVal, {});
                        }
                    }
                    Binding on currentIndex{
                        value: model.indexOf(X1Plus.GpioKeys.getActionText(btn, pressType))
                    }                  
                }
            }
          
            Loader {
                Layout.fillWidth: true
                sourceComponent: choiceMenu
                onLoaded: { item.btn = "cfw_power"; item.pressType = "shortPress";item.defaultSelection = X1Plus.GpioKeys.getDefault(item.btn,item.pressType); item.placeHolder =  X1Plus.GpioKeys.getActionText(item.btn, item.pressType)}
            }

            Loader {
                Layout.fillWidth: true
                sourceComponent: choiceMenu
                onLoaded: {item.btn =  "cfw_power"; item.pressType = "longPress";item.defaultSelection = X1Plus.GpioKeys.getDefault(item.btn,item.pressType); item.placeHolder =  X1Plus.GpioKeys.getActionText(item.btn, item.pressType)}
            }

            Image {
                Layout.row: 2
                Layout.column: 0
                Layout.preferredWidth: 56
                Layout.preferredHeight: 56
                source: "../../icon/components/estop.svg"
            }

            Loader {
                Layout.fillWidth: true
                sourceComponent: choiceMenu
                onLoaded: {item.btn =  "cfw_estop"; item.pressType = "shortPress";item.defaultSelection = X1Plus.GpioKeys.getDefault(item.btn,item.pressType); item.placeHolder =  X1Plus.GpioKeys.getActionText(item.btn, item.pressType)}
            }

            Loader {
                Layout.fillWidth: true
                sourceComponent: choiceMenu
                onLoaded: {item.btn =  "cfw_estop"; item.pressType = "longPress";item.defaultSelection = X1Plus.GpioKeys.getDefault(item.btn,item.pressType); item.placeHolder =  X1Plus.GpioKeys.getActionText(item.btn, item.pressType)}
            }
            
        }

        ZLineSplitter {
            id: lineLights
            alignment: Qt.AlignTop
            anchors.top: buttonGrid.bottom
            anchors.topMargin: 26
            padding: 24
            color: Colors.gray_600
        }

        Text {
            id: lightsTx
            anchors.top: lineLights.bottom
            anchors.topMargin: 20
            anchors.left: interfaceTx.left
            color: Colors.gray_400
            font: Fonts.body_30
            text: qsTr("Lights")
        }

        Text {
            id: dispBrightnessTxt
            anchors.top: lightsTx.bottom
            anchors.topMargin: 26
            anchors.left: parent.left
            anchors.leftMargin: 32
            font: Fonts.body_24
            color: Colors.gray_100
            text: qsTr("Backlight")
        }

        Slider {
            id: dispBrightnessAdj
            anchors.verticalCenter: dispBrightnessTxt.verticalCenter
            anchors.left: toolheadLedTxt.right
            anchors.leftMargin: 20
            anchors.right: buttonGrid.right
            from: 1
            value: brightness
            to: 100
            onMoved: {
                brightness = value;
                X1PlusNative.updateBacklight(value);
                dispBrightnessChangeTimer.restart();
            }
            background: Rectangle {
                anchors.centerIn: parent
                width: parent.width-12
                height: 10
                radius: height / 2
                color: Colors.gray_600
                
                Rectangle {
                    width: dispBrightnessAdj.visualPosition * parent.width
                    height: parent.height
                    radius: height / 2
                    color: Colors.brand
                }
            }
        }
        
        Text {
            id: toolheadLedTxt
            anchors.top: dispBrightnessTxt.bottom
            anchors.topMargin: 26
            anchors.left: parent.left
            anchors.leftMargin: 32
            font: Fonts.body_24
            color: Colors.gray_100
            text: qsTr("Toolhead LED")
        }

        ZSwitchButton {
            id: toolheadLedButton
            anchors.verticalCenter: toolheadLedTxt.verticalCenter
            anchors.right: buttonGrid.right
            dynamicChecked: DeviceManager.getSetting("cfw_toolhead_led", false)
            onToggled: {
                dynamicChecked = checked
                DeviceManager.putSetting("cfw_toolhead_led", checked);
                X1Plus.sendGcode("M960 S5 P" + (checked ? 1 : 0));
            }
        }
    }

    Component.onCompleted: {
        DeviceManager.maintain.getAccessories();
        // let t  = X1Plus.GpioKeys._loadSettings(false);
        // console.log(t);
    }

    PopupPad {
        id: accessoriesHelpPad
        width: 733
        height: 400
        anchors.right: parent.right
        anchors.rightMargin: 225
        anchors.top: parent.top
        anchors.topMargin: 74
        name: "accessoriesHelpPad"
        closeBtn: true

        contentComponent: Rectangle {
            radius: 15
            color: Colors.gray_600
            Text {
                width: 600
                wrapMode: Text.WordWrap
                anchors.centerIn: parent
                font: Fonts.body_36
                color: Colors.gray_200
                text: qsTr("If you have replaced the accessories, please update the settings below to keep it consistent with the actual condition of the accessory to ensure the print quality")
            }
        }
    }
    PopupPad {
        id: buttonHelpPad
        width: 800
        height: 500
        anchors.right: parent.right
        anchors.rightMargin: 225
        anchors.verticalCenter: parent.verticalCenter
        name: "buttonHelpPad"
        closeBtn: true

        contentComponent: Rectangle {
            radius: 15
            color: Colors.gray_600
            Text {
                width: 670
                wrapMode: Text.WordWrap
                anchors.centerIn: parent
                font: Fonts.body_24
                color: Colors.gray_200
                text: qsTr("<b>You can change the behavior of the hardware buttons on the top of the printer.</b>  A short press is less than 0.85 seconds, and a long press is anything longer than that.<br><br>" +
                           "<b>Reboot</b>: gracefully restarts Linux with 'reboot' command.<br>" +
                           "<b>Set temp</b>: sets nozzle or bed target temperature.<br>" + 
                           "<b>Pause print</b>: pauses current print job.  (Original behavior for red button.)<br>" + 
                           "<b>Abort print</b>: cancels current print job.<br>" +
                           "<b>Sleep/wake</b>: toggles display screen saver.  (Original behavior for black button.)<br>" +
                           "<b>Run macro</b>: executes G-code or Python macro.")
            }
        }
    }
   
}