#Requires -Version 5.1
<#
.SYNOPSIS
    Загружает код Jarvis с этого компьютера в ЗАКРЫТЫЙ репозиторий GitHub tagiriskaliev18-hash/jarvis.

.DESCRIPTION
    1. Ставит Git через winget, если его нет.
    2. Находит папку Jarvis: параметр -Path, ярлык или папка «Jarvis» на рабочем столе, типичные места
       (%USERPROFILE%\jarvis, Документы, Projects, C:\jarvis); если не нашёл или нашёл несколько — спросит.
    3. Копирует код во временную папку БЕЗ секретов и мусора: .env, ключи (*.pem, *.key), виртуальные
       окружения, node_modules, кэши, файлы больше 50 МБ. В копии значения ключей API (sk-…, gsk_…, AIza…,
       hf_…, ghp_… и т. п.) заменяются на <СКРЫТО>. Оригинал на диске НЕ меняется.
    4. Входит в GitHub через браузер (Git Credential Manager), создаёт закрытый репозиторий jarvis
       и отправляет туда код. Повторный запуск отправляет новую версию.

    Запуск: двойной щелчок по Upload-Jarvis.bat, или:
        powershell -ExecutionPolicy Bypass -File .\Upload-Jarvis.ps1 -Path D:\Jarvis
#>
[CmdletBinding()]
param(
    [string]$Path = "",
    [string]$Owner = "tagiriskaliev18-hash",
    [string]$Repo = "jarvis"
)

$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
function Say([string]$Text) { Write-Host "==> $Text" -ForegroundColor Cyan }
function Warn([string]$Text) { Write-Host "ВНИМАНИЕ: $Text" -ForegroundColor Yellow }
function Fail([string]$Text) { Write-Host "Ошибка: $Text" -ForegroundColor Red; exit 1 }

# ------------------------------------------------------------------- Git --
function Get-Git {
    $g = Get-Command git.exe -ErrorAction SilentlyContinue
    if ($g) { return $g.Source }
    Say 'Устанавливаю Git…'
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Start-Process 'https://git-scm.com/download/win'
        Fail 'winget не найден. Установите Git со страницы, которая открылась, и запустите скрипт снова.'
    }
    winget install --id Git.Git -e --silent --accept-package-agreements --accept-source-agreements | Out-Null
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
    $g = Get-Command git.exe -ErrorAction SilentlyContinue
    if (-not $g) { Fail 'Git установлен, но не найден. Закройте окно и запустите скрипт ещё раз.' }
    return $g.Source
}

# --------------------------------------------------------- Поиск Jarvis --
function Resolve-Shortcut([string]$lnk) {
    try { return (New-Object -ComObject WScript.Shell).CreateShortcut($lnk).TargetPath } catch { return $null }
}

function Find-Jarvis {
    $found = @()
    $desktop = [Environment]::GetFolderPath('Desktop')
    $docs = [Environment]::GetFolderPath('MyDocuments')
    foreach ($item in Get-ChildItem -Path $desktop, (Join-Path $env:PUBLIC 'Desktop') -Filter '*jarvis*' -ErrorAction SilentlyContinue) {
        if ($item.PSIsContainer) { $found += $item.FullName; continue }
        if ($item.Extension -eq '.lnk') {
            $t = Resolve-Shortcut $item.FullName
            if ($t) {
                # Ярлык на программу (exe/py/bat) — берём её папку
                if (Test-Path $t -PathType Leaf) { $t = Split-Path $t -Parent }
                if (Test-Path $t -PathType Container) { $found += $t }
            }
        }
    }
    foreach ($base in @($env:USERPROFILE, $docs, (Join-Path $env:USERPROFILE 'Projects'),
                        (Join-Path $env:USERPROFILE 'source\repos'), 'C:\', 'D:\')) {
        if (-not (Test-Path $base)) { continue }
        Get-ChildItem -Path $base -Directory -Filter '*jarvis*' -ErrorAction SilentlyContinue |
            ForEach-Object { $found += $_.FullName }
    }
    # Если ярлык указывал на подпапку (dist, bin, src) — поднимаемся к корню проекта
    $found = $found | ForEach-Object {
        $p = $_
        while ((Split-Path $p -Leaf) -match '^(dist|bin|build|src|app|release|x64)$' -and (Split-Path $p -Parent)) {
            $p = Split-Path $p -Parent
        }
        (Resolve-Path $p).Path
    } | Sort-Object -Unique
    return @($found)
}

function Pick-Folder {
    Add-Type -AssemblyName System.Windows.Forms
    $dlg = New-Object System.Windows.Forms.FolderBrowserDialog
    $dlg.Description = 'Выберите папку с кодом Jarvis'
    if ($dlg.ShowDialog() -eq 'OK') { return $dlg.SelectedPath }
    return $null
}

if (-not $Path) {
    $cands = Find-Jarvis
    if ($cands.Count -eq 1) {
        $Path = $cands[0]
        Say "Нашёл Jarvis: $Path"
        $ans = Read-Host 'Это он? [Д/н]'
        if ($ans -match '^(н|n)') { $Path = Pick-Folder }
    } elseif ($cands.Count -gt 1) {
        Say 'Нашёл несколько папок Jarvis:'
        for ($i = 0; $i -lt $cands.Count; $i++) { Write-Host "  [$($i + 1)] $($cands[$i])" }
        $n = Read-Host "Номер нужной (или Enter — выбрать вручную)"
        if ($n -match '^\d+$' -and [int]$n -ge 1 -and [int]$n -le $cands.Count) { $Path = $cands[[int]$n - 1] }
        else { $Path = Pick-Folder }
    } else {
        Warn 'Папку Jarvis не нашёл автоматически — выберите её.'
        $Path = Pick-Folder
    }
}
if (-not $Path -or -not (Test-Path $Path -PathType Container)) { Fail 'Папка с Jarvis не выбрана.' }
$Path = (Resolve-Path $Path).Path

# ------------------------------------------- Копия без секретов и мусора --
$SkipDirs = @('.git', 'node_modules', 'venv', '.venv', 'env', '__pycache__', '.mypy_cache', '.pytest_cache',
              '.idea', '.vs', 'dist', 'build', '.next', '.cache', 'logs', 'site-packages', '.gradle', 'target')
$SkipFiles = @('*.pem', '*.key', '*.pfx', '*.p12', 'id_rsa*', 'id_ed25519*', '*.sqlite', '*.db', '*.log',
               'credentials*.json', 'token*.json', 'service-account*.json', '*.exe', '*.dll', '*.pyc', '*.gguf',
               '*.bin', '*.safetensors', '*.pt', '*.onnx', '*.zip', '*.7z', '*.rar')
$SecretRx = '(sk-(?:proj-|ant-)?[A-Za-z0-9_\-]{20,}|gsk_[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_\-]{30,}|hf_[A-Za-z0-9]{30,}|' +
            'gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|xai-[A-Za-z0-9]{30,}|sk-or-v1-[a-f0-9]{40,}|' +
            '\d{8,10}:[A-Za-z0-9_\-]{35,})'          # последнее — токен Telegram-бота
$TextExt = @('.py', '.js', '.ts', '.tsx', '.jsx', '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf',
             '.txt', '.md', '.bat', '.cmd', '.ps1', '.sh', '.html', '.css', '.cs', '.java', '.go', '.rs', '.xml', '.env.example')

$Work = Join-Path $env:TEMP "jarvis-upload-$(Get-Date -Format yyyyMMddHHmmss)"
New-Item -ItemType Directory -Force -Path $Work | Out-Null
Say "Готовлю копию без секретов: $Work"
$skippedEnv = @(); $redacted = @(); $big = @()
$all = Get-ChildItem -Path $Path -Recurse -File -Force -ErrorAction SilentlyContinue
foreach ($f in $all) {
    $rel = $f.FullName.Substring($Path.Length).TrimStart('\')
    $parts = $rel -split '\\'
    if ($parts.Count -gt 1 -and ($parts[0..($parts.Count - 2)] | Where-Object { $SkipDirs -contains $_ })) { continue }
    if ($f.Name -match '^\.env($|\.)' -and $f.Name -notmatch 'example|sample|template') { $skippedEnv += $rel; continue }
    $skip = $false
    foreach ($m in $SkipFiles) { if ($f.Name -like $m) { $skip = $true; break } }
    if ($skip) { continue }
    if ($f.Length -gt 50MB) { $big += $rel; continue }
    $dst = Join-Path $Work $rel
    New-Item -ItemType Directory -Force -Path (Split-Path $dst -Parent) | Out-Null
    if ($TextExt -contains $f.Extension.ToLower() -and $f.Length -lt 5MB) {
        $text = [IO.File]::ReadAllText($f.FullName)
        if ($text -match $SecretRx) {
            # Переписываем только файлы с ключами; остальные копируются байт в байт (кодировка не меняется)
            [IO.File]::WriteAllText($dst, [regex]::Replace($text, $SecretRx, '<СКРЫТО>'), (New-Object System.Text.UTF8Encoding($false)))
            $redacted += $rel
        } else {
            Copy-Item -LiteralPath $f.FullName -Destination $dst -Force
        }
    } else {
        Copy-Item -LiteralPath $f.FullName -Destination $dst -Force
    }
}
# .gitignore, чтобы секреты не попали и при будущих ручных коммитах
$gi = Join-Path $Work '.gitignore'
$extra = "`n# Добавлено Upload-Jarvis.ps1: секреты и мусор`n.env`n.env.*`n!.env.example`n*.pem`n*.key`nvenv/`n.venv/`nnode_modules/`n__pycache__/`n*.log`n"
if (Test-Path $gi) { Add-Content -Path $gi -Value $extra -Encoding UTF8 } else { Set-Content -Path $gi -Value $extra.TrimStart() -Encoding UTF8 }
$count = (Get-ChildItem -Path $Work -Recurse -File).Count
Say "В копии $count файлов."
if ($skippedEnv) { Warn "Не загружаю файлы с секретами: $($skippedEnv -join ', ')" }
if ($redacted) { Warn "Ключи API заменены на <СКРЫТО> в копии: $($redacted -join ', ')" }
if ($big) { Warn "Пропущены файлы больше 50 МБ: $($big -join ', ')" }

# ------------------------------------------------------- Вход в GitHub --
$git = Get-Git
Say 'Вход в GitHub: если откроется браузер — войдите в аккаунт tagiriskaliev18-hash и разрешите доступ.'
$req = "protocol=https`nhost=github.com`n`n"
$cred = $req | & $git credential fill 2>$null
$token = ($cred | Where-Object { $_ -like 'password=*' }) -replace '^password=', ''
if (-not $token) { Fail 'Не удалось войти в GitHub. Запустите скрипт ещё раз и завершите вход в браузере.' }
$headers = @{ Authorization = "token $token"; 'User-Agent' = 'Upload-Jarvis'; Accept = 'application/vnd.github+json' }
try {
    $me = Invoke-RestMethod -Uri 'https://api.github.com/user' -Headers $headers -ErrorAction Stop
} catch {
    $req | & $git credential reject 2>$null
    Fail 'GitHub не принял вход (устаревший пароль?). Запустите скрипт ещё раз — откроется новый вход.'
}
$req | & $git credential approve 2>$null
if ($me.login -ne $Owner) { Warn "Вы вошли как $($me.login), репозиторий будет $($me.login)/$Repo"; $Owner = $me.login }

# ------------------------------------------------- Репозиторий и отправка --
try {
    Invoke-RestMethod -Uri "https://api.github.com/repos/$Owner/$Repo" -Headers $headers -ErrorAction Stop | Out-Null
    Say "Репозиторий $Owner/$Repo уже есть — отправлю новую версию."
} catch {
    Say "Создаю закрытый репозиторий $Owner/$Repo…"
    $body = @{ name = $Repo; private = $true; description = 'Jarvis — личный ИИ-ассистент' } | ConvertTo-Json
    try {
        Invoke-RestMethod -Method Post -Uri 'https://api.github.com/user/repos' -Headers $headers -Body $body `
            -ContentType 'application/json; charset=utf-8' -ErrorAction Stop | Out-Null
    } catch { Fail "Не удалось создать репозиторий: $($_.Exception.Message)" }
}

Push-Location $Work
& $git init -q -b main
& $git -c user.name="$($me.login)" -c user.email="$($me.id)+$($me.login)@users.noreply.github.com" add -A
& $git -c user.name="$($me.login)" -c user.email="$($me.id)+$($me.login)@users.noreply.github.com" `
    commit -q -m "Jarvis: код с компьютера $env:COMPUTERNAME ($(Get-Date -Format 'yyyy-MM-dd HH:mm'))"
& $git remote add origin "https://github.com/$Owner/$Repo.git"
# Новая версия целиком заменяет прежнюю в ветке main (история прошлых загрузок остаётся в upload-*)
& $git push -q -f origin main
$code = $LASTEXITCODE
& $git push -q origin "main:refs/heads/upload-$(Get-Date -Format yyyyMMdd-HHmmss)"
Pop-Location
if ($code -ne 0) { Fail 'Git не смог отправить код (см. сообщение выше).' }

Write-Host ''
Say "Готово: https://github.com/$Owner/$Repo (закрытый, виден только вам)"
Write-Host 'Напишите Claude: «Jarvis загружен в репозиторий jarvis» — он подключит репозиторий и проверит код.'
Remove-Item -Recurse -Force $Work -ErrorAction SilentlyContinue
