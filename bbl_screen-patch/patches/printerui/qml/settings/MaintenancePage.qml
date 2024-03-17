import QtQml 2.12
import QtQuick 2.12
import UIBase 1.0
import Printer 1.0
import QtQuick.Controls 2.12
import QtQuick.Layouts 1.12
import UIBase 1.0


import "qrc:/uibase/qml/widgets"
import "../printer"
import ".."

Item {
    id: utilities
    property var maintain: DeviceManager.maintain

     property var mapping: ([
          { "friendly": qsTr("Bed Mesh Calibration"), "page": "../printer/BedMesh.qml", "icon": "../../icon/components/bedlevel.svg" },
          { "friendly": qsTr("Vibration Compensation"), "page": "../printer/VibrationComp.qml",  "icon": "../../icon/components/vibcomp.svg" },
          { "friendly": qsTr("Carbon Rods Clearance"), "page": "DeviceMaintainPage.qml", "loadCompOpen": 0, "icon": "../../icon/components/rods.svg", "dot": maintain.carbon },
          { "friendly": qsTr("Lead Screws Lubrication"), "page": "DeviceMaintainPage.qml", "loadCompOpen": 1, "icon": "../../icon/components/jiayou.svg", "dot": maintain.screws },
          { "friendly": qsTr("Printer Calibration"), "page": "../printer/CalibrationPage.qml", "icon": "../../icon/components/lidar.svg" },
          { "friendly": qsTr("On-Screen Console"), "page": "ConsolePage.qml", "icon": "../../icon/components/console_shell.svg" },
          { "friendly": qsTr("Device Self-test"), "page": "../assist/SelfTestPage.qml", "icon": "../../icon/components/selftest.svg" },
          { "friendly": qsTr("Dry Filament"), "page": "../printer/DryFilamentPage.qml",  "icon": "../../icon/components/filamentdry.svg" }

     ])

     MarginPanel {
          id: infosPanel
          anchors.left: parent.left
          anchors.right: parent.right
          anchors.top: parent.top
          anchors.bottom: parent.bottom
          leftMargin: 10 // 16px outer, adds up to 26px to match BedMesh.qml
          rightMargin: 10
          bottomMargin: 10
          radius: 15
          color: Colors.gray_600

          ListView {
               ScrollBar.vertical: ScrollBar {
                   interactive: true
                   policy: ScrollBar.AlwaysOn
               }
               id: infoList
               anchors.topMargin: 10
               anchors.bottomMargin: 10
               anchors.rightMargin: 10
               boundsBehavior: Flickable.StopAtBounds
               anchors.fill: parent
               clip:true
               interactive:true
               model: mapping
               delegate: infoComp
          }
     }

     Component {
          id: infoComp
          
          Rectangle {
               width: ListView.view.width
               height: 87
               color: modelData.onClicked === undefined ? "transparent" : backColor.color
               radius: 15

               ZLineSplitter {
                    alignment: Qt.AlignTop
                    padding: 23
                    color: "#606060"
                    visible: index > 0
               }
               

               Item {
                    height: parent.height
                    anchors.left: parent.left
                    anchors.leftMargin: 12
                    anchors.right: parent.right
                    anchors.rightMargin: 36
                    MouseArea {
                         anchors.fill: parent
                         onClicked: {
                              pageStack.push(modelData.page)
                              if (modelData.loadCompOpen !== undefined) {
                                  pageStack.currentPage.loadCompOpen(modelData.loadCompOpen)
                              }
                         }
                    }
                    Rectangle {
                        width: parent.width
                        height: 81
                        color: "transparent"
                        radius: 15
                    }
                    Image {
                        id: moduleIcon
                        anchors.verticalCenter: parent.verticalCenter
                        fillMode: Image.PreserveAspectFit
                        anchors.left: parent.left
                        anchors.leftMargin: 24
                        width: height
                        height: parent.height - 18
                        source: modelData.icon
                    }

                    Text {
                        id: infoListTitle
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.left: moduleIcon.right
                        anchors.leftMargin: 10
                        color: Colors.gray_200
                        font: Fonts.body_30
                        text: modelData.friendly
                    }

                    Image {
                        id: menuImage
                        width: height
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.right: parent.right
                        fillMode: Image.Pad
                        horizontalAlignment: Qt.AlignRight
                        source: "../../icon/right.svg"
                    }
                    
                    Rectangle { // dot
                        width: 10
                        height: width
                        radius: width / 2
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.left: parent.left
                        anchors.leftMargin: 10
                        color: "red"
                        visible: !!modelData.dot
                    }
               }

               

               StateColorHandler {
                    id: backColor
                    stateColor: StateColors.get("transparent_pressed")
               }
          }

     }
}
