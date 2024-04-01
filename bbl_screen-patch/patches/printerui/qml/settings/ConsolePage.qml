import QtQuick 2.12
import QtQuick.Layouts 1.12
import QtQuick.Controls 2.12
import QtQuick.VirtualKeyboard 2.1
import X1PlusNative 1.0
import UIBase 1.0
import Printer 1.0
import '../X1Plus.js' as X1Plus
import "../printer"
import "qrc:/uibase/qml/widgets"
import ".."

Item {
    id: consoleComp
    property var cmdHistory:[]
    property var gencode: X1Plus.GcodeGenerator
    property bool gcodeCmd: DeviceManager.getSetting("cfw_default_console",false);
    property var gcodes: ["ABL On/Off",
                "Coordinates:<br>Absolute",
                "Coordinates:<br>Relative",
                "Disable<br>Endstops",
                "Extruder:<br>Retract",
                "Extruder:<br>Extrude",
                "Fan Speed:<br>Aux",
                "Fan Speed:<br>Chamber",
                "Fan Speed:<br>Part",
                "Gcode<br>Claim<br>Action",
                "Home:<br>XYZ",
                "Home:<br>XY",
                "Home:<br>Low<br>Precision",
                "Input<br>Shaper<br>On/Off",
                "Jerk<br>Limits",
                "K-value",
                "LiDAR:<br>Laser 1",
                "LiDAR:<br>Laser 2",
                "LiDAR:<br>Camera on",
                "LiDAR:<br>Camera off",
                "LiDAR:<br>Camera<br>exposure",
                "LiDAR:<br>Camera<br>capture",
                "LEDs:<br>Nozzle",
                "LEDs:<br>Toolhead",
                "Move<br>Bed Down",
                "Move<br>Bed Up",
                "Move<br>Toolhead",
                "Noise<br>Cancellation<br>Off",
                "Pause<br>(G4)",
                "Pause<br>(M400)",
                "Print Speed:<br>50%",
                "Print Speed:<br>100%" ,
                "Print Speed:<br>120%",
                "Print Speed:<br>166%",
                "Timeline<br>Update",
                "Reset<br>Feed Rate",
                "Reset<br>Flow Rate",
                "Save<br>(M500)",
                "Stepper<br>Current",
                "Temperature:<br>Nozzle",
                "Temperature:<br>Bed",
                "Temperature:<br>Bed + Wait"
                ]
    property var gcode_actions: [
                gencode.G292(1),
                gencode.G90(),
                gencode.G91(),
                gencode.M211({x:0,y:0,z:0}),
                gencode.G1({e: -5, accel: 300}),
                gencode.G1({e: 5, accel: 300}),
                gencode.M106(gencode.FANS.AUX_FAN,255),
                gencode.M106(gencode.FANS.CHAMBER_FAN,255),
                gencode.M106(gencode.FANS.PART_FAN,255),
                gencode.M1002({action_code:3, action:1}),
                gencode.G28(0),
                gencode.G28(4),
                gencode.G28(1),
                gencode.M975(true),
                gencode.M221({x:0,y:0,z:0}),
                gencode.M900(0.01,1,1000),
                gencode.M960({type:gencode.LEDS.LASER_VERTICAL,val:1}),
                gencode.M960({type:gencode.LEDS.LASER_HORIZONTAL,val:1}),
                gencode.M973({action:gencode.OV2740.ON}),
                gencode.M973({action:gencode.OV2740.OFF}),  
                gencode.M973({action:gencode.OV2740.EXPOSE,num:2, expose:600}),
                gencode.M973({action:gencode.OV2740.CAPTURE, num:1, expose:1}),
                gencode.M960({type:gencode.LEDS.LED_NOZZLE,val:1}),
                gencode.M960({type:gencode.LEDS.LED_TOOLHEAD,val:1}),
                gencode.G91() + '\\n' + gencode.G0({z:-10,accel:1200}), 
                gencode.G91() + '\\n' + gencode.G0({z:10,accel:1200}), 
                gencode.G0({x:228,y:253,z:8,accel:1200}),
                gencode.M9822(),
                gencode.M400(50),
                gencode.G4(50),
                gencode.M1009(4),
                gencode.M1009(5),
                gencode.M1009(6),
                gencode.M1009(7),
                gencode.M73(0,18),
                gencode.M221({x:-1,y:-1,z:-1}),
                gencode.M220(),
                gencode.M500(),
                gencode.M17(0.3,0.3,0.3),
                gencode.M109(250),
                gencode.M140(100),
                gencode.M140(55,true)
                ]
    property var cmds: [" $ ","  ( )  "," ` ", "  { }  ","  |  ","  -  ","  &  ","  /  ", "reboot","awk ","cat ", "chmod ","chown ", "chroot", "cp ","date -s ", "dd ", "df ", "echo ","grep", "head ","ifconfig", "iptables ", "kill ","killall ","ln -s","ls -l ","mount ","mv ","pgrep ","pidof","ping -c 1","poweroff","print ","ps aux ", "ps -ef ", "pwd", "remount", "rm ", "sed","sort","tar","test","touch ", "uname -a"]
    property var outputText:""
    property string savePath
    property string space: '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'
    
    MarginPanel {
        id: outputPanel
        width: 1130
        height: parent.height-80 - 150
        anchors.left: parent.left
        anchors.top:  inputPanel.bottom
        anchors.right: parent.right
        bottomMargin: 16
        leftMargin: 26
        topMargin: 5
        rightMargin: 26

        ScrollView {
            id: termScroll
            anchors.top:parent.top
            anchors.topMargin: 18
            anchors.left:parent.left
            anchors.right: parent.right
            anchors.rightMargin: 18
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 18
            anchors.leftMargin:18
            ScrollBar.vertical.interactive: true
            ScrollBar.vertical.policy: outputTextArea.height > termScroll.height ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff
            ScrollBar.horizontal.policy: ScrollBar.AsNeeded
            ScrollBar.horizontal.interactive: true
            clip: true
            TextArea {
                id: outputTextArea
                width: parent.width - 56
                textFormat: Qt.PlainText //RichText is way too slow on the printer
                readOnly: true
                font: outputText.length == 0 ? Fonts.body_24 : Fonts.body_18
                color: Colors.gray_100
                text: outputText
                placeholderText: gcodeCmd 
                    ? qsTr("This interface allows you to send G-code commands to the printer. You can enter commands " +
                        "with the virtual keyboard, or put together commands from the shortcut bar at the bottom of " +
                        "the screen. The printer's G-code parser is somewhat picky; here are some tips for how to placate " +
                        "it: ") +
                    "<br><br>" +
                    qsTr("Commands are case sensitive; the first character of a command is always a capital letter, " +
                        "followed by a number. For example, to set the aux fan to full speed, use M106 P2 S255:") +
                    "<br>" +
                    space + qsTr("M106: G-code command for fan control") + "<br>" +
                    space + qsTr("P2: parameter to select which fan (aux = 2)") + "<br>" +
                    space + qsTr("S255: parameter to set fan speed (0 to 255)") +
                    "<br><br>" +
                    qsTr("For multi-line commands, each G-code command must be separated by the newline escape " +
                        "sequence, \\n. For example:") +
                    "<br>" +
                    space + qsTr("M106 P2 S255\\nG4 S5\\nM106 P2 S0") +
                    "<br><br>" +
                    space + qsTr("Aux fan to 255 -> Wait 5 sec -> Aux fan to 0")
                    : qsTr("This interface allows you to run commands on your printer as root. You can enter commands " +
                        "with the virtual keyboard, or put together commands from the shortcut bar at the bottom of " +
                        "the screen. Commands are executed synchronously, so long-running commands or commands " +
                        "that require user input may hang the UI; use caution! This is intended as a quick diagnostic " +
                        "tool, but for more intensive tasks, consider SSHing to the printer instead.") +
                    "<br><br>" +
                    qsTr("WARNING: It is possible to do permanent, irreversible damage to your printer from a root " +
                        "console. Do not enter commands unless you understand what you are typing.")

                placeholderTextColor: Colors.gray_300
            }
            function scroll(contentOffset){
                // NB: future versions of Qt Quick will have to use flickableItem here, not contentItem
                var maxOffset = outputTextArea.topPadding + outputTextArea.contentHeight + outputTextArea.bottomPadding - height;
                if (maxOffset < 0)
                    maxOffset = 0;
                
                // There is some kind of margin behavior in here that I do
                // not understand.  The `height` is actually 12px higher
                // than I measured it in GIMP.  And contentOffset ends up
                // getting off by 24px!  Life is too long to track down
                // idiosyncracies in old versions of Qt, though, so I sure
                // am not going to waste another single breath on it.
                contentOffset -= 24;
                if (contentOffset < 0)
                    contentOffset = 0;

                // console.log(`I would like to scroll to contentOffset = ${contentOffset}, maxOffset = ${maxOffset}, contentY = ${contentItem.contentY}, height = ${height}, contentItem.height = ${contentItem.height}, originY = ${contentItem.originY}, oTA contentHeight = ${outputTextArea.contentHeight}, oTA height = ${outputTextArea.height}`);
                contentItem.contentY = contentOffset > maxOffset ? maxOffset : contentOffset;
            }

        }

    }

    MarginPanel {
        id: hotkeysPane
        width: parent.width
        height: 120
        anchors.left: parent.left
        anchors.top:  outputPanel.bottom
        anchors.bottom:parent.bottom
        anchors.right: parent.right
        rightMargin: 26
        leftMargin: 26
        topMargin: 5
        bottomMargin:18

        ListView {
            id: hotkeysList
            anchors.top: hotkeysPane.top
            anchors.topMargin: 2   
            width: parent.width
            height: 105
            orientation: ListView.Horizontal
            model: gcodeCmd ? gcodes : cmds
            clip:true
            delegate: Item {
                id: itm
                width: gcodeCmd ? 130 : (index < 8) ? 70 : 130
                height: hotkeysList.height
                ZButton {
                    text: modelData
                    width: parent.width
                    height: hotkeysList.height-10
                    type: ZButtonAppearance.Tertiary
                    textSize: 26
                    textColor: Colors.gray_300
                    backgroundColor: "transparent_pressed"
                    borderColor: "transparent"
                    //cornerRadius: width / 2
                    onClicked: {
                        if (gcodeCmd){
                            if (inputTextBox.text == "") {
                                inputTextBox.text = gcode_actions[index].trim();
                            } else {
                                inputTextBox.text =inputTextBox.text +"\\n"+ gcode_actions[index].trim();
                            }
                        } else {
                            let cmdreplace = cmds[index];
                            if (index < 8) {
                                cmdreplace = cmdreplace.trim();
                                inputTextBox.text = inputTextBox.text + cmdreplace.replace("<br>","");
                            } else {
                                cmdreplace = cmdreplace.trim();
                                inputTextBox.text =cmdreplace.replace("<br>","");
                            }
                        }
                    }
                }


                Rectangle {
                    width: 1
                    height: parent.height-20
                    anchors.left: parent.left
                    color: "#606060"
                    visible: index >0 && itm.width > 1//< model.count - 1 // Hide for the last item
                
                }
            }

            ScrollBar.horizontal: ScrollBar {
                policy: ScrollBar.AlwaysOn
            }

            ScrollBar.vertical: ScrollBar {
                policy: ScrollBar.AlwaysOff
            }
        }
    }

    function timestamp(offset){
        const now = new Date();
        now.setDate(now.getDate()-offset);
        const year = now.getFullYear().toString().slice(2);
        const month = (now.getMonth()+1).toString().padStart(2,'0');
        const day = now.getDate().toString().padStart(2,'0');
        const hrs = now.getHours().toString().padStart(2,'0');
        const mins = now.getMinutes().toString().padStart(2,'0');
        const ms = now.getSeconds().toString().padStart(2,'0');
        return hrs + mins + ms;
    }
    function sendCommand(str){
        console.log("[x1p] executing command ", str);
        try {
            let rs = X1PlusNative.popen(`${str}`);
            console.log("[x1p] executed command ", rs);
            return rs;
        } catch (e) {
            console.log("[x1p] error executing command", e);
            return "";
        }
    }
    MarginPanel{
        id:inputPanel
        property var lastCmd:""
        width: parent.width
        height:80
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        rightMargin: 26
        leftMargin: 26
        topMargin: 26

        Rectangle {
            id: consoleToggle
            anchors.verticalCenter: inputTextBox.verticalCenter
            anchors.left: parent.left
            anchors.leftMargin:60
            //anchors.leftMargin: -5
            height: 70
            width: height * 1.9
            radius: height / 2
            color: Colors.gray_800
            border.color: Colors.gray_500
            border.width: 2
            
            Rectangle {
                width: height
                height: parent.height
                radius: height / 2
                color: Colors.gray_500
                border.color: Colors.gray_400
                border.width: 2
                anchors.verticalCenter: parent.verticalCenter
                x: gcodeCmd ? parent.width - width : 0
                Behavior on x { PropertyAnimation {} }
            }
            
            MouseArea {
                anchors.fill: parent
                onClicked: {
                    gcodeCmd = !gcodeCmd;
                    outputText = "";
                    DeviceManager.putSetting("cfw_default_console", gcodeCmd);
                }
            }
            
            Image {
                source: gcodeCmd ? "../../icon/components/console_shell.svg" : "../../icon/components/console_shell_active.svg"
                height: parent.height * 0.6
                width: height
                anchors.verticalCenter: parent.verticalCenter
                x: parent.height / 2 - height / 2
            }
            
            Image {
                source: gcodeCmd ? "../../icon/components/console_gcode_active.svg" : "../../icon/components/console_gcode.svg"
                height: parent.height * 0.6
                width: height
                anchors.verticalCenter: parent.verticalCenter
                x: parent.width - parent.height / 2 - height / 2
            }
        }

        TextField {
            id: inputTextBox
            height: 80
            anchors.left: consoleToggle.right
            anchors.leftMargin: 0 - leftInset + 15
            anchors.right: enterBtn.left
            anchors.rightMargin:20 - rightInset
            font: Fonts.body_28
            color: Colors.gray_200
            selectByMouse: true
            verticalAlignment: TextInput.AlignVCenter
            inputMethodHints: gcodeCmd ? Qt.ImhAutoUppercase | Qt.ImhPreferUppercase | Qt.ImhPreferNumbers
                                | Qt.ImhSensitiveData | Qt.ImhNoPredictiveText | Qt.ImhLatinOnly
                                : Qt.ImhNoAutoUppercase | Qt.ImhPreferLowercase | Qt.ImhPreferNumbers
                                | Qt.ImhSensitiveData | Qt.ImhNoPredictiveText | Qt.ImhLatinOnly
            placeholderText: gcodeCmd ? qsTr("enter a G-code command")
                                      : qsTr("enter a shell command to run as root")
            placeholderTextColor: Colors.gray_400
            background: Rectangle {
                color: Colors.gray_800
                radius: height / 4
            }
            leftInset: -20
            rightInset: -20
            // taphandler was not working because TextInput already has a MouseArea defined. 
            //I like this idea though (long press to pull up historical commands) but we need
            //to sort out input handling
            /*TapHandler {
                onTapped: {
                    
                }
                onLongPressed: {
                    if (cmdHistory.length == 0){
                        return;
                    }
                    if (i >= cmdHistory.length){
                        i = 0;
                    }
                    inputTextBox.clear();
                    console.log(i, inputTextBox.text);
                    inputTextBox.text = cmdHistory[i];
                    i++;
                }
            }*/
        }

        ZButton { 
            id: enterBtn
            icon: "../../icon/components/console_enter.svg"
            type: ZButtonAppearance.Secondary
            anchors.right: exportBtn.left 
            anchors.rightMargin: 10
            anchors.verticalCenter:inputPanel.verticalCenter
            iconSize: 80
            width: 60
            //cornerRadius: width / 2
            property string out
            property bool printing: PrintManager.currentTask.stage >= PrintTask.WORKING
            onClicked: {
                var inputCmd = inputTextBox.text.trim();
                if (inputCmd.length <1) return;
                
                if (gcodeCmd){
                    
                    try {
                        if (printing) {
                            out = qsTr("Printer is running! Cannot execute gcode now");
                        } else {
                            X1Plus.sendGcode(inputCmd);
                        }
                    } catch (e){
                        
                    }
                    out = qsTr(">Gcode command published to device\n  ") + inputCmd.replace(/\\n/g, '\n  ');
                }  else {
                    
                    out = sendCommand(inputCmd);
                    inputPanel.lastCmd= inputCmd;
                    

                }
                cmdHistory.push(inputCmd);
                if (outputText != "")
                    outputText += "\n\n";
                var origHeight = outputText == "" ? 0 : outputTextArea.contentHeight;
                var ts = timestamp(0) + "[root]:";
                outputText += ts + inputCmd  + "\n" + out;
                if (!gcodeCmd) {
                    termScroll.scroll(origHeight);
                }
                inputTextBox.text = "";
            }
        }


        ZButton{
            id:exportBtn
            icon:"../../icon/components/export.svg"
            iconSize: 50
            width: 50

            anchors.right:parent.right
            anchors.rightMargin:26
            anchors.top:parent.top
            anchors.topMargin:12
            type: ZButtonAppearance.Secondary
            onClicked: {
    
                dialogStack.popupDialog(
                        "TextConfirm", {
                            name: gcodeCmd ? qsTr("Export console log"):qsTr("Export Gcode macro"),
                            type: TextConfirm.YES_NO,
                            defaultButton: 0,
                            text: qsTr("Export console output to a log file?"),
                            onYes: function() {
                                if (gcodeCmd) {
                                    pathDialog(`/mnt/sdcard/x1plus/gcode_${timestamp(0)}.log`,savePath);                 
                                } else {
                                    pathDialog(`/mnt/sdcard/x1plus/console_${timestamp(0)}.log`,savePath);                 
                                }
                                                        
                            },
                        })
            }
        }        
    }

    function pathDialog(inputtxt){
            dialogStack.push("InputPage.qml", {
                                input_head_text : qsTr("Save console output to:"),
                                input_text : inputtxt,
                                max_input_num : 50,
                                isUsePassWord : false,
                                isInputShow : true,
                                isInputting_obj : rect_isInputting_obj,
                                output_obj : savePath});    
        }
    QtObject {
        id: rect_isInputting_obj
        property bool isInputting: false
      
        onIsInputtingChanged: {
            if(!isInputting){
                if (!savePath== ""){
                    console.log(`[x1p] saving console log ${savePath}`);
                    X1PlusNative.saveFile(savePath, outputTextArea.text);
                }
    
                
            }
        }
    }
    Item {
        X1PBackButton {
            id: backBtn
            onClicked: { 
                consoleComp.parent.pop();
            }
        }
    }   
}