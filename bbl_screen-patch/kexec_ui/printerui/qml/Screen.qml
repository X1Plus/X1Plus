/* X1Plus main installer / kexec prompt
 *
 * Copyright (c) 2023 - 2024 Joshua Wise, and the X1Plus authors.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import QtQuick 2.12
import QtQuick.Controls 2.12
import UIBase 1.0
import Printer 1.0
import DdsListener 1.0
import X1PlusNative 1.0

import "qrc:/uibase/qml/widgets"

import "."
import "settings"

Rectangle {
    id: screen
    width: 1280
    height: 720
    color: Colors.gray_500
    
    Component.onCompleted: {
        /* Boot flags set in check_kexec */
        var KEXEC_LAUNCH_INSTALLER = X1PlusNative.getenv("KEXEC_LAUNCH_INSTALLER") || "";
        var BOOT_DIALOG_TIMER = X1PlusNative.getenv("BOOT_DIALOG_TIMER") || 10;        
        var X1P_OTA = X1PlusNative.getenv("X1P_OTA") || "";

        if (KEXEC_LAUNCH_INSTALLER != "") //first stage installer is running, skip dialog
            dialogStack.popupDialog("KexecDialog", { stage1: KEXEC_LAUNCH_INSTALLER, countdown: 0});
        else //normal boot behavior, check_kexec decides whether an OTA update is ready
            dialogStack.popupDialog("KexecDialog", {x1pName:X1P_OTA, countdown: BOOT_DIALOG_TIMER}); 
    }
    
    Component.onDestruction: {
    }

    // https://www.cnblogs.com/linuxAndMcu/p/13667894.html
    EmbededInputPanel {
    }
    
    StackView {
        id: dialogStack
        anchors.fill: parent
        pushEnter: null
        pushExit: null
        popEnter: null
        popExit: null
        replaceEnter: null
        replaceExit: null
        initialItem: Item { objectName: "initialItem" }
        function popupDialog(dialog, args) {
            if (args === undefined) args = {}
            push("Dialog.qml", {url: "dialog/" + dialog + ".qml", args: args})
        }
    }
}
