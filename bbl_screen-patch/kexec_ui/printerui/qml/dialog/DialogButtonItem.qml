import QtQml 2.12

QtObject {
    property string name
    property string title
    property bool visible: true
    property bool isDefault: false
    property bool keepDialog: false // keep dialog open on click

    signal clicked()
}
