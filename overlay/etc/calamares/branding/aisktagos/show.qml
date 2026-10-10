// Слайды, которые показываются во время копирования файлов.
// Единый стиль Mind: тёмный кадр, стеклянная карточка с объёмной тенью, «орб» с иконкой Mind
// (фиолетово-синий градиент, переливается), появление с пружиной (bounce-in) и индикатор слайдов.
// Только QtQuick 2.15 (Qt 5.15 и Qt 6) без QtGraphicalEffects — модуль может отсутствовать в live-системе.
import QtQuick 2.15
import calamares.slideshow 1.0

Presentation {
    id: presentation

    // Единый стиль Mind: фиолетово-синий градиент (MindKit tokens.json)
    readonly property color g1: "#a46cf0"
    readonly property color g2: "#7c66df"
    readonly property color g3: "#5b8dee"
    readonly property color g4: "#49b3f7"
    // Пружина как cubic-bezier(0.34, 1.56, 0.64, 1) в вебе
    readonly property real springOvershoot: 2.2

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
        // Имя иконки Mind из папки icons/ (SVG с фиолетово-синим градиентом, без эмодзи)
        property string icon

        opacity: visible ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 450; easing.type: Easing.OutCubic } }

        // Объёмная тень под карточкой (без QtGraphicalEffects: несколько полупрозрачных слоёв)
        Repeater {
            model: 3
            Rectangle {
                anchors.centerIn: card
                anchors.verticalCenterOffset: 10 + index * 6
                width: card.width + 12 + index * 14
                height: card.height + index * 10
                radius: card.radius + 6 + index * 6
                color: "#1a140a3c"
                scale: card.scale
            }
        }

        // Стеклянная карточка с градиентной кромкой; появляется с пружиной (bounce-in)
        Rectangle {
            id: card
            anchors.centerIn: parent
            width: Math.min(parent.width * 0.78, 760)
            height: content.height + 72
            radius: 22
            gradient: Gradient {
                GradientStop { position: 0.0; color: "#cc1d1a40" }
                GradientStop { position: 1.0; color: "#cc110f2a" }
            }
            border.width: 1
            border.color: "#59a46cf0"
            scale: slide.visible ? 1.0 : 0.92
            Behavior on scale {
                NumberAnimation { duration: 620; easing.type: Easing.OutBack; easing.overshoot: presentation.springOvershoot }
            }

            // Блик по верхней кромке (3D-вставка)
            Rectangle {
                anchors { left: parent.left; right: parent.right; top: parent.top; margins: 22 }
                anchors.topMargin: 1
                height: 1
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: "#00ffffff" }
                    GradientStop { position: 0.5; color: "#66ffffff" }
                    GradientStop { position: 1.0; color: "#00ffffff" }
                }
            }

            Column {
                id: content
                anchors.centerIn: parent
                width: parent.width - 80
                spacing: 16

                // Значок-«орб» Mind: пульсирующий ореол, вращающееся градиентное кольцо, иконка
                Item {
                    id: orb
                    width: 104
                    height: 104
                    anchors.horizontalCenter: parent.horizontalCenter
                    scale: slide.visible ? 1.0 : 0.4
                    Behavior on scale {
                        NumberAnimation { duration: 760; easing.type: Easing.OutBack; easing.overshoot: presentation.springOvershoot }
                    }
                    Rectangle {
                        anchors.centerIn: parent
                        width: 104; height: 104; radius: 52
                        color: "#337c66df"
                        SequentialAnimation on opacity {
                            running: slide.visible
                            loops: Animation.Infinite
                            NumberAnimation { from: 0.35; to: 1.0; duration: 1800; easing.type: Easing.InOutSine }
                            NumberAnimation { from: 1.0; to: 0.35; duration: 1800; easing.type: Easing.InOutSine }
                        }
                    }
                    // Кольцо: круг с градиентом медленно вращается — градиент «переливается»
                    Rectangle {
                        anchors.centerIn: parent
                        width: 78; height: 78; radius: 39
                        gradient: Gradient {
                            GradientStop { position: 0.0; color: presentation.g1 }
                            GradientStop { position: 0.33; color: presentation.g2 }
                            GradientStop { position: 0.67; color: presentation.g3 }
                            GradientStop { position: 1.0; color: presentation.g4 }
                        }
                        RotationAnimation on rotation {
                            running: slide.visible
                            loops: Animation.Infinite
                            from: 0; to: 360
                            duration: 6000
                        }
                    }
                    // Тёмная «линза» внутри кольца с бликом сверху
                    Rectangle {
                        anchors.centerIn: parent
                        width: 72; height: 72; radius: 36
                        gradient: Gradient {
                            GradientStop { position: 0.0; color: "#2a2558" }
                            GradientStop { position: 1.0; color: "#110f2a" }
                        }
                        Rectangle {
                            anchors.horizontalCenter: parent.horizontalCenter
                            y: 5
                            width: 40; height: 14; radius: 7
                            color: "#14ffffff"
                        }
                    }
                    Image {
                        anchors.centerIn: parent
                        width: 38; height: 38
                        sourceSize.width: 76
                        sourceSize.height: 76
                        source: slide.icon ? "icons/" + slide.icon + ".svg" : ""
                        smooth: true
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
                // Переливающаяся черта под заголовком: широкая полоса градиента едет внутри рамки
                Item {
                    width: 88
                    height: 4
                    clip: true
                    anchors.horizontalCenter: parent.horizontalCenter
                    Rectangle {
                        width: parent.width * 3
                        height: parent.height
                        radius: 2
                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: 0.0; color: presentation.g1 }
                            GradientStop { position: 0.17; color: presentation.g2 }
                            GradientStop { position: 0.33; color: presentation.g3 }
                            GradientStop { position: 0.5; color: presentation.g4 }
                            GradientStop { position: 0.67; color: presentation.g3 }
                            GradientStop { position: 0.83; color: presentation.g2 }
                            GradientStop { position: 1.0; color: presentation.g1 }
                        }
                        NumberAnimation on x {
                            running: slide.visible
                            loops: Animation.Infinite
                            from: 0; to: -88 * 2
                            duration: 6000
                        }
                    }
                }
                Text {
                    text: body
                    font.family: "Inter"
                    font.pixelSize: 17
                    color: "#cfcdf2"
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    lineHeight: 1.3
                }
            }
        }
    }

    InfoSlide {
        icon: "sparkles"
        title: "Добро пожаловать в AIsktagOS"
        body: "Удобство macOS, свобода Linux Mint и мощь Ubuntu LTS — в одной системе. Установка займёт 5–15 минут."
    }
    InfoSlide {
        icon: "keyboard"
        title: "Привычный интерфейс"
        body: "Стеклянная строка меню сверху, парящий док снизу, поиск по Meta+Space (как Spotlight), обзор окон — Meta+W или угол экрана слева снизу."
    }
    InfoSlide {
        icon: "code"
        title: "Готова к разработке сразу"
        body: "VS Code, Git, Docker и Podman, Python, Node.js, Rust, компиляторы C/C++, терминал kitty с zsh и подсказками — всё уже установлено."
    }
    InfoSlide {
        icon: "gpu"
        title: "Любая видеокарта"
        body: "AMD и Intel работают сразу. Для NVIDIA откройте «Менеджер драйверов» — он предложит нужный драйвер в один клик."
    }
    InfoSlide {
        icon: "history"
        title: "Обновления без страха"
        body: "Перед каждым обновлением создаётся снимок системы. Если что-то пошло не так — откат в Timeshift за минуту."
    }
    InfoSlide {
        icon: "store"
        title: "Тысячи приложений"
        body: "Центр приложений Discover: пакеты Ubuntu и магазин Flathub — Telegram, Spotify, Slack, JetBrains, OBS и многое другое."
    }

    // Индикатор слайдов: активная точка вытягивается в градиентную капсулу с пружиной
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
                color: "#40ffffff"
                Behavior on width { NumberAnimation { duration: 420; easing.type: Easing.OutBack; easing.overshoot: presentation.springOvershoot } }
                Rectangle {
                    anchors.fill: parent
                    radius: parent.radius
                    opacity: parent.current ? 1 : 0
                    Behavior on opacity { NumberAnimation { duration: 300 } }
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0.0; color: presentation.g1 }
                        GradientStop { position: 1.0; color: presentation.g4 }
                    }
                }
            }
        }
    }
}
