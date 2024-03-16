import QtQuick 2.12

QtObject {
    property var bound: null
    /* it does not seem to be possible to route these through JavaScript, though.  not work dont know why */
    signal sigEvent0()
    signal sigEvent1(var param)
}

