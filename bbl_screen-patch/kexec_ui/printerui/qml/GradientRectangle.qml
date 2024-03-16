import QtQuick 2.12
import QtQuick.Controls 2.12

Rectangle {
    property var colors

    gradient: Gradient {
        id: gradient
        orientation: Gradient.Horizontal
        stops: colors.length <= 1 ? [] : createStops(colors)

        property Component stop: GradientStop {}
        function createStops(colors) {
            return colors.map((c, i) => stop.createObject(gradient, {
                                          position: i / (colors.length - 1),
                                          color: c}))
        }
    }
}
