// AIsktagOS: строка меню сверху + плавающий док снизу (в духе macOS)

// ---- Строка меню ----------------------------------------------------------
var menuBar = new Panel;
menuBar.location = "top";
menuBar.height = Math.round(gridUnit * 1.6);
menuBar.floating = false;
menuBar.hiding = "none";

// Меню системы с логотипом AIsktagOS (аналог меню «яблока»)
var menu = menuBar.addWidget("org.kde.plasma.kickoff");
menu.currentConfigGroup = ["General"];
menu.writeConfig("icon", "aisktagos-logo-symbolic");
menu.writeConfig("favoritesPortedToKAstats", true);

// Глобальное меню активного приложения
menuBar.addWidget("org.kde.plasma.appmenu");
menuBar.addWidget("org.kde.plasma.panelspacer");

// Мини-монитор нагрузки процессора: лёгкий график (датчики ksystemstats,
// обновление раз в 2 с). В Plasma 5.27/6 действие по щелчку у него не
// переназначается — щелчок раскрывает подробный график; полный список процессов
// открывается из Центра AIsktagOS (aisktag-welcome --page processes).
if (knownWidgetTypes.indexOf("org.kde.plasma.systemmonitor.cpu") >= 0) {
    menuBar.addWidget("org.kde.plasma.systemmonitor.cpu");
}

var systrayApplet = menuBar.addWidget("org.kde.plasma.systemtray");
// Значки лотка живут во внутреннем контейнере (так и в Plasma 5.27, и в 6):
// уведомления и задачи (прогресс загрузок и копирования) — всегда на виду
var systrayId = systrayApplet.readConfig("SystrayContainmentId");
var systray = systrayId ? desktopById(systrayId) : null;
if (systray) {
    systray.currentConfigGroup = ["General"];
    systray.writeConfig("shownItems", [
        "org.kde.plasma.notifications",
        "org.kde.plasma.networkmanagement",
        "org.kde.plasma.volume",
        "org.kde.plasma.battery"
    ]);
}

var clock = menuBar.addWidget("org.kde.plasma.digitalclock");
clock.currentConfigGroup = ["Appearance"];
clock.writeConfig("showDate", true);
clock.writeConfig("dateDisplayFormat", "BesideTime");
clock.writeConfig("dateFormat", "shortDate");

// ---- Док ------------------------------------------------------------------
var dock = new Panel;
dock.location = "bottom";
// Значки покрупнее: ~64 px при стандартном шрифте
dock.height = Math.round(gridUnit * 3.8);
dock.alignment = "center";
dock.hiding = "dodgewindows";
// Свойства floating (плавающая панель, Plasma 5.25+) и lengthMode (длина по
// содержимому, только Plasma 6) задаём, лишь если они есть у панели: в 5.27
// lengthMode нет, и док центрируется через alignment на всю длину края.
// minimumLength/maximumLength не задаём: в 5.27 они фиксировали бы длину в пикселях.
if ("floating" in dock) {
    dock.floating = true;
}
if ("lengthMode" in dock) {
    dock.lengthMode = "fit";
}

// Все приложения на весь экран (аналог Launchpad)
var launchpad = dock.addWidget("org.kde.plasma.kickerdash");
launchpad.currentConfigGroup = ["General"];
launchpad.writeConfig("icon", "view-app-grid-symbolic");

// Для каждого места в доке — варианты по порядку; берётся первый установленный
var dockApps = [
    ["org.kde.dolphin.desktop"],
    ["firefox.desktop", "org.mozilla.firefox.desktop", "org.kde.falkon.desktop"],
    ["kitty.desktop", "org.kde.konsole.desktop"],
    ["com.microsoft.VSCode.desktop", "code.desktop", "org.kde.kate.desktop"],
    ["org.kde.discover.desktop"],
    ["aisktag-welcome.desktop"],
    ["systemsettings.desktop"]
];
var launchers = [];
for (var a = 0; a < dockApps.length; a++) {
    for (var b = 0; b < dockApps[a].length; b++) {
        if (applicationExists(dockApps[a][b])) {
            launchers.push("applications:" + dockApps[a][b]);
            break;
        }
    }
}

var tasks = dock.addWidget("org.kde.plasma.icontasks");
tasks.currentConfigGroup = ["General"];
tasks.writeConfig("launchers", launchers);
tasks.writeConfig("indicateAudioStreams", true);
tasks.writeConfig("iconSpacing", 2);
// Индикаторы и прогресс на значках: полоса прогресса из Job API (загрузки,
// копирование) и счётчики (LauncherEntry), подсветка окна при наведении,
// приложение, требующее внимания, показывает скрытый док
tasks.writeConfig("smartLaunchersEnabled", true);
tasks.writeConfig("highlightWindows", true);
tasks.writeConfig("showToolTips", true);
tasks.writeConfig("unhideOnAttention", true);
tasks.writeConfig("maxStripes", 1);

dock.addWidget("org.kde.plasma.marginsseparator");
dock.addWidget("org.kde.plasma.trash");

// ---- Обои -----------------------------------------------------------------
var desktopsArray = desktopsForActivity(currentActivity());
for (var j = 0; j < desktopsArray.length; j++) {
    var d = desktopsArray[j];
    d.wallpaperPlugin = "org.kde.image";
    d.currentConfigGroup = ["Wallpaper", "org.kde.image", "General"];
    d.writeConfig("Image", "file:///usr/share/wallpapers/AIsktagOS/");
}
