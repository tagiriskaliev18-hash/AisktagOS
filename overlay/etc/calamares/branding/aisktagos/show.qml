// Слайды, которые показываются во время копирования файлов.
// Стиль «Cinematic Glass»: тёмный кадр, стеклянная карточка с неоновой кромкой,
// светящийся значок, плавное появление и индикатор слайдов внизу.
// Только QtQuick 2.15 (Qt 5.15 и Qt 6) без QtGraphicalEffects — модуль может отсутствовать в live-системе.
import QtQuick 2.15
import calamares.slideshow 1.0

Presentation {
    id: presentation

    readonly property color cyan: "#22e4ff"
    readonly property color neon: "#3d7bff"

    // Фон под всеми слайдами (без белых полей при любом размере окна)
    Rectangle {
        anchors.fill: parent
        color: "#0a0f1e"
        z: -2
    }
    Image {
        anchors.fill: parent
        source: "slide-bg.jpg"
        fillMode: Image.PreserveAspectCrop
        z: -1
    }

    Timer {
        interval: 9000
        running: true
        repeat: true
        onTriggered: presentation.goToNextSlide()
    }

    component InfoSlide: Slide {
        id: slide
        property string title
        property string body
        property string glyph

        opacity: visible ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 450; easing.type: Easing.OutCubic } }

        // Стеклянная карточка
        Rectangle {
            id: card
            anchors.centerIn: parent
            width: Math.min(parent.width * 0.78, 760)
            height: content.height + 72
            radius: 22
            color: "#b30e1426"
            border.width: 1
            border.color: "#4d8fd8ff"

            // Блик по верхней кромке
            Rectangle {
                anchors { left: parent.left; right: parent.right; top: parent.top; margins: 22 }
                anchors.topMargin: 1
                height: 1
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: "#00ffffff" }
                    GradientStop { position: 0.5; color: "#55ffffff" }
                    GradientStop { position: 1.0; color: "#00ffffff" }
                }
            }

            Column {
                id: content
                anchors.centerIn: parent
                width: parent.width - 80
                spacing: 16

                // Светящийся значок: пульсирующий ореол + кольцо
                Item {
                    width: 96
                    height: 96
                    anchors.horizontalCenter: parent.horizontalCenter
                    Rectangle {
                        anchors.centerIn: parent
                        width: 96; height: 96; radius: 48
                        color: "#2622e4ff"
                        SequentialAnimation on opacity {
                            running: slide.visible
                            loops: Animation.Infinite
                            NumberAnimation { from: 0.35; to: 1.0; duration: 1800; easing.type: Easing.InOutSine }
                            NumberAnimation { from: 1.0; to: 0.35; duration: 1800; easing.type: Easing.InOutSine }
                        }
                    }
                    Rectangle {
                        anchors.centerIn: parent
                        width: 72; height: 72; radius: 36
                        gradient: Gradient {
                            GradientStop { position: 0.0; color: "#1f6dff" }
                            GradientStop { position: 1.0; color: "#0c2a66" }
                        }
                        border.width: 1
                        border.color: presentation.cyan
                    }
                    Text {
                        anchors.centerIn: parent
                        text: glyph
                        font.pixelSize: 34
                        color: "#ffffff"
                    }
                }
                Text {
                    text: title
                    font.family: "Inter"
                    font.pixelSize: 30
                    font.weight: Font.DemiBold
                    color: "#ffffff"
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                }
                // Неоновая черта под заголовком
                Rectangle {
                    width: 64
                    height: 3
                    radius: 1.5
                    anchors.horizontalCenter: parent.horizontalCenter
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0.0; color: presentation.cyan }
                        GradientStop { position: 1.0; color: presentation.neon }
                    }
                }
                Text {
                    text: body
                    font.family: "Inter"
                    font.pixelSize: 17
                    color: "#c9d3f2"
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    lineHeight: 1.3
                }
            }
        }
    }

    InfoSlide {
        glyph: "👋"
        title: "Добро пожаловать в AIsktagOS"
        body: "Привычный рабочий стол как в Windows, свобода Linux и встроенный ИИ — в одной системе. Установка займёт 5–15 минут."
    }
    InfoSlide {
        glyph: "⌘"
        title: "Привычный интерфейс"
        body: "Стеклянная строка меню сверху, парящий док снизу, поиск по Meta+Space (как Spotlight), обзор окон — Meta+W или угол экрана слева снизу."
    }
    InfoSlide {
        glyph: "</>"
        title: "Готова к разработке сразу"
        body: "VS Code, Git, Docker и Podman, Python, Node.js, Rust, компиляторы C/C++, терминал kitty с zsh и подсказками — всё уже установлено."
    }
    InfoSlide {
        glyph: "🎮"
        title: "Любая видеокарта"
        body: "AMD и Intel работают сразу. Для NVIDIA откройте «Менеджер драйверов» — он предложит нужный драйвер в один клик."
    }
    InfoSlide {
        glyph: "⏪"
        title: "Обновления без страха"
        body: "Перед каждым обновлением создаётся снимок системы. Если что-то пошло не так — откат в Timeshift за минуту."
    }
    InfoSlide {
        glyph: "🛍"
        title: "Тысячи приложений"
        body: "Центр приложений Discover: пакеты Ubuntu и магазин Flathub — Telegram, Spotify, Slack, JetBrains, OBS и многое другое."
    }

    // Индикатор слайдов: активная точка вытягивается в неоновую капсулу
    Row {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 26
        spacing: 8
        z: 5
        Repeater {
            model: presentation.slides.length
            Rectangle {
                readonly property bool current: index === presentation.currentSlide
                width: current ? 26 : 8
                height: 8
                radius: 4
                color: current ? presentation.cyan : "#40ffffff"
                Behavior on width { NumberAnimation { duration: 300; easing.type: Easing.OutCubic } }
                Behavior on color { ColorAnimation { duration: 300 } }
            }
        }
    }
}
