import QtQuick 2.12
import QtQml 2.12
import QtQuick.VirtualKeyboard 2.1
import QtQuick.VirtualKeyboard.Settings 2.1

// TODO: there is a timer keep running, who is it?
//   PauseAnimationJob( 0x1f7e387c860 ) duration: 530

InputPanel {

    id: inputPanel
    anchors.left: parent.left
    anchors.right: parent.right
    y: parent.height
    externalLanguageSwitchEnabled: true

    Component.onCompleted: {
        VirtualKeyboardSettings.styleName = "bbl"
    }

    states: State {
        name: "visible"
        /*  The visibility of the InputPanel can be bound to the Qt.inputMethod.visible property,
            but then the handwriting input panel and the keyboard input panel can be visible
            at the same time. Here the visibility is bound to InputPanel.active property instead,
            which allows the handwriting panel to control the visibility when necessary.
        */
        when: inputPanel.active
        PropertyChanges {
            target: inputPanel
            y: parent.height - inputPanel.height
        }
    }
    transitions: Transition {
        id: inputPanelTransition
        from: ""
        to: "visible"
        reversible: true
        enabled: !VirtualKeyboardSettings.fullScreenMode
        ParallelAnimation {
            NumberAnimation {
                properties: "y"
                duration: 250
                easing.type: Easing.InOutQuad
            }
        }
    }

    onActiveChanged: {
        console.log("EmbededInputPanel onActiveChanged " + active)
    }

    Binding {
        target: InputContext
        property: "animating"
        value: inputPanelTransition.running
        //restoreMode: Binding.RestoreBinding
    }
}
