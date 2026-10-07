@echo off
chcp 65001 >nul
rem Склейка частей образа AIsktagOS и проверка контрольной суммы (Windows 10/11).
rem Шаблон: CI подставляет имя ISO и число частей и переводит строки в CRLF.
setlocal EnableDelayedExpansion
cd /d "%~dp0"
set "ISO=@ISO@"
set "PARTS=@PARTS@"

echo AIsktagOS: склеиваю %ISO% из %PARTS% частей...
set /a LAST=%PARTS%-1
set "LIST="
for /l %%i in (0,1,%LAST%) do (
    if not exist "%ISO%.part%%i" (
        echo.
        echo ОШИБКА: нет файла %ISO%.part%%i
        echo Скачайте со страницы релиза ВСЕ части .part0 ... .part%LAST% в эту же папку и запустите снова.
        pause
        exit /b 1
    )
    if defined LIST (set "LIST=!LIST! + "%ISO%.part%%i"") else (set "LIST="%ISO%.part%%i"")
)
copy /b !LIST! "%ISO%" >nul
if errorlevel 1 (
    echo ОШИБКА: не удалось записать %ISO% ^(хватает ли места на диске?^)
    pause
    exit /b 1
)

if exist "%ISO%.sha256" (
    echo Проверяю контрольную сумму, это займёт минуту...
    set /p EXPECTED=<"%ISO%.sha256"
    for /f "tokens=1" %%h in ("!EXPECTED!") do set "EXPECTED=%%h"
    for /f "usebackq delims=" %%h in (`powershell -NoProfile -Command "(Get-FileHash -Algorithm SHA256 -LiteralPath '%ISO%').Hash"`) do set "ACTUAL=%%h"
    if /i "!ACTUAL!"=="!EXPECTED!" (
        echo Контрольная сумма совпала: образ целый.
    ) else (
        echo.
        echo ОШИБКА: образ повреждён ^(контрольная сумма не совпала^).
        echo Скорее всего, одна из частей скачалась не до конца. Скачайте части заново.
        del "%ISO%"
        pause
        exit /b 1
    )
) else (
    echo Файл %ISO%.sha256 не найден — проверка пропущена.
)

echo.
echo Готово: %ISO%
echo Запись на флешку в Rufus: выберите этот ISO, нажмите «СТАРТ», а на вопрос о режиме выберите
echo «Записать в режиме DD-образ». Части .part можно удалить.
pause
