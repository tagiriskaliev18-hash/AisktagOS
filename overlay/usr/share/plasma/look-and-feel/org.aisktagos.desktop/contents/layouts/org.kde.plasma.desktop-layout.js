// AIsktagOS: стеклянная строка меню сверху + парящий док снизу (в духе macOS).
// Стекло и размытие даёт стиль Plasma «AIsktagOS Glass» (desktoptheme/AIsktagOS).
// Скрипт рассчитан и на Plasma 5.27 (Ubuntu 24.04), и на Plasma 6.

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
menuBar.addWidget("org.kde.plasma.systemtray");

var clock = menuBar.addWidget("org.kde.plasma.digitalclock");
clock.currentConfigGroup = ["Appearance"];
clock.writeConfig("showDate", true);
clock.writeConfig("dateDisplayFormat", "BesideTime");
clock.writeConfig("dateFormat", "shortDate");
clock.writeConfig("autoFontAndSize", false);
clock.writeConfig("fontFamily", "Inter");
clock.writeConfig("fontWeight", 500);

// ---- Док ------------------------------------------------------------------
var dock = new Panel;
dock.location = "bottom";
dock.height = Math.round(gridUnit * 3.4);
dock.floating = true;
dock.alignment = "center";
dock.hiding = "dodgewindows";
// В Plasma 6 док сам подстраивается по ширине значков; в 5.27 такого режима нет,
// поэтому ширина считается ниже, после добавления значков
var dockFits = typeof dock.lengthMode !== "undefined";
if (dockFits) {
    dock.lengthMode = "fit";
}

// Все приложения на весь экран (аналог Launchpad)
var launchpad = dock.addWidget("org.kde.plasma.kickerdash");
launchpad.currentConfigGroup = ["General"];
launchpad.writeConfig("icon", "view-app-grid-symbolic");
// Тонкий светящийся разделитель (рисуется из widgets/line.svg стиля AIsktagOS Glass)
dock.addWidget("org.kde.plasma.marginsseparator");

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

dock.addWidget("org.kde.plasma.marginsseparator");
dock.addWidget("org.kde.plasma.trash");

if (!dockFits) {
    // Plasma 5.27: значки + Launchpad + корзина + разделители, с запасом под открытые окна
    var dockLength = Math.round((launchers.length + 4) * dock.height * 0.92 + gridUnit * 2);
    dock.minimumLength = dockLength;
    dock.maximumLength = dockLength;
}

// ---- Обои -----------------------------------------------------------------
var desktopsArray = desktopsForActivity(currentActivity());
for (var j = 0; j < desktopsArray.length; j++) {
    var d = desktopsArray[j];
    d.wallpaperPlugin = "org.kde.image";
    d.currentConfigGroup = ["Wallpaper", "org.kde.image", "General"];
    d.writeConfig("Image", "file:///usr/share/wallpapers/AIsktagOS/");
}
