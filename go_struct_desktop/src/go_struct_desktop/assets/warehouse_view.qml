import QtQuick
import QtQuick.Controls
import QtQuick3D
import QtQuick3D.Helpers

Item {
    id: root
    property var members: []
    property string viewTitle: "3D PRELIMINARY MODEL"
    property string displayMode: "model"
    property real zoom: 1.0
    property real cameraDistance: 48.0
    property real groundX: 0.0
    property real groundY: 0.0
    property real groundZ: -0.12
    property real groundWidth: 30.0
    property real groundDepth: 20.0
    property real axisX: -15.0
    property real axisY: -10.0
    property real axisZ: -6.0
    property real axisLength: 4.0
    signal memberPicked(int memberId)

    function resetView() {
        root.zoom = 1.0
        orbitOrigin.position = Qt.vector3d(0, 0, 0)
        // Keep the building's global +Z vertical on screen.  This direct
        // camera orientation is the stable warehouse isometric, while the
        // parent remains the orbit/pan pivot used by the controller.
        orbitOrigin.eulerRotation = Qt.vector3d(0, 0, 0)
        camera.position = Qt.vector3d(root.cameraDistance * 0.60, root.cameraDistance * 0.48, root.cameraDistance * 0.76)
        camera.eulerRotation = Qt.vector3d(-25, 38, 0)
    }

    function setView(viewName) {
        root.zoom = 1.0
        var d = root.cameraDistance
        orbitOrigin.position = Qt.vector3d(0, 0, 0)
        orbitOrigin.eulerRotation = Qt.vector3d(0, 0, 0)
        if (viewName === "iso") {
            camera.position = Qt.vector3d(d * 0.60, d * 0.48, d * 0.76)
            camera.eulerRotation = Qt.vector3d(-25, 38, 0)
        } else if (viewName === "front") {
            camera.position = Qt.vector3d(-d, 0, 0)
            camera.lookAt(Qt.vector3d(0, 0, 0))
        } else if (viewName === "back") {
            camera.position = Qt.vector3d(d, 0, 0)
            camera.lookAt(Qt.vector3d(0, 0, 0))
        } else if (viewName === "right") {
            camera.position = Qt.vector3d(0, d, 0)
            camera.lookAt(Qt.vector3d(0, 0, 0))
        } else if (viewName === "left") {
            camera.position = Qt.vector3d(0, -d, 0)
            camera.lookAt(Qt.vector3d(0, 0, 0))
        } else if (viewName === "top") {
            camera.position = Qt.vector3d(0, 0, d)
            camera.lookAt(Qt.vector3d(0, 0, 0))
        } else if (viewName === "bottom") {
            camera.position = Qt.vector3d(0, 0, -d)
            camera.lookAt(Qt.vector3d(0, 0, 0))
        }
    }

    function pickMember(point) {
        var result = scene.pick(point.x, point.y)
        if (result.objectHit && result.objectHit.objectName.indexOf("member-") === 0)
            root.memberPicked(Number(result.objectHit.objectName.substring(7)))
    }

    View3D {
        id: scene
        anchors.fill: parent
        environment: SceneEnvironment {
            clearColor: "#0b1624"
            backgroundMode: SceneEnvironment.Color
            antialiasingMode: SceneEnvironment.MSAA
            antialiasingQuality: SceneEnvironment.High
        }
        camera: camera
        Node {
            id: orbitOrigin
            PerspectiveCamera {
                id: camera
                position: Qt.vector3d(root.cameraDistance * 0.60, root.cameraDistance * 0.48, root.cameraDistance * 0.76)
                eulerRotation: Qt.vector3d(-25, 38, 0)
                clipNear: 0.1
                clipFar: 10000
                onPositionChanged: {
                    if (position.z < 0.5)
                        position = Qt.vector3d(position.x, position.y, 0.5)
                }
            }
        }
        DirectionalLight { eulerRotation: Qt.vector3d(-35, -25, 0); brightness: 1.2 }
        DirectionalLight { eulerRotation: Qt.vector3d(-60, 145, 0); brightness: 0.45 }
        Node {
            id: building
            Model {
            source: "#Cube"
            // Cube's thin local Z is rotated into scene Y, so the slab lies
            // on the engineering X/Y ground plane (scene X/Z).
            position: Qt.vector3d(root.groundX, root.groundZ, root.groundY)
            scale: Qt.vector3d(root.groundWidth / 100.0, root.groundDepth / 100.0, 0.002)
            eulerRotation: Qt.vector3d(90, 0, 0)
            materials: DefaultMaterial { diffuseColor: "#17263a" }
            }
            Repeater3D {
            model: root.members
            delegate: Model {
                source: "#Cylinder"
                objectName: "member-" + modelData.id
                visible: modelData.visible
                pickable: true
                position: Qt.vector3d(modelData.x, modelData.y, modelData.z)
                scale: Qt.vector3d(modelData.selected ? 0.007 : 0.004, modelData.length / 100.0, modelData.selected ? 0.007 : 0.004)
                rotation: Qt.quaternion(modelData.qs, modelData.qx, modelData.qy, modelData.qz)
                materials: DefaultMaterial { diffuseColor: modelData.color }
            }
            }
        }
        // Global coordinate triad.  X = building length (red), Y = building
        // width (green), Z = elevation (blue).  It is deliberately rendered
        // in the same 3D scene, not as a decorative 2D icon.
        Node {
            id: axes
            Model {
                source: "#Cylinder"
                position: Qt.vector3d(root.axisX + root.axisLength / 2, root.axisY, root.axisZ)
                scale: Qt.vector3d(0.025, root.axisLength / 100, 0.025)
                rotation: Qt.quaternion(0.7071068, 0, 0, -0.7071068)
                materials: DefaultMaterial { diffuseColor: "#ef4444" }
            }
            Model {
                source: "#Cylinder"
                position: Qt.vector3d(root.axisX, root.axisY, root.axisZ - root.axisLength / 2)
                scale: Qt.vector3d(0.025, root.axisLength / 100, 0.025)
                rotation: Qt.quaternion(0.7071068, -0.7071068, 0, 0)
                materials: DefaultMaterial { diffuseColor: "#33c481" }
            }
            Model {
                source: "#Cylinder"
                position: Qt.vector3d(root.axisX, root.axisY + root.axisLength / 2, root.axisZ)
                scale: Qt.vector3d(0.025, root.axisLength / 100, 0.025)
                rotation: Qt.quaternion(1, 0, 0, 0)
                materials: DefaultMaterial { diffuseColor: "#4b9cff" }
            }
        }
        OrbitCameraController {
            anchors.fill: parent
            origin: orbitOrigin
            camera: camera
            panEnabled: true
            enabled: true
        }
    }
    DragHandler {
        id: rightMousePan
        target: null
        acceptedButtons: Qt.RightButton
        property point previousTranslation: Qt.point(0, 0)
        onActiveChanged: previousTranslation = Qt.point(0, 0)
        onTranslationChanged: {
            var dx = activeTranslation.x - previousTranslation.x
            var dy = activeTranslation.y - previousTranslation.y
            var scale = root.cameraDistance / Math.max(300, Math.min(root.width, root.height))
            orbitOrigin.position = Qt.vector3d(
                orbitOrigin.position.x - (camera.right.x * dx - camera.up.x * dy) * scale,
                orbitOrigin.position.y - (camera.right.y * dx - camera.up.y * dy) * scale,
                orbitOrigin.position.z - (camera.right.z * dx - camera.up.z * dy) * scale)
            previousTranslation = activeTranslation
        }
    }
    TapHandler {
        acceptedButtons: Qt.LeftButton
        gesturePolicy: TapHandler.DragThreshold
        onTapped: function(eventPoint) { root.pickMember(eventPoint.position) }
    }
    Rectangle {
        anchors.left: parent.left; anchors.top: parent.top; anchors.margins: 12
        color: "#0f2235"; border.color: "#3cc5ba"; border.width: 1; radius: 2
        width: 220; height: 32
        Text { anchors.centerIn: parent; text: root.viewTitle; color: "#e7f5f3"; font.bold: true; font.pixelSize: 12 }
    }
    Rectangle {
        anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 12
        width: 146; height: 34; color: "#0f2235"; border.color: "#46677b"; border.width: 1; radius: 2
        Row {
            anchors.centerIn: parent; spacing: 6
            Rectangle {
                width: 60; height: 24; color: "#17394a"; border.color: "#3cc5ba"; border.width: 1
                Text { anchors.centerIn: parent; text: "ISO"; color: "#e7f5f3"; font.bold: true; font.pixelSize: 11 }
                MouseArea { anchors.fill: parent; onClicked: root.setView("iso") }
            }
            Rectangle {
                width: 60; height: 24; color: "#e76143"
                Text { anchors.centerIn: parent; text: "FIT"; color: "white"; font.bold: true; font.pixelSize: 11 }
                MouseArea { anchors.fill: parent; onClicked: root.resetView() }
            }
        }
    }
    Text {
        anchors.horizontalCenter: parent.horizontalCenter; anchors.bottom: parent.bottom; anchors.bottomMargin: 14
        text: "Left drag: rotate   •   Right drag: pan   •   Wheel: zoom   •   FIT: recover view"
        color: "#91a8b8"; font.pixelSize: 11
    }
    Rectangle {
        anchors.left: parent.left; anchors.bottom: parent.bottom; anchors.margins: 14
        width: 182; height: 52; color: "#0d2032"; border.color: "#46677b"; border.width: 1; radius: 2
        Column {
            anchors.centerIn: parent; spacing: 3
            Text { text: "GLOBAL AXES"; color: "#dbeaf1"; font.bold: true; font.pixelSize: 10 }
            Row {
                spacing: 6
                Text { text: "X"; color: "#ef4444"; font.bold: true; font.pixelSize: 10 }
                Text { text: "length"; color: "#b8cad4"; font.pixelSize: 10 }
                Text { text: "Y"; color: "#33c481"; font.bold: true; font.pixelSize: 10 }
                Text { text: "width"; color: "#b8cad4"; font.pixelSize: 10 }
                Text { text: "Z"; color: "#4b9cff"; font.bold: true; font.pixelSize: 10 }
                Text { text: "elevation"; color: "#b8cad4"; font.pixelSize: 10 }
            }
        }
    }
    Rectangle {
        anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: 14
        visible: root.displayMode !== "model"
        width: 230; height: root.displayMode === "deformed" ? 62 : 112
        color: "#0d2032"; border.color: "#46677b"; border.width: 1; radius: 2
        Column {
            anchors.fill: parent; anchors.margins: 10; spacing: 5
            Text { text: root.displayMode === "utilization" ? "UTILIZATION SCALE" : root.displayMode === "axial" ? "AXIAL FORCE SCALE" : "DEFORMATION"; color: "#eaf6f8"; font.bold: true; font.pixelSize: 11 }
            Row { visible: root.displayMode === "utilization"; spacing: 4
                Repeater { model: [{c:"#38c99b", t:"0–0.60"}, {c:"#f1c453", t:"0.60–0.90"}, {c:"#ef8a45", t:"0.90–1.00"}, {c:"#ef6250", t:"> 1.00"}]
                    delegate: Column {
                        spacing: 3
                        Rectangle { width: 47; height: 12; color: modelData.c }
                        Text { text: modelData.t; color: "#d3e0e6"; font.pixelSize: 9 }
                    }
                }
            }
            Row { visible: root.displayMode === "axial"; spacing: 4
                Repeater { model: [{c:"#ef6250", t:"Compression"}, {c:"#52677c", t:"Low"}, {c:"#36d2ad", t:"Tension"}]
                    delegate: Column {
                        spacing: 3
                        Rectangle { width: 65; height: 12; color: modelData.c }
                        Text { text: modelData.t; color: "#d3e0e6"; font.pixelSize: 9 }
                    }
                }
            }
            Text { visible: root.displayMode === "deformed"; text: "Exaggerated visual shape — values remain in Analysis."; color: "#d3e0e6"; wrapMode: Text.WordWrap; width: 205; font.pixelSize: 10 }
        }
    }
}
