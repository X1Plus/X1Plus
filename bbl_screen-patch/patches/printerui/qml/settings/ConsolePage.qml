import QtQuick 2.12
import QtQuick.Layouts 1.12
import QtQuick.Controls 2.12
import QtQuick.VirtualKeyboard 2.1
import X1PlusNative 1.0
import UIBase 1.0
import Printer 1.0
import X1PlusProcess 1.0
import '../X1Plus.js' as X1Plus
import "../printer"
import "qrc:/uibase/qml/widgets"
import ".."

Item {
    id: consoleComp
    property var cmdHistory:[[],[]]
    property var idx: -1
    property bool gcodeConsole: X1Plus.Settings.get("consolepage.default",false)
    property alias inputText: inputTextBox.text
    property bool printing: PrintManager.currentTask.stage >= PrintTask.WORKING
    property bool ignoreDialog: false
    property var gcodeCommand: [
        {
            "name": "Command<br>History",
            "action": "",
        }
        ]
    property var shellCommand: [
        {
            "name": "Command<br>History",
            "action": "",
        }
        ]

    property var outputText:""
    property string savePath
    property string space: '       '
    property bool jsonLoaded: false
    

    
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
                width: 1130 - 56
                textFormat: Qt.AutoText //RichText is way too slow on the printer
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
                    space + qsTr("M106 P2 S255\\nG4 S5") + '\n\n' +
                    space + qsTr("Aux fan to 255 -> Wait 5 sec")
                    : qsTr("WARNING: It is possible to do permanent, irreversible damage to your printer from a root " +
                        "console. For any intensive tasks, consider SSHing to the printer instead ")

                placeholderTextColor: Colors.gray_300
            }
            
            function scroll(){
                var contentOffset = outputText == "" ? 0 : outputTextArea.contentHeight;
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

        Flickable {
            id: flickable
            width: parent.width
            anchors.fill: parent
            height: 105
            contentWidth: hotkeysList.contentWidth
            contentHeight: hotkeysList.height
            interactive: true
            flickableDirection: Flickable.HorizontalFlick
            clip: true
            ScrollBar.horizontal: ScrollBar {
                id: horizontalScrollBar
                active: true
                width: flickable.width
                height: 10
                anchors.bottom: flickable.bottom

                contentItem: Rectangle {
                    color: Colors.gray_300
                    radius: 10
                }

                policy: ScrollBar.AsNeeded
                visible: flickable.contentWidth > flickable.width
            }
            ListView {
                id: hotkeysList
                visible: jsonLoaded
                width: parent.width
                height: 105
                orientation: ListView.Horizontal
                model: !jsonLoaded ? null : 
                        gcodeConsole ? gcodeCommand : shellCommand
                clip:true
                Component.onCompleted:{
                    loadJsonData();
                }
                delegate: Item {
                    id: itm
                    width: (index == 0) ? 100 : 130 //: gcodeConsole ? 130 : (index < 9) ? 70 : 130
                    height: parent.height
                    Rectangle {
                        id: hotkeyBtn
                        width: parent.width
                        height: hotkeysList.height - 10
                        color: Colors.gray_600
                        radius: width / 2
                        
                        Text {
                            id: hotkeyTxt
                            anchors.centerIn : parent
                            width: parent.width
                            height: parent.height
                            text: modelData.name
                            color: Colors.gray_300
                            font: Fonts.body_20
                            verticalAlignment: Text.AlignVCenter
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.WordWrap
                        }
                        
                        MouseArea {
                            anchors.fill: parent
                            
                            onClicked: {
                                if (index == 0 ){
                                    navigateHistory();
                                } else {
                                    let commandToAdd = modelData.action.trim().replace("<br>", "");
                                    inputText += commandToAdd;
                                }
                            }
                            onDoubleClicked:{
                                
                            }
                        }
                    }


                    Rectangle {
                        width: 1
                        height: parent.height-20
                        anchors.left: parent.left
                        color: "#606060"
                        visible: index > 0 && itm.width > 1//< model.count - 1 // Hide for the last item
                    
                    }
                }
            }
        
        }
    }
    function loadJsonData(){
        jsonLoaded = false;
        var gcodeJsonPath = X1Plus.Settings.get("consolepage.gcode.json","/usr/etc/macros/gcode_commands.json")
        var shellJsonPath = X1Plus.Settings.get("consolepage.gcode.shell","/usr/etc/macros/shell_commands.json")
        var jsonData = X1Plus.loadJson(gcodeJsonPath);
        if (jsonData){
            jsonData.forEach(function(item) {
                gcodeCommand.push(item);
            });
        } else {
            console.error("Failed to load gcode commands.");
        }
        jsonData = X1Plus.loadJson(shellJsonPath);
        if (jsonData){
            jsonData.forEach(function(item) {
                shellCommand.push(item);
            });
            jsonLoaded = true;
        } else {
            console.error("Failed to load shell commands.");
        }
    }
    function navigateHistory() {
        if (gcodeConsole) {
            idx = Math.max(idx - 1, 0);
            inputText = cmdHistory[0][idx] || "";
        } else {   
            idx = Math.max(idx - 1, 0);
            inputText = cmdHistory[1][idx] || "";
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
        try {
            var inputCmd = str.replace(/\\n/g, '\n  ');
            inputCmd = str.trim();
            var rootStr = "<font color='#AAFF00'>[root@BL-P001]: </font>"
            consoleComp.outputText += `<br>${rootStr} ${inputCmd}<br>`

            if (gcodeConsole) {
                gcodeProc.write(inputCmd + "\n");
                cmdHistory[0].push(inputCmd);
                idx = cmdHistory[0].length;
            } else {
                let commandParts = inputCmd.split(' ')
                if (commandParts.length > 0) {
                    let command = commandParts[0]
                    let args = commandParts.slice(1)
                    shellProcess.start("bash", ["-c", inputCmd]);
                    cmdHistory[1].push(inputCmd);
                    idx = cmdHistory[1].length;
                }
            }
            return inputCmd;
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
                    if (shellProcess.running) shellProcess.terminate();
                    if (gcodeProc.running) gcodeProc.terminate();
                    
                    if (gcodeConsole) {
                        gcodeProc.start("python3",["-u", "/opt/x1plus/bin/log_monitor.py"]);
                    } else {
                        gcodeProc.terminate();
                    }
                    outputText = "";
                    inputText = "";
                    X1Plus.Settings.put("consolepage.default", gcodeConsole);
                   
                    idx = 0;
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
            anchors.right: buttonPanel.left
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
            property var hIndex: -1
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
        Shortcut {
            sequences: ["Stop", "Ctrl+D"]
            onActivated: {
                if (shellProcess.running) shellProcess.terminate();
                if (gcodeProc.running) gcodeProc.terminate();
            }
        }
        
        Component.onCompleted: {
            if (gcodeConsole) {
                gcodeProc.start("python3",["-u", "/opt/x1plus/bin/log_monitor.py"]);
            }
        }
        
        Component.onDestruction: {
            if (shellProcess.running) shellProcess.terminate();
            if (gcodeProc.running) gcodeProc.terminate();
        }

        X1PlusProcess {
            id: shellProcess
            property string output: ""
            property bool running: false
            onStarted: {
                running = true;
            }
            onFinished:{
                outputText += `Finished with exit code ${exitCode} and status ${exitStatus}<br>`
                termScroll.scroll();
                running = false;
            }
            onErrorOccurred: {
                consoleComp.outputText += `Error: ${error}<br>`;
                termScroll.scroll();
                running = false;
            }
            
            onReadyReadStandardOutput: {
                output = "<br>" + shellProcess.readAll().toString().replace(/\n/g, '<br>')
                output.replace('<br><br>','<br>');
                consoleComp.outputText += output;
                termScroll.scroll();
            }
        }
        X1PlusProcess {
            id: gcodeProc
            property string output: ""
            property bool running: false
            onStarted: {
                running = true;
            }
            onFinished:{
                running = false;
            }
            onErrorOccurred: {
                running = false;
            }
            
            onReadyReadStandardOutput: {
                output = gcodeProc.readAll().toString().trim();
                consoleComp.outputText += `${output}`;
                termScroll.scroll();
            }
        }
        
        Rectangle { 
            id: buttonPanel
            anchors.right: parent.right
            anchors.top: parent.top
            width: 140

            property string out
            
            Rectangle {
                id: enterBtn
                width: 70 
                height: 70
                color: "transparent"
                anchors.right: stopBtn.left
                anchors.leftMargin: 15
                ZImage {
                    width: 70 
                    height: 70
                    anchors.fill:parent
                    fillMode: Image.PreserveAspectFit 
                    originSource:  "../../icon/start.svg"
                    tintColor:  (gcodeConsole) ? Colors.gray_300 : (shellProcess.running) ? "orange" : "green"
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        var inputCmd = inputText.trim();
                        if (inputCmd.length <1) return;
                        
                        if (shellProcess.running && !gcodeConsole){
                            shellProcess.write(inputTextBox.text + "\n");
                            consoleComp.outputText += '<br>' + inputTextBox.text + "<br>"
                            inputTextBox.text = "";
                            termScroll.scroll();
                            return;
                        }
                        if (printing && !ignoreDialog) {
                            dialogStack.popupDialog(
                                "TextConfirm", {
                                    name: "Limit Frame",
                                    type: TextConfirm.YES_NO,
                                    titles: [qsTr("Ignore"), qsTr("Close")],
                                    text: qsTr("Printer is busy! Are you sure you want to publish this command? Press ignore to hide this message."),
                                    onYes: function() {ignoreDialog = true},
                                    onNo: function () {return},
                            }); 
                        }
                    
                        
                        inputCmd = inputCmd.replace(/\\n/g, '\n  ');
                        sendCommand(inputCmd);
                        inputText = "";  
                    }
                    onEntered: parent.opacity = 0.8
                    onExited: parent.opacity = 1.0
                }
            }
            Rectangle {
                id: stopBtn
                color: "transparent"
                width: 70 
                height: 70
                anchors.right: parent.right
                ZImage {
                    width: 70 
                    height: 70
                    anchors.fill:parent
                    fillMode: Image.PreserveAspectFit 
                    originSource:  "../../icon/stop.svg"
                    tintColor:  (gcodeConsole) ? Colors.gray_300 : (shellProcess.running) ? "red" :  Colors.gray_300
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        if (shellProcess.running)
                            inputText = "";
                            shellProcess.terminate();
                    }
                    onEntered: parent.opacity = 0.8
                    onExited: parent.opacity = 1.0
                }
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
                    //X1PlusNative.saveFile(savePath, outputTextArea.text);
                }
            }
        }
    }
    Item {
        X1PBackButton {
            id: backBtn
            onClicked: { 
                if (shellProcess.running) shellProcess.terminate();
                if (gcodeProc.running) gcodeProc.terminate();
                consoleComp.parent.pop();
            }
        }
    }   
}