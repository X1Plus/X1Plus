import QtQuick 2.0
import QtQuick.Layouts 1.12
import UIBase 1.0
import Printer 1.0
import "qrc:/uibase/qml/widgets"
import "../dialog"
import "../printer"

import "../X1Plus.js" as X1Plus

Item {
    property alias name: textConfirm.objectName
    property var port: ("") /* "a", "b", "c", "d" */
    property var port_id: (`port_${port}`)
    property var port_stat: X1Plus.Expansion.status().ports[port_id]
    property var detected_model: X1Plus.Expansion.moduleTypeInPort(port_id)
    property var detected_moduledb: detected_model && X1Plus.Expansion.database().modules[detected_model]
    
    property var liveconfig: X1Plus.Settings.get(`expansion.${port_id}`, {}) /* XXX: should this be hoisted out into Expander? */
    property var config: liveconfig /* make sure to always config = config; to trigger the binding! */
    property var proposed_module: config.meta && config.meta.module_config || ""
    property var changes_pending: false

    property var buttons: SimpleItemModel {
        DialogButtonItem {
            name: "no"; title: qsTr("Save changes")
            visible: changes_pending
            isDefault: defaultButton == 1
            keepDialog: true
            onClicked: { changes_pending = false; X1Plus.Settings.put(`expansion.${port_id}`, config); }
        }

        DialogButtonItem {
            name: "no"; title: changes_pending ? qsTr("Cancel") : qsTr("Return")
            isDefault: defaultButton == 1
            keepDialog: false
            onClicked: { ; }
        }
    }
    property bool finished: false

    id: textConfirm
    width: 960
    height: layout.height
    
    RowLayout {
        id: layout
        width: 960
        spacing: 0
        
        Image {
            id: moduleIcon
            Layout.preferredWidth: 128
            Layout.preferredHeight: 128
            Layout.rightMargin: 24
            Layout.alignment: Qt.AlignTop | Qt.AlignLeft
            fillMode: Image.PreserveAspectFit
            source: "../../icon/components/mc-board.svg" /* XXX */
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
                text: qsTr("Port %1 configuration").arg(port.toUpperCase())
            }

            Text {
                Layout.columnSpan: 2
                Layout.fillWidth: true
                font: Fonts.body_26
                color: Colors.gray_200
                wrapMode: Text.Wrap
                text: !port_stat ? qsTr("<b>No attached module detected.</b>")
                                 : qsTr("<b>Attached module:</b> %1 (%2)").arg(detected_moduledb && qsTranslate("Expander", detected_moduledb.name) || qsTr("Unknown module")).arg(`${port_stat.model}-${port_stat.revision}-${port_stat.serial}`)
            }

            Text {
                font: Fonts.body_26
                color: Colors.gray_200
                wrapMode: Text.Wrap
                text: qsTr("Use port as:")
            }
            
            /* XXX: complain if port_stat does not match selected module */
            Choise {
                property var modules: Object.entries(X1Plus.Expansion.database().modules)
                Layout.fillWidth: true
                textFont: Fonts.body_26
                listTextFont: Fonts.body_26
                backgroundColor: Colors.gray_600
                currentIndex: modules.findIndex(([k, v]) => k == proposed_module) /* could be -1; that's ok */
                model: modules.map(([k, v]) => `${qsTranslate("Expander", v.name)} (${k})`)

                onCurrentIndexChanged: {
                    let [k, v] = modules[currentIndex];
                    if (config && config.meta && config.meta.module_config && config.meta.module_config == k) {
                        return;
                    }
                    var newconfig = JSON.parse(JSON.stringify(v.configuration)); /* ugh */
                    newconfig.meta = {};
                    newconfig.meta.module_config = k;
                    config = newconfig;
                    changes_pending = true;
                }
            }
            
            ZLineSplitter {
                Layout.fillWidth: true
                Layout.columnSpan: 2
                Layout.topMargin: 10
                Layout.bottomMargin: 10
                alignment: Qt.AlignTop
                padding: 24
                color: Colors.gray_300
                visible: proposedModuleBox.status == Loader.Ready
            }
            
            Loader {
                id: proposedModuleBox
                Layout.columnSpan: 2
                Layout.fillWidth: true
                source: !proposed_module ? "" : `file:///${X1Plus.emulating}/opt/x1plus/share/expansion/${X1Plus.Expansion.database().modules[proposed_module].configuration_ui}`
                
                onSourceChanged: {
                    console.log("Loader source is now ", source);
                }
            }
        }
    }
}
