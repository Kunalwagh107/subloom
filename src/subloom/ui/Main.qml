import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtMultimedia

ApplicationWindow {
    id: window
    width: 1260; height: 840
    minimumWidth: 900; minimumHeight: 500
    visible: true
    title: "Subloom — local subtitles"
    color: "#090e17"
    property var s: controller.state
    property var mediaPlayer: controller.player
    property string overlay: ""
    property int captionRevision: 0
    property color ink: "#edf1fa"
    property color muted: "#8e9ab0"
    property color blue: "#8b9eff"
    palette.window: "#0b0e14"
    palette.windowText: ink
    palette.base: "#111722"
    palette.text: ink
    palette.button: "#202a3b"
    palette.buttonText: ink
    palette.highlight: "#547fdf"
    palette.highlightedText: "#ffffff"
    palette.alternateBase: "#182235"
    palette.light: "#33425e"
    palette.mid: "#27344b"
    palette.dark: "#090e17"
    palette.placeholderText: muted
    font.family: "Segoe UI"
    font.pixelSize: 13
    function elapsedText(seconds) {
        let h = Math.floor(seconds / 3600)
        let m = Math.floor(seconds / 60) % 60
        return (h > 0 ? h + "h " : "") + (m > 0 ? m + "m " : "") + (seconds % 60) + "s"
    }

    component Action: Button {
        id: action
        property bool primary: false
        property bool quiet: false
        implicitHeight: 40
        font.weight: Font.DemiBold
        padding: 14
        background: Rectangle {
            radius: 10
            color: !action.enabled ? "#171e2b" : action.down ? "#6676db" : action.primary ? "#9aaaff" : action.hovered ? "#2b3851" : action.quiet ? "transparent" : "#202c42"
            border.color: action.activeFocus ? "#c6d0ff" : action.primary ? "#b1bdff" : "#34435e"
            border.width: action.quiet ? 0 : 1
        }
        contentItem: Text {
            text: action.text
            color: !action.enabled ? "#586275" : action.primary ? "#08152e" : "#e8edfa"
            font: action.font
            horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
        }
        Accessible.name: text
    }
    component SmallLabel: Label { color: window.muted; font.pixelSize: 11; font.weight: Font.DemiBold }
    component Card: Rectangle { color: "#111a29"; radius: 16; border.color: "#263650" }
    component Choice: ComboBox {
        id: choice
        implicitHeight: 40
        Layout.fillWidth: true
        enabled: !window.s.busy
        Accessible.name: displayText
        leftPadding: 13; rightPadding: 34
        font.pixelSize: 13
        background: Rectangle {
            radius: 9; color: choice.enabled ? "#182438" : "#141d2d"
            border.color: choice.activeFocus || choice.popup.visible ? window.blue : choice.hovered ? "#50617e" : "#31415c"
        }
        contentItem: Text {
            text: choice.displayText; font: choice.font
            color: choice.enabled ? "#edf2ff" : "#697991"
            verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight
        }
        indicator: Text {
            x: choice.width - width - 13; anchors.verticalCenter: parent.verticalCenter
            text: "⌄"; font.pixelSize: 18; color: choice.enabled ? "#a5b7da" : "#65738c"
        }
        delegate: ItemDelegate {
            id: option
            required property int index
            width: choice.width - 12; height: 42
            text: choice.textAt(index)
            highlighted: choice.highlightedIndex === index
            contentItem: Text {
                text: option.text; color: "#f0f4ff"; font.pixelSize: 13
                verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight
            }
            background: Rectangle { radius: 7; color: option.highlighted || option.hovered ? "#34466e" : "#162136" }
        }
        popup: Popup {
            objectName: "darkChoicePopup"
            y: choice.height + 5; width: choice.width; padding: 6
            implicitHeight: Math.min(contentItem.implicitHeight + 12, 280)
            contentItem: ListView {
                clip: true; implicitHeight: contentHeight
                model: choice.popup.visible ? choice.delegateModel : null
                currentIndex: choice.highlightedIndex
                ScrollIndicator.vertical: ScrollIndicator { }
            }
            background: Rectangle { objectName: "darkChoiceBackground"; color: "#162136"; radius: 10; border.color: "#4a5c82" }
        }
    }
    component TimeInput: TextField {
        color: "#dfe8ff"; selectionColor: "#546eac"; selectedTextColor: "white"
        placeholderTextColor: "#8596b2"; leftPadding: 7; rightPadding: 7
        background: Rectangle { radius: 5; color: "#0d1727"; border.color: parent.activeFocus ? window.blue : "#33445f" }
    }
    component Sheet: Dialog {
        id: sheet
        padding: 22
        palette.windowText: "#edf2ff"; palette.button: "#26344b"; palette.buttonText: "#edf2ff"
        background: Rectangle { color: "#121b2b"; radius: 18; border.color: "#3b4c6c" }
        header: Label { text: sheet.title; color: "#edf2ff"; font.pixelSize: 20; font.weight: Font.DemiBold; padding: 22; bottomPadding: 8 }
        footer: DialogButtonBox {
            standardButtons: sheet.standardButtons
            delegate: Action { }
            padding: 16
            background: Rectangle { color: "transparent" }
            onAccepted: sheet.accept()
            onRejected: sheet.reject()
        }
        Overlay.modal: Rectangle { color: "#bb050a12" }
    }

    Shortcut { sequence: "Ctrl+O"; onActivated: controller.openFile() }
    Shortcut { sequence: "Ctrl+Return"; onActivated: controller.generate() }
    Shortcut { sequence: "Ctrl+Space"; onActivated: controller.togglePlayback() }
    Shortcut { sequence: "F1"; onActivated: helpDialog.open() }
    Connections {
        target: controller
        function onChanged() { window.captionRevision++; window.overlay = controller.captionAt(window.mediaPlayer.position) }
        function onAlert(message) { errorText.text = message; errorDialog.open() }
        function onGpuRetry(message) { gpuText.text = message; gpuDialog.open() }
    }
    Connections {
        target: mediaPlayer
        function onPositionChanged(position) { window.overlay = controller.captionAt(position) }
    }

    Flickable {
        id: workspace
        objectName: "workspace"
        anchors.fill: parent
        contentWidth: width
        contentHeight: content.height + 48
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        interactive: contentHeight > height
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
    ColumnLayout {
        id: content
        x: 24; y: 24
        width: workspace.width - 48
        height: Math.max(workspace.height - 48, 720)
        spacing: 18

        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            Rectangle {
                width: 42; height: 42; radius: 13
                gradient: Gradient { GradientStop { position: 0; color: "#b5bfff" } GradientStop { position: 1; color: "#7885e8" } }
                Text { anchors.centerIn: parent; text: "s"; font.pixelSize: 29; font.weight: Font.Bold; color: "#101a35" }
            }
            ColumnLayout {
                spacing: 0
                Label { text: "subloom"; color: ink; font.pixelSize: 23; font.weight: Font.DemiBold }
                Label { text: "STUDIO  /  LOCAL CAPTIONS"; color: muted; font.pixelSize: 10; font.letterSpacing: 1.2 }
            }
            Item { Layout.fillWidth: true }
            Rectangle {
                width: localLabel.implicitWidth + 26; height: 28; radius: 14; color: "#142a25"
                Label { id: localLabel; anchors.centerIn: parent; text: "●  On-device processing"; color: "#8ed5b0"; font.pixelSize: 11 }
            }
            Action { text: "Help"; quiet: true; onClicked: helpDialog.open() }
            Action { objectName: "settingsButton"; text: "Models & settings"; quiet: true; enabled: !s.busy; onClicked: settingsDialog.open() }
            Action { text: "Open recording"; enabled: !s.busy; onClicked: controller.openFile() }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            Label { text: "01  YOUR RECORDING"; color: s.hasMedia ? blue : ink; font.pixelSize: 11; font.weight: Font.DemiBold }
            Rectangle { Layout.fillWidth: true; height: 1; color: "#273144" }
            Label { text: "02  CHOOSE & CREATE"; color: s.hasMedia ? blue : muted; font.pixelSize: 11; font.weight: Font.DemiBold }
            Rectangle { Layout.fillWidth: true; height: 1; color: "#273144" }
            Label { text: "03  REVIEW & EXPORT"; color: s.count > 0 ? blue : muted; font.pixelSize: 11; font.weight: Font.DemiBold }
        }

        RowLayout {
            Layout.fillWidth: true; Layout.fillHeight: true
            spacing: 18
            ColumnLayout {
                Layout.preferredWidth: window.width * 0.52
                Layout.fillWidth: true; Layout.fillHeight: true
                spacing: 14

                Card {
                    id: previewCard
                    Layout.fillWidth: true; Layout.fillHeight: true
                    Layout.minimumHeight: 170
                    clip: true
                    color: "#080b11"
                    VideoOutput {
                        id: video
                        anchors.fill: parent; anchors.margins: 1
                        visible: s.hasVideo
                        fillMode: VideoOutput.PreserveAspectFit
                        Component.onCompleted: controller.attachVideo(videoSink)
                    }
                    ColumnLayout {
                        anchors.centerIn: parent
                        visible: !s.hasVideo
                        spacing: 14
                        Label { Layout.alignment: Qt.AlignHCenter; text: s.hasMedia ? "♫" : "↓"; font.pixelSize: 44; color: blue }
                        Label { Layout.alignment: Qt.AlignHCenter; text: s.hasMedia ? "Audio recording" : "Great captions. Zero uploads."; font.pixelSize: 23; color: ink; font.weight: Font.DemiBold }
                        Label { Layout.alignment: Qt.AlignHCenter; text: s.hasMedia ? s.filename : "Drop your video or audio here — we'll keep it local."; color: muted; elide: Text.ElideMiddle; Layout.maximumWidth: previewCard.width - 40 }
                        Action { visible: !s.hasMedia; Layout.alignment: Qt.AlignHCenter; text: "Choose a recording"; primary: true; onClicked: controller.openFile() }
                    }
                    Rectangle {
                        visible: overlay.length > 0 && s.hasMedia
                        anchors.horizontalCenter: parent.horizontalCenter
                        anchors.bottom: parent.bottom; anchors.bottomMargin: 20
                        width: Math.min(parent.width - 32, overlayText.implicitWidth + 32)
                        height: overlayText.implicitHeight + 18
                        radius: 5; color: "#d90a0e16"
                        Text { id: overlayText; anchors.centerIn: parent; width: parent.width - 28; text: overlay; color: "white"; textFormat: Text.PlainText; wrapMode: Text.Wrap; horizontalAlignment: Text.AlignHCenter; font.pixelSize: Math.max(16, Math.min(23, previewCard.width / 25)); font.weight: Font.DemiBold }
                    }
                    DropArea {
                        anchors.fill: parent
                        enabled: !s.busy
                        onDropped: drop => { if (drop.hasUrls && drop.urls.length === 1) controller.importUrl(drop.urls[0]); else { errorText.text = "Drop one local recording at a time."; errorDialog.open() } }
                        Rectangle { anchors.fill: parent; visible: parent.containsDrag; color: "#70233760"; border.color: blue; border.width: 2; radius: 12 }
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 5
                    RowLayout {
                        Layout.fillWidth: true
                        Label { text: s.hasMedia ? s.filename : "One recording. Three ways to caption."; color: ink; font.weight: Font.DemiBold; elide: Text.ElideMiddle; Layout.fillWidth: true }
                        Label { text: s.hasMedia ? s.mediaType + " · " + controller.formatTime(s.duration).slice(0, -4) : ""; color: muted; font.pixelSize: 11 }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        Action { text: mediaPlayer.playbackState === MediaPlayer.PlayingState ? "Pause" : "Play"; enabled: s.hasMedia; onClicked: controller.togglePlayback() }
                        Slider {
                            id: seekSlider
                            Layout.fillWidth: true
                            from: 0; to: Math.max(s.duration, 1)
                            value: mediaPlayer.position
                            enabled: s.hasMedia
                            onMoved: controller.seek(Math.round(value))
                            Accessible.name: "Playback position"
                        }
                        Label { text: controller.formatTime(mediaPlayer.position).slice(0, -4); color: muted; font.pixelSize: 11; font.family: "Consolas" }
                    }
                }

                Card {
                    Layout.fillWidth: true
                    implicitHeight: configLayout.implicitHeight + 30
                    ColumnLayout {
                        id: configLayout
                        anchors.fill: parent; anchors.margins: 15
                        spacing: 10
                        RowLayout {
                            Layout.fillWidth: true
                            ColumnLayout {
                                Layout.fillWidth: true; spacing: 5
                                SmallLabel { text: "SUBTITLE OUTPUT" }
                                Choice {
                                    id: modeChoice
                                    objectName: "modeChoice"
                                    model: ["Hinglish (Roman Hindi)", "English translation", "Original transcription"]
                                    currentIndex: ["hinglish", "english", "original"].indexOf(s.mode)
                                    onActivated: controller.setOption("mode", ["hinglish", "english", "original"][currentIndex])
                                }
                            }
                            ColumnLayout {
                                Layout.fillWidth: true; spacing: 5
                                SmallLabel { text: "ACCURACY / MODEL" }
                                Choice {
                                    model: ["Quick draft · Base", "Recommended · Small", "More detail · Medium"]
                                    currentIndex: ["base", "small", "medium"].indexOf(s.model)
                                    onActivated: controller.setOption("model", ["base", "small", "medium"][currentIndex])
                                }
                            }
                        }
                        Label { Layout.fillWidth: true; text: s.mode === "hinglish" ? "Hindi in readable Roman spelling. English terms stay in English." : s.mode === "english" ? "Local audio-to-English translation. May require a second inference pass." : "Recognized speech in its original script, with no extra conversion."; color: muted; wrapMode: Text.Wrap; font.pixelSize: 11 }
                        RowLayout {
                            Layout.fillWidth: true
                            ColumnLayout {
                                Layout.fillWidth: true; spacing: 5
                                SmallLabel { text: "COMPUTE PROFILE" }
                                Choice { model: ["Eco", "Balanced", "Performance"]; currentIndex: model.indexOf(s.profile); onActivated: controller.setOption("profile", currentText) }
                            }
                            ColumnLayout {
                                Layout.fillWidth: true; spacing: 5
                                SmallLabel { text: "PROCESSOR" }
                                Choice { model: ["Auto", "CPU", "GPU"]; currentIndex: model.indexOf(s.device); onActivated: controller.setOption("device", currentText) }
                            }
                            Action {
                                Layout.alignment: Qt.AlignBottom
                                primary: true
                                text: s.modelReady ? "Generate captions" : "Get model"
                                enabled: !s.busy && s.hasMedia
                                onClicked: { if (s.modelReady) controller.generate(); else settingsDialog.open() }
                            }
                        }
                        Label {
                            Layout.fillWidth: true; color: s.gpuAvailable ? "#99d8c0" : muted
                            font.pixelSize: 11; wrapMode: Text.Wrap
                            text: s.gpuAvailable ? "⚡ " + s.gpuName + " · Auto uses GPU in Balanced / Performance" : s.gpuReason
                        }
                        Label {
                            visible: s.decoding === "fast"; Layout.fillWidth: true; color: "#e7c39c"
                            font.pixelSize: 11; wrapMode: Text.Wrap
                            text: "Fast decoding is on · your model is unchanged, but recognition may be less accurate."
                        }
                        Label {
                            visible: s.longRecording; Layout.fillWidth: true; color: "#b5c5ff"
                            font.pixelSize: 11; wrapMode: Text.Wrap
                            text: "Long recording: completed parts save automatically. Generate again to resume with matching settings. English translation needs two local passes."
                        }
                    }
                }
            }

            Card {
                Layout.fillHeight: true; Layout.fillWidth: true
                Layout.preferredWidth: window.width * 0.43
                ColumnLayout {
                    anchors.fill: parent; anchors.margins: 16; spacing: 12
                    RowLayout {
                        Layout.fillWidth: true
                        Label { text: "Captions"; font.pixelSize: 19; font.weight: Font.DemiBold; color: ink }
                        Label { text: s.count > 0 ? s.count + " segments · " + ({"hinglish":"Roman Hindi", "english":"English", "original":"Original"}[s.captionMode] || "Preview") : ""; color: muted; font.pixelSize: 11 }
                        Item { Layout.fillWidth: true }
                        Action { text: "+ Add"; quiet: true; enabled: s.saved && !s.busy; onClicked: controller.addCue() }
                    }
                    Label { text: "Click a time to seek. Edit any word or timestamp."; color: muted; font.pixelSize: 11; Layout.fillWidth: true; wrapMode: Text.Wrap }
                    Rectangle { Layout.fillWidth: true; height: 1; color: "#293244" }
                    Item {
                        Layout.fillWidth: true; Layout.fillHeight: true
                        ColumnLayout {
                            anchors.centerIn: parent
                            width: parent.width - 40
                            visible: s.count === 0
                            spacing: 12
                            Label { Layout.alignment: Qt.AlignHCenter; text: "≡"; font.pixelSize: 38; color: "#4b6085" }
                            Label { Layout.alignment: Qt.AlignHCenter; text: s.busy ? "Working on your recording…" : "Your words will appear here"; color: ink; font.pixelSize: 16 }
                            Label { Layout.fillWidth: true; text: "Choose your output and model, then generate. All speech processing happens on this computer."; color: muted; wrapMode: Text.Wrap; horizontalAlignment: Text.AlignHCenter; lineHeight: 1.3 }
                        }
                        ListView {
                            id: captionsList
                            objectName: "captionsList"
                            anchors.fill: parent; clip: true; spacing: 8
                            model: controller.captionModel
                            reuseItems: false
                            cacheBuffer: 250
                            ScrollBar.vertical: ScrollBar { }
                            delegate: Rectangle {
                                id: cue
                                required property string cueId
                                required property string startTime
                                required property string endTime
                                required property string captionText
                                required property int index
                                width: captionsList.width - 10
                                height: cueLayout.implicitHeight + 22
                                radius: 8; color: "#181f2c"; border.color: textEditor.activeFocus ? blue : "#283246"
                                TapHandler { onTapped: controller.seekCue(cue.cueId) }
                                ColumnLayout {
                                    id: cueLayout
                                    anchors.fill: parent; anchors.margins: 11; spacing: 7
                                    RowLayout {
                                        Layout.fillWidth: true; spacing: 5
                                        Label { text: String(cue.index + 1).padStart(2, "0"); color: muted; font.pixelSize: 10; Layout.preferredWidth: 22 }
                                        TimeInput { id: startEdit; text: cue.startTime; Layout.preferredWidth: 106; implicitHeight: 28; font.pixelSize: 11; font.family: "Consolas"; enabled: !s.busy; selectByMouse: true; Accessible.name: "Caption start time"; onEditingFinished: controller.editCue(cue.cueId, text, endEdit.text, textEditor.text) }
                                        Label { text: "→"; color: muted }
                                        TimeInput { id: endEdit; text: cue.endTime; Layout.preferredWidth: 106; implicitHeight: 28; font.pixelSize: 11; font.family: "Consolas"; enabled: !s.busy; selectByMouse: true; Accessible.name: "Caption end time"; onEditingFinished: controller.editCue(cue.cueId, startEdit.text, text, textEditor.text) }
                                        Item { Layout.fillWidth: true }
                                        ToolButton { text: "↗"; implicitWidth: 26; implicitHeight: 27; Accessible.name: "Seek to caption"; onClicked: controller.seekCue(cue.cueId) }
                                        ToolButton { text: "×"; implicitWidth: 26; implicitHeight: 27; enabled: !s.busy; Accessible.name: "Remove caption"; onClicked: controller.removeCue(cue.cueId) }
                                    }
                                    TextArea {
                                        id: textEditor
                                        Layout.fillWidth: true
                                        text: cue.captionText
                                        wrapMode: TextEdit.Wrap
                                        selectByMouse: true
                                        enabled: !s.busy
                                        color: ink; font.pixelSize: 14
                                        leftPadding: 4; rightPadding: 4; topPadding: 4; bottomPadding: 4
                                        background: Rectangle { color: "transparent" }
                                        Accessible.name: "Caption text"
                                        onTextChanged: { if (activeFocus) editDebounce.restart() }
                                        onActiveFocusChanged: { if (!activeFocus && text !== cue.captionText) controller.editCue(cue.cueId, startEdit.text, endEdit.text, text) }
                                        Timer { id: editDebounce; interval: 250; onTriggered: controller.editCue(cue.cueId, startEdit.text, endEdit.text, textEditor.text) }
                                    }
                                }
                            }
                        }
                    }
                    Label { Layout.fillWidth: true; visible: s.notice.length > 0; text: s.notice; color: "#98b4e7"; wrapMode: Text.Wrap; font.pixelSize: 11 }
                    Rectangle { Layout.fillWidth: true; height: 1; color: "#293244" }
                    RowLayout {
                        Layout.fillWidth: true
                        Choice { id: exportFormat; model: s.hasVideo ? ["SRT", "VTT", "TXT", "MP4"] : ["SRT", "VTT", "TXT"]; Accessible.name: "Export format" }
                        CheckBox { id: timedText; visible: exportFormat.currentText === "TXT"; text: "Times"; checked: false }
                        Action { text: exportFormat.currentText === "MP4" ? "Export video" : "Export captions"; primary: true; enabled: s.count > 0 && !s.busy; onClicked: controller.export(exportFormat.currentText.toLowerCase(), timedText.checked) }
                    }
                    Label { visible: exportFormat.currentText === "MP4"; Layout.fillWidth: true; text: "Burns captions into H.264 video at source resolution and frame rate. Video is re-encoded; compatible audio is copied."; color: muted; wrapMode: Text.Wrap; font.pixelSize: 10 }
                }
            }
        }

        Card {
            Layout.fillWidth: true
            implicitHeight: progressColumn.implicitHeight + 24
            ColumnLayout {
                id: progressColumn
                anchors.fill: parent; anchors.margins: 12; spacing: 8
                RowLayout {
                    Layout.fillWidth: true
                    BusyIndicator { running: s.busy; visible: s.busy; implicitWidth: 22; implicitHeight: 22 }
                    Rectangle { visible: !s.busy; width: 7; height: 7; radius: 4; color: s.error ? "#e6a28b" : "#8ed5b0" }
                    Label { text: s.step; color: ink; elide: Text.ElideRight; Layout.fillWidth: true }
                    Label { visible: s.busy; text: window.elapsedText(s.elapsed) + " elapsed" + (s.progress >= 0 ? " · " + Math.round(s.progress * 100) + "%" : ""); color: muted; font.pixelSize: 11 }
                    Action { visible: s.busy; text: "Cancel"; onClicked: controller.cancel() }
                    Action { visible: s.output.length > 0 && !s.busy; text: "Show export"; quiet: true; onClicked: controller.revealOutput() }
                }
                ProgressBar { visible: s.busy; Layout.fillWidth: true; from: 0; to: 1; value: Math.max(0, s.progress); indeterminate: s.progress < 0 }
                Label { visible: s.output.length > 0 && !s.busy; Layout.fillWidth: true; text: s.output; color: muted; elide: Text.ElideMiddle; font.pixelSize: 11 }
            }
        }
        Label { Layout.alignment: Qt.AlignHCenter; text: "Models download to this computer. Your video/audio never leaves this device."; color: muted; font.pixelSize: 11 }
    }
    }

    Sheet {
        id: helpDialog
        objectName: "helpDialog"
        title: "Subloom · quick start"
        anchors.centerIn: parent
        width: Math.min(window.width - 64, 620)
        height: Math.min(window.height - 64, 570)
        modal: true; standardButtons: Dialog.Close
        contentItem: ScrollView {
            clip: true
            ColumnLayout {
                width: helpDialog.availableWidth - 16; spacing: 16
                Label { text: "Version " + s.version + " · private, local captions"; color: blue; font.weight: Font.DemiBold }
                Label { Layout.fillWidth: true; wrapMode: Text.Wrap; color: ink; text: "1. Open or drop one local recording.\n2. Choose output and a multilingual model in Settings.\n3. Download the model once, or import a verified offline copy.\n4. Generate, review with playback, then edit text and timings.\n5. Export SRT, VTT, TXT or a captioned MP4." }
                Label { Layout.fillWidth: true; wrapMode: Text.Wrap; color: muted; text: "The installer includes the interface, editor, playback, Python/Qt and CPU/media tools. Model weights are separate downloads. Optional NVIDIA support also needs a compatible driver. CPU processing remains available." }
                Label { Layout.fillWidth: true; wrapMode: Text.Wrap; color: muted; text: "Profiles control resources and never replace your model. Fast decoding can reduce accuracy. English translation normally needs a second local pass. Long runs checkpoint completed parts; Generate with matching settings to resume." }
                Label { Layout.fillWidth: true; wrapMode: Text.Wrap; color: "#99d8c0"; text: "Your video/audio never leaves this device. Raw recognition and edits stay separate. Session files contain private text and paths; do not share the local data folder." }
                Label { Layout.fillWidth: true; wrapMode: Text.Wrap; color: muted; text: "Ctrl+O: open · Ctrl+Enter: generate · Ctrl+Space: play/pause\nF1: help · Times: HH:MM:SS.mmm\n\nFull user guide, troubleshooting and license notices are included in the installation folder. Source media is never overwritten. Burned-caption video is re-encoded and is not lossless." }
            }
        }
    }
    Sheet {
        id: settingsDialog
        objectName: "settingsDialog"
        title: "Models & settings"
        anchors.centerIn: parent
        width: Math.min(window.width - 64, 780)
        height: Math.min(window.height - 64, 740)
        modal: true
        standardButtons: Dialog.Close
        background: Rectangle { color: "#151c29"; border.color: "#3a4862"; radius: 12 }
        contentItem: ScrollView {
            clip: true
            ColumnLayout {
                width: settingsDialog.availableWidth - 16
                spacing: 13
                Label { text: "Choose the right fit for your recording"; color: ink; font.pixelSize: 21; font.weight: Font.DemiBold; Layout.fillWidth: true; wrapMode: Text.Wrap }
                Label { text: s.hardware; color: muted }
                Label { text: s.gpuReason; color: s.gpuAvailable ? "#99d8c0" : muted; wrapMode: Text.Wrap; Layout.fillWidth: true; font.pixelSize: 12 }
                SmallLabel { text: "DECODING SPEED" }
                Choice {
                    objectName: "decodingChoice"
                    model: ["Standard · checks more candidates", "Fast · fewer checks, may reduce accuracy"]
                    currentIndex: s.decoding === "fast" ? 1 : 0
                    onActivated: controller.setOption("decoding", currentIndex === 1 ? "fast" : "standard")
                }
                Label { text: "Fast keeps your chosen model. Standard remains the default. Completed parts of long recordings are saved automatically."; color: muted; wrapMode: Text.Wrap; Layout.fillWidth: true; font.pixelSize: 11 }
                Action {
                    visible: s.gpuName.length > 0 && !s.gpuAvailable
                    text: "Enable NVIDIA acceleration · 460 MB"; primary: true; enabled: !s.busy
                    onClicked: gpuInstallDialog.open()
                }
                Label { text: "Multilingual models · GGML F16 · whisper.cpp v1.8.3\nSpeed and quality are relative guidance, not measured guarantees."; color: muted; Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: 12 }
                Repeater {
                    model: s.models
                    delegate: Card {
                        required property var modelData
                        Layout.fillWidth: true
                        implicitHeight: modelColumn.implicitHeight + 28
                        border.color: s.model === modelData.id ? blue : "#2b3548"
                        ColumnLayout {
                            id: modelColumn
                            anchors.fill: parent; anchors.margins: 14; spacing: 6
                            RowLayout {
                                Layout.fillWidth: true
                                Label { text: (modelData.id === "small" ? "Recommended" : modelData.name) + " · Whisper " + modelData.id.charAt(0).toUpperCase() + modelData.id.slice(1); color: ink; font.pixelSize: 15; font.weight: Font.DemiBold; Layout.fillWidth: true }
                                Label { text: (modelData.bytes / 1000000).toFixed(0) + " MB"; color: muted }
                                Action { text: modelData.installed ? (s.model === modelData.id ? "Selected" : "Use") : "Download"; primary: s.model === modelData.id; enabled: !s.busy; onClicked: { controller.setOption("model", modelData.id); if (!modelData.installed) controller.downloadModel() } }
                            }
                            Label { text: modelData.description; color: muted; wrapMode: Text.Wrap; Layout.fillWidth: true; font.pixelSize: 12 }
                            Label { text: (modelData.installed ? "Installed · verified before inference" : "Download required") + "  ·  " + modelData.compatibility; color: modelData.installed ? "#8ed5b0" : "#b2c5ea"; wrapMode: Text.Wrap; Layout.fillWidth: true; font.pixelSize: 11 }
                            Label { text: modelData.reason; color: muted; wrapMode: Text.Wrap; Layout.fillWidth: true; font.pixelSize: 11 }
                        }
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    Action { text: s.modelReady ? "Verify installed model" : "Download selected model"; primary: true; enabled: !s.busy; onClicked: controller.downloadModel() }
                    Action { text: "Import offline model"; enabled: !s.busy; onClicked: controller.importModel() }
                    Action { text: "Delete selected"; enabled: !s.busy && s.modelReady; onClicked: deleteDialog.open() }
                }
                Label { text: s.modelStatus; color: blue; visible: s.modelStatus.length > 0 }
                ProgressBar { visible: s.busy; Layout.fillWidth: true; from: 0; to: 1; value: Math.max(0, s.progress); indeterminate: s.progress < 0 }
                RowLayout {
                    visible: s.busy
                    Layout.fillWidth: true
                    Label { text: s.step; color: ink; Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: 11 }
                    Action { text: "Cancel"; onClicked: controller.cancel() }
                }
                Label { text: "Models download to this computer. Your video/audio never leaves this device."; color: "#8ed5b0"; wrapMode: Text.Wrap; Layout.fillWidth: true; font.pixelSize: 12 }
                RowLayout {
                    Layout.fillWidth: true
                    Label { text: s.model_dir; color: muted; elide: Text.ElideMiddle; Layout.fillWidth: true; font.pixelSize: 11 }
                    Action { text: "Change folder"; enabled: !s.busy; onClicked: controller.chooseModelFolder() }
                }
                RowLayout {
                    Layout.fillWidth: true
                    ColumnLayout {
                        Layout.fillWidth: true
                        SmallLabel { text: "SPOKEN LANGUAGE" }
                        Choice { model: ["Auto-detect", "Hindi / Hinglish", "English"]; currentIndex: ["auto", "hi", "en"].indexOf(s.language); onActivated: controller.setOption("language", ["auto", "hi", "en"][currentIndex]) }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        SmallLabel { text: "AUDIO TRACK" }
                        Choice { model: s.tracks; textRole: "label"; valueRole: "index"; currentIndex: { for (let i=0;i<s.tracks.length;i++) if(s.tracks[i].index===s.track) return i; return -1 } onActivated: controller.setOption("track", currentValue) }
                    }
                }
                Label { text: "Eco uses fewer threads; Performance uses more. Your model choice is always retained.\nFast code-switching and Roman spellings can need correction. Review captions before sharing."; color: muted; wrapMode: Text.Wrap; Layout.fillWidth: true; font.pixelSize: 11 }
            }
        }
    }
    Sheet {
        id: gpuInstallDialog
        title: "Enable NVIDIA acceleration?"
        anchors.centerIn: parent; width: Math.min(window.width - 64, 560); modal: true
        standardButtons: Dialog.Yes | Dialog.No
        contentItem: Label {
            color: ink; wrapMode: Text.Wrap
            text: "Download the pinned Whisper CUDA runtime (460 MB) to this computer. It needs about 1.6 GB of free space during installation. Your media stays local. Your selected model will stay the same."
        }
        onAccepted: controller.enableGPU()
    }
    Sheet {
        id: errorDialog
        title: "Needs attention"
        anchors.centerIn: parent; width: Math.min(window.width - 80, 650)
        modal: true; standardButtons: Dialog.Ok
        contentItem: Label { id: errorText; color: ink; wrapMode: Text.Wrap; textFormat: Text.PlainText }
        background: Rectangle { color: "#202838"; radius: 10; border.color: "#52607a" }
    }
    Sheet {
        id: gpuDialog
        title: "GPU inference needs attention"
        anchors.centerIn: parent; width: Math.min(window.width - 80, 650)
        modal: true
        contentItem: ColumnLayout {
            Label { id: gpuText; Layout.fillWidth: true; wrapMode: Text.Wrap; color: ink }
            Action { text: "Retry on CPU · same model"; primary: true; onClicked: { gpuDialog.close(); controller.retryCPU() } }
            Action { text: "Keep GPU setting"; onClicked: gpuDialog.close() }
        }
    }
    Sheet {
        id: deleteDialog
        title: "Delete Whisper " + s.model + "?"
        anchors.centerIn: parent; modal: true; width: Math.min(window.width - 80, 500)
        standardButtons: Dialog.Yes | Dialog.No
        contentItem: Label { text: "You can import or download this model again. Saved captions are retained."; color: ink; wrapMode: Text.Wrap }
        onAccepted: controller.deleteModel()
    }
}

