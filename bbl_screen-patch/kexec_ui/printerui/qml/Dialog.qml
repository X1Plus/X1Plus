import QtQuick 2.12
import QtQuick.Controls 2.12
import UIBase 1.0
import "qrc:/uibase/qml/widgets"


Rectangle {

    property url url
    property var args: ({})

    property var content: loader.item
    property var filterButtons: SortFilterProxyModel {
        sourceModel: content.buttons ? content.buttons : ItemModels.empty
        filterRoleName: "visible"
        filterValue: true
    }
    property var buttons: content.buttons ? filterButtons : null
    property int defaultButton: {
        var items = filterButtons.items
        for (var i = 0; i < items.length; ++i)
            if (items[i].isDefault)
                return i
        return -1
    }
    property bool finished: content.finished === true
    property bool finishChanged: !finished
    property bool hasActivated: false
    property real paddingX: content.paddingX ? content.paddingX : 60
    property real paddingBottom: content.paddingBottom ? content.paddingBottom : 13

    id: dialog
    color: "#B20D0F0D"

    MouseArea {
        anchors.fill: parent
        onPressed: {
            mouse.accepted = true
        }
    }

    StackView.onActivated: {
        hasActivated = true
    }

    onFinishedChanged: {
        // console.log("onFinishedChanged finished " + finished + " finishChanged " + finishChanged)
        if (finished) {
            dismissIfFinished()
        } else {
            finishChanged = true
        }
    }

    function dismiss(immediate = true) {
        if (parent && parent.currentItem === dialog) {
            var stack = parent
            stack.pop(immediate ? StackView.Immediate : StackView.Transition)
            // some stack has no initialItem
            if (parent && parent.currentItem === dialog)
                stack.clear()
            else if (stack.currentItem.dismissIfFinished)
                stack.currentItem.dismissIfFinished();
        }
    }

    function dismissIfFinished() {
        // No problem if initial finished(=true)
        //   dismiss will not work because parent.currentItem is not me
        // But if this are call from another dismiss, the dialog has no chance to show
        //   so use finishChanged to work around
        if (finished && finishChanged && hasActivated) {
            finishChanged = true // stop tracking
            if (parent && parent.currentItem === dialog) {
                console.log("dismissIfFinished " + content)
                dismiss()
            }
        }
    }

    Text {
        id: buttonTexts
        font: Fonts.body_30
        visible: false
        text: {
            if (!buttons)
                return ""
            var text = ""
            var items = buttons.items
            for (var i = 0; i < items.length; ++i)
                text = text + items[i].title
            return text
        }
    }

    Rectangle {
        id: regionBackground
        width: Math.max(
                   (buttons ? (buttons.length * 100 - btnList.spacing
                        + buttonTexts.implicitWidth + 120) : 0),
                   title.width + 210,
                   paddingX + content.width + paddingX,
                   580)
        height: loader.y + content.height
                + (buttons ? (30 + 1 + 13 + 60) : 0) + paddingBottom
        anchors.centerIn: parent
        radius: 15
        color: Colors.gray_500

        Text {
            id: title
            x: 96
            y: 64
            font: Fonts.head_30
            text: content.title ? content.title : ""
            visible: text != ""
        }

        Loader {
            id: loader
            anchors.horizontalCenter: parent.horizontalCenter
            y: title.text === "" ? 50 : 128
        }

        ZLineSplitter {
            id: splitter
            padding: 60
            alignment: Qt.AlignVCenter
            anchors.top: loader.bottom
            anchors.topMargin: 30
            color: Colors.gray_300
            visible: buttons !== null
        }

        ListView {
            id: btnList
            height: 60
            width: splitter.width
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 14
            orientation: Qt.Horizontal
            spacing: 20
            boundsBehavior: Flickable.StopAtBounds
            model: buttons ? buttons : []
            property real paddingX: (width - buttonTexts.width - (model.length - 1) * spacing)
                                    / model.length / 2
            delegate: ZButton {
                height: 60
                type: ZButtonAppearance.Secondary
                backgroundColor: StateColors.get("transparent_pressed")
                paddingX: ListView.view.paddingX
                verticalTapMargin: 10
                text: modelData.title
                checked: false
                onClicked: {
                    var button = modelData
                    console.log("buttonClicked " + button.name)
                    modelData.clicked()
                }
                ZLineSplitter { alignment: Qt.AlignLeft; offset: -10; color: Colors.gray_400; visible: index > 0 }
            }
        }

    }

    Component.onCompleted: {
        loader.setSource(url, args)
    }

    property var buttonClicked
    // TODO: if push new item in callback, StackView's currentItem is wrong.
    //  Why? setCurrentItem is last step of pop,
    //   before that the old item has already been destucted
    //  How? add a small duration pop animation, destruct old item later
    Component.onDestruction: {
        var button = buttonClicked
        if (button)
            button.clicked()
    }
}
