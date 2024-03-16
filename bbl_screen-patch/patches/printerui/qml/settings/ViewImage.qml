import QtQuick 2.12
import QtQuick.Layouts 1.12
import QtQuick.Controls 2.12
import UIBase 1.0
import Printer 1.0


import "qrc:/uibase/qml/widgets"
import ".."

Item {
    id: viewimg
    property string nozzlepath:"file:///mnt/sdcard/x1plus/nozzle_check.jpg"
  
    function setImage(url){
        nozzlepath = url;
    }
    Rectangle {
        width: 1180
        height: 720
        color: Colors.gray_800
        id: img
        
        Rectangle {
            width: 640*1.25
            height:480*1.25
            anchors.centerIn: img
            color: Colors.gray_800
            id: pic
            ZRoundedImage {
                    id: nozzleimg
                    anchors.fill: pic
                    transform:
                        Rotation { origin.x: nozzleimg.width/2; origin.y: nozzleimg.height/2; angle: -270}
                        //Scale {yScale: -1; origin.x: nozzleimg.width/2; origin.y: nozzleimg.height/2}
                    cornerRadius: parent.radius
                    originSource: nozzlepath
            }
        }
        X1PBackButton {
            onClicked: { 
                viewimg.parent.pop();
            }
        }
            
    }
}