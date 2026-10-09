// AIsktagOS «Hybrid»: рабочий стол «между Windows и Linux».
//   от Windows — панель задач снизу: меню «Пуск», закреплённые приложения, трей, часы, «показать рабочий стол»,
//                 значки на столе, кнопки окна справа;
//   от Linux   — виртуальные рабочие столы в панели, плитки окон, терминал по Ctrl+Alt+T / Meta+Enter,
//                 ИИ-ассистент Mind под рукой (Meta+A).
// Стекло и размытие даёт стиль Plasma «AIsktagOS» (desktoptheme/AIsktagOS).
// Скрипт рассчитан на Plasma 5.27 (Ubuntu 24.04) и на Plasma 6.

var panel = new Panel;
panel.location = "bottom";
panel.height = Math.round(gridUnit * 2.8);
panel.floating = false;
panel.hiding = "none";

// «Пуск»: меню приложений с логотипом AIsktagOS
var start = panel.addWidget("org.kde.plasma.kickoff");
start.currentConfigGroup = ["General"];
start.writeConfig("icon", "aisktagos-logo");
start.writeConfig("favoritesPortedToKAstats", true);

panel.addWidget("org.kde.plasma.marginsseparator");

// Закреплённые приложения. Для каждого места — варианты по порядку, берётся первый установленный.
var pinned = [
    ["aisktag-mind.desktop"],
    ["org.kde.dolphin.desktop"],
    ["firefox.desktop", "org.mozilla.firefox.desktop", "org.kde.falkon.desktop"],
    ["kitty.desktop", "org.kde.konsole.desktop"],
    ["com.microsoft.VSCode.desktop", "code.desktop", "org.kde.kate.desktop"],
    ["org.kde.discover.desktop"],
    ["aisktag-welcome.desktop"],
    ["systemsettings.desktop"]
];
var launchers = [];
for (var a = 0; a < pinned.length; a++) {
    for (var b = 0; b < pinned[a].length; b++) {
        if (applicationExists(pinned[a][b])) {
            launchers.push("applications:" + pinned[a][b]);
            break;
        }
    }
}

var tasks = panel.addWidget("org.kde.plasma.icontasks");
tasks.currentConfigGroup = ["General"];
tasks.writeConfig("launchers", launchers);
tasks.writeConfig("indicateAudioStreams", true);
tasks.writeConfig("highlightWindows", true);   // при наведении на значок подсвечиваются его окна
tasks.writeConfig("iconSpacing", 2);

panel.addWidget("org.kde.plasma.panelspacer");

// Виртуальные рабочие столы (4 штуки, настроены в kwinrc): переключение щелчком, окна перетаскиваются между ними
var pager = panel.addWidget("org.kde.plasma.pager");
pager.currentConfigGroup = ["General"];
pager.writeConfig("showWindowIcons", true);

panel.addWidget("org.kde.plasma.marginsseparator");
panel.addWidget("org.kde.plasma.systemtray");

// Часы в две строки, как в Windows: время и под ним дата
var clock = panel.addWidget("org.kde.plasma.digitalclock");
clock.currentConfigGroup = ["Appearance"];
clock.writeConfig("showDate", true);
clock.writeConfig("dateDisplayFormat", "BelowTime");
clock.writeConfig("dateFormat", "shortDate");
clock.writeConfig("autoFontAndSize", false);
clock.writeConfig("fontFamily", "Inter");
clock.writeConfig("fontWeight", 500);

// Узкая кнопка у правого края: свернуть всё и показать рабочий стол
panel.addWidget("org.kde.plasma.showdesktop");

// ---- Обои -----------------------------------------------------------------
var desktopsArray = desktopsForActivity(currentActivity());
for (var j = 0; j < desktopsArray.length; j++) {
    var d = desktopsArray[j];
    d.wallpaperPlugin = "org.kde.image";
    d.currentConfigGroup = ["Wallpaper", "org.kde.image", "General"];
    d.writeConfig("Image", "file:///usr/share/wallpapers/AIsktagOS/");
}
