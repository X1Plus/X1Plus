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
    property int historyIndex: 0

    property bool gcodeConsole: DeviceManager.getSetting("cfw_default_console",false)
    property alias inputText: inputTextBox.text
    property bool printing: PrintManager.currentTask.stage >= PrintTask.WORKING
    property bool ignoreDialog: false
    property var gcodeLibrary: X1Plus.GcodeGenerator
    property var gcodeCommands: [
        {
            name: "History",
            action: "command history"
        },
        {
            name: "ABL On",
            action: gcodeLibrary.G292(1)
        },
        {
            name: "Toolhead:<br>Absolute",
            action: gcodeLibrary.G90()
        },
        {
            name: "Toolhead:<br>Relative",
            action: gcodeLibrary.G91()
        },
        {
            name: "Disable<br>Endstops",
            action: gcodeLibrary.M211({x:0, y:0, z:0})
        },
        {
            name: "Extruder:<br>Retract",
            action: gcodeLibrary.G1({e: -5, accel: 300})
        },
        {
            name: "Extruder:<br>Extrude",
            action: gcodeLibrary.G1({e: 5, accel: 300})
        },
        {
            name: "Fan Speed:<br>Aux",
            action: gcodeLibrary.M106.aux(255)
        },
        {
            name: "Fan Speed:<br>Chamber",
            action: gcodeLibrary.M106.chamber(255)
        },
        {
            name: "Fan Speed:<br>Part",
            action: gcodeLibrary.M106.part(255)
        },
        {
            name: "Skew<br>Correction",
            action: gcodeLibrary.M1005.i(0.001)
        },
        {
            name: "Home:<br>XYZ",
            action: gcodeLibrary.G28.xyz()
        },
        {
            name: "Home:<br>XY",
            action: gcodeLibrary.G28.xy()
        },
        {
            name: "Home:<br>Low<br>Precision",
            action: gcodeLibrary.G28.z_low_precision()
        },
        {
            name: "Input<br>Shaper<br>On/Off",
            action: gcodeLibrary.M975(true)
        },
        {
            name: "Jerk<br>Limits",
            action: gcodeLibrary.M205({x:0, y:0, z:0, e:0})
        },
        {
            name: "K-value",
            action: gcodeLibrary.M900(0.01, 1, 1000)
        },
        {
            name: "Toolhead<br>Laser 1",
            action: gcodeLibrary.M960.laser_vertical(1)
        },
        {
            name: "Toolhead<br>Laser 2",
            action: gcodeLibrary.M960.laser_horizontal(1)
        },
        {
            name: "Toolhead<br>Camera<br>On",
            action: gcodeLibrary.M973.on()
        },
        {
            name: "Toolhead<br>Camera<br>Off",
            action: gcodeLibrary.M973.off()
        },
        {
            name: "Toolhead<br>Camera<br>Exposure",
            action: gcodeLibrary.M973.expose(2, 600)
        },
        {
            name: "Toolhead<br>Camera<br>Capture",
            action: gcodeLibrary.M973.capture(1, 1)
        },
        {
            name: "Toolhead<br>LED",
            action: gcodeLibrary.M960.nozzle(1)
        },
        {
            name: "Z-axis<br>down",
            action: gcodeLibrary.G91() + gcodeLibrary.G0({z:5,accel:200})
        },
        {
            name: "Z-axis<br>up",
            action: gcodeLibrary.G91() + gcodeLibrary.G0({z:-5,accel:200})

        },
        {
            name: "Move<br>toolhead",
            action: gcodeLibrary.G91() + gcodeLibrary.G0({x:228,y:253,z:8,accel:1200})
        },
        {
            name: "Disable<br>Motor<br>Noise<br>Cancellation",
            action: gcodeLibrary.M9822()
        },
        {
            name: "Pause<br>(G4)",
            action: gcodeLibrary.G4(1)
        },
        {
            name: "Pause<br>(M400)",
            action: gcodeLibrary.M400.M400(1)
        },
        {
            name: "Print<br>speed<br>50%",
            action: gcodeLibrary.printSpeed("Silent")
        },
        {
            name: "Print<br>speed<br>100%",
            action: gcodeLibrary.printSpeed("Normal")
        },
        {
            name: "Print<br>speed<br>124%",
            action: gcodeLibrary.printSpeed("Sport")
        },
        {
            name: "Print<br>speed<br>166%",
            action: gcodeLibrary.printSpeed("Ludicrous")
        },
        {
            name: "Timeline<br>Update",
            action: gcodeLibrary.M73(100,0)
        },
        {
            name: "Reset<br>Feed Rate",
            action: gcodeLibrary.M220(100)
        },
        {
            name: "Reset<br>Flow Rate",
            action: gcodeLibrary.M221(100)
        },
        {
            name: "Save<br>settings",
            action: gcodeLibrary.M500()
        },  
        {
            name: "Disable<br>steppers",
            action: gcodeLibrary.M84()
        },  
        {
            name: "Stepper<br>Current",
            action: gcodeLibrary.M17(0.3,0.3,0.3)
        },  
        {
            name: "Nozzle<br>Temp",
            action: gcodeLibrary.M104(250)
        },  
        {
            name: "Nozzle<br>Temp<br>(delay)",
            action: gcodeLibrary.M109(250)
        },  
        {
            name: "Bed<br>Temp",
            action: gcodeLibrary.M140(55)
        },  
        {
            name: "Bed Temp<br>(delay)",
            action: gcodeLibrary.M190(55)
        }

    ]
    property var shellCommands: ["History"," $ ","  ( )  "," ` ", "  { }  ","  |  ","  -  ","  &  ","  /  ", "reboot","awk ","cat ", "chmod ","chown ", "chroot", "cp ","date -s ", "dd ", "df ", "echo ","grep", "head ","ifconfig", "iptables ", "kill ","killall ","ln -s","ls -l ","mount ","mv ","pgrep ","pidof","ping -c 1","poweroff","print ","ps aux ", "ps -ef ", "pwd", "remount", "rm ", "sed","sort","tar","test","touch ", "uname -a"]
    property var outputText:""
    property string savePath
    property string space: '       '

    MarginPanel {
        id: outputPanel
        width: 1130
        height: parent.height - 80 - 150
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
                width: 1130 /* parent.width, but avoiding a binding loop */ - 56
                textFormat: Qt.PlainText //RichText is way too slow on the printer
                readOnly: true
                font: outputText.length == 0 ? Fonts.body_24 : Fonts.body_18
                color: outputText.length == 0 ? Colors.gray_300 : Colors.gray_100
                wrapMode: TextEdit.Wrap
                text: outputText.length != 0 ? outputText :
                      gcodeConsole ? qsTr("This interface allows you to send G-code commands to the printer. You can enter commands " +
                        "with the virtual keyboard, or put together commands from the shortcut bar at the bottom of " +
                        "the screen. The printer's G-code parser is somewhat picky; here are some tips for how to placate " +
                        "it: ") + '\n\n' +
                    qsTr("Commands are case sensitive; the first character of a command is always a capital letter, " +
                        "followed by a number. For example, to set the aux fan to full speed, use M106 P2 S255:") + '\n' +
                    space + qsTr("M106: G-code command for fan control") +'\n' +
                    space + qsTr("P2: parameter to select which fan (aux = 2)") +'\n' +
                    space + qsTr("S255: parameter to set fan speed (0 to 255)") + '\n\n' +
                    qsTr("For multi-line commands, each G-code command must be separated by the newline escape " +
                        "sequence, \\n. For example:") +'\n' +
                    space + qsTr("M106 P2 S255\\nG4 S5\\nM106 P2 S0") + '\n\n' +
                    space + qsTr("Aux fan to 255 -> Wait 5 sec -> Aux fan to 0")
                    : qsTr("This interface allows you to run commands on your printer as root. You can enter commands " +
                        "with the virtual keyboard, or put together commands from the shortcut bar at the bottom of " +
                        "the screen. Commands are executed synchronously, so long-running commands or commands " +
                        "that require user input may hang the UI; use caution! This is intended as a quick diagnostic " +
                        "tool, but for more intensive tasks, consider SSHing to the printer instead.") + '\n\n' +
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
            model: gcodeConsole ? gcodeCommands : shellCommands
            clip:true
            delegate: Item {
                id: itm
                width: (index == 0) ? 100 : gcodeConsole ? 130 : (index < 8) ? 70 : 130
                height: hotkeysList.height
                ZButton {
                    text: gcodeConsole ? modelData.name : modelData
                    width: parent.width
                    height: hotkeysList.height-10
                    type: ZButtonAppearance.Tertiary
                    textSize: 26
                    textColor: Colors.gray_300
                    backgroundColor: "transparent_pressed"
                    borderColor: "transparent"
                    //cornerRadius: width / 2
                    onClicked: {
                        if (index == 0 ){
                            navigateHistory();
                        } else {
                            let commandToAdd = gcodeConsole ? modelData.action : shellCommands[index].trim().replace("<br>", "");
                            if (inputText.trim().length > 0 && gcodeConsole) inputText += "\\n";
                            inputText += commandToAdd;
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
    function navigateHistory() {
        if (cmdHistory.length === 0) return;
        historyIndex = (historyIndex - 1 + cmdHistory.length) % cmdHistory.length;
        inputText = cmdHistory[historyIndex];
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
        try {
            if (gcodeConsole) {
                console.log("[x1p] publishing gcode ", str);
                X1Plus.sendGcode(str);
                cmdHistory.push(str);
                return str;
            } else {
                let rs = X1PlusNative.popen(`${str}`);
                console.log("[x1p] executed command ", rs);
                cmdHistory.push(str);
                return rs;
            }
        } catch (e) {
            console.log("[x1p] error executing command", e);
            return "";
        }
    }

    MarginPanel{
        id:inputPanel
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
                x: gcodeConsole ? parent.width - width : 0
                Behavior on x { PropertyAnimation {} }
            }
            
            MouseArea {
                anchors.fill: parent
                onClicked: {
                    gcodeConsole = !gcodeConsole;
                    outputText = "";
                    inputText = "";
                    DeviceManager.putSetting("cfw_default_console", gcodeConsole);
                    cmdHistory = [];
                    historyIndex = 0;
                }
            }
            
            Image {
                source: gcodeConsole ? "../../icon/components/console_shell.svg" : "../../icon/components/console_shell_active.svg"
                height: parent.height * 0.6
                width: height
                anchors.verticalCenter: parent.verticalCenter
                x: parent.height / 2 - height / 2
            }
            
            Image {
                source: gcodeConsole ? "../../icon/components/console_gcode_active.svg" : "../../icon/components/console_gcode.svg"
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
            text: ""//inputText
            verticalAlignment: TextInput.AlignVCenter
            inputMethodHints: gcodeConsole ? Qt.ImhAutoUppercase | Qt.ImhPreferUppercase | Qt.ImhPreferNumbers
                                | Qt.ImhSensitiveData | Qt.ImhNoPredictiveText | Qt.ImhLatinOnly
                                : Qt.ImhNoAutoUppercase | Qt.ImhPreferLowercase | Qt.ImhPreferNumbers
                                | Qt.ImhSensitiveData | Qt.ImhNoPredictiveText | Qt.ImhLatinOnly
            placeholderText: gcodeConsole ? qsTr("enter a G-code command")
                                      : qsTr("enter a shell command to run as root")
            placeholderTextColor: Colors.gray_400
            background: Rectangle {
                color: Colors.gray_800
                radius: height / 4
            }
            leftInset: -20
            rightInset: -20
            Binding on text {
                value: inputText
            }
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
            onClicked: {
                if (printing && !ignoreDialog) {
                    dialogStack.popupDialog(
                        "TextConfirm", {
                            name: "Limit Frame",
                            type: TextConfirm.YES_NO_CANCEL,
                            titles: [qsTr("Home"), qsTr("Ignore"), qsTr("Close")],
                            text: qsTr("Printer is busy! Are you sure you want to publish this command? Press ignore to hide this message."),
                            onNo: function() {ignoreDialog = true},
                            OnCancel: function () {return},
                    }); 
                }
                var inputCmd = inputText.trim();
                if (inputCmd.length <1) return;
                inputCmd = inputCmd.replace(/\\n/g, '\n  ');
                let response = sendCommand(inputCmd);
                if (response !== "") {
                    if (gcodeConsole) {
                        out = qsTr(">Gcode command published to device\n  ");
                    } else {
                        out = response;
                    }
                    if (outputText != "") outputText += "\n\n";
                    var origHeight = outputText == "" ? 0 : outputTextArea.contentHeight;
                    var ts = timestamp(0) + "[root]:";
                    outputText += ts + inputCmd  + "\n" + out;
                    inputText = "";
                    termScroll.scroll(origHeight);
                }                
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
                            name: gcodeConsole ? qsTr("Export console log"):qsTr("Export Gcode macro"),
                            type: TextConfirm.YES_NO,
                            defaultButton: 0,
                            text: qsTr("Export console output to a log file?"),
                            onYes: function() {
                                if (gcodeConsole) {
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
                                output_obj : inputText});    
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