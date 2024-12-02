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
    property var module_detected_dbent: X1Plus.Expansion.database().modules[port_stat.module_detected] /* indexing with undefined is undefined, so we're good */
    
    property var liveconfig: port_stat.config
    property var config: liveconfig /* make sure to always config = config; to trigger the binding! */
    property var proposed_module: config.meta && config.meta.module_config || ""
    property var changes_pending: false
    property var did_override: null
    
    function switchConfig(k) {
        var newconfig = JSON.parse(JSON.stringify(X1Plus.Expansion.database().modules[k].configuration)); /* ugh */
        newconfig.meta = {};
        newconfig.meta.module_config = k;
        config = newconfig;
        changes_pending = true;
    }

    property var buttons: SimpleItemModel {
        DialogButtonItem {
            name: "no"; title: qsTr("Save changes")
            visible: changes_pending
            isDefault: defaultButton == 1
            keepDialog: true
            onClicked: { changes_pending = false; did_override = false; X1Plus.Settings.put(`expansion.${port_id}`, config); }
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
            source: "../../icon/components/addon-module.png"
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
                text: !port_stat.module_detected ? qsTr("<b>No attached module detected.</b>")
                                                 : qsTr("<b>Attached module:</b> %1 (%2)").arg(module_detected_dbent && qsTranslate("Expander", module_detected_dbent.name) || qsTr("Unknown module")).arg(`${port_stat.model}-${port_stat.revision}-${port_stat.serial}`)
            }
            
            Component.onCompleted: {
                if (port_stat.module_detected && (port_stat.module_detected != proposed_module) && X1Plus.Expansion.database().modules[port_stat.module_detected]) {
                    /* XXX: make x1plusd do this on boot, too */
                    switchConfig(port_stat.module_detected);
                    did_override = true;
                }
            }
            
            Text {
                font: Fonts.body_26
                color: Colors.warning
                wrapMode: Text.Wrap
                visible: did_override
                Layout.columnSpan: 2
                Layout.fillWidth: true
                text: qsTr("<b>Port was previously not configured for this module.  Saving changes will overwrite any previous configuration.</b>")
            }

            Text {
                font: Fonts.body_26
                color: Colors.gray_200
                wrapMode: Text.Wrap
                text: qsTr("<b>Use port as:</b>")
                visible: module_detected_dbent == null
            }
            
            Choise {
                property var modules: [["", null], ...Object.entries(X1Plus.Expansion.database().modules)]
                Layout.fillWidth: true
                textFont: Fonts.body_26
                listTextFont: Fonts.body_26
                backgroundColor: Colors.gray_600
                currentIndex: modules.findIndex(([k, v]) => k == proposed_module) /* could be -1; that's ok */
                model: modules.map(([k, v]) => k == "" ? qsTr("None") : v ? `${qsTranslate("Expander", v.name)} (${k})` : qsTranslate("Expander", k))
                visible: module_detected_dbent == null

                onCurrentIndexChanged: {
                    let [k, v] = modules[currentIndex];
                    if (k == "" && proposed_module != "") {
                        /* special case for "none" */
                        config = {};
                        changes_pending = true;
                        return;
                    }
                    if (config && proposed_module == k) {
                        return;
                    }
                    switchConfig(k);
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
