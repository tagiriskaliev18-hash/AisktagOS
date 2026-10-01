param(
    [ValidateSet("setup", "start", "stop", "status", "reconfig")]
    [string]$Action = "status",
    [string]$VmName = "AIsktagOS",
    [string]$IsoPath = "$PSScriptRoot\..\out\aisktagos-1.0-amd64.iso",
    [int]$MemoryMb = 4096,
    [int]$CpuCount = 2,
    [int]$DiskSizeMb = 40960
)

$VBoxManage = "C:\Program Files\Oracle\VirtualBox\VBoxManage.exe"
if (-not (Test-Path $VBoxManage)) {
    Write-Error "VirtualBox not found at: $VBoxManage"
    exit 1
}

# Если в Windows работает Hyper-V, VirtualBox запускает ВМ через него (зелёная черепаха
# в строке состояния) в 10–20 раз медленнее: загрузка выглядит зависшей на строках systemd.
$HypervisorOn = $false
try { $HypervisorOn = (Get-CimInstance Win32_ComputerSystem).HypervisorPresent } catch {}
if ($HypervisorOn -and $Action -in @("setup", "start")) {
    Write-Warning "Hyper-V is active: VirtualBox will run this VM very slowly (green turtle icon). Boot may take 10-15 minutes."
    Write-Warning "To fix (as Administrator): bcdedit /set hypervisorlaunchtype off; turn off Core isolation > Memory integrity; reboot Windows."
}

$ResolvedIso = (Resolve-Path $IsoPath -ErrorAction SilentlyContinue).Path
$VmFolder = "$HOME\VirtualBox VMs\$VmName"
$VdiPath = "$VmFolder\$VmName.vdi"

function Invoke-VBox {
    param([string[]]$ArgsList)
    & $VBoxManage @ArgsList
}

switch ($Action) {
    "setup" {
        Write-Host "==> Setup VM: $VmName" -ForegroundColor Cyan
        $existing = & $VBoxManage list vms
        if ($existing -match "`"$VmName`"") {
            Write-Warning "VM $VmName is already registered. Applying reconfig..."
        } else {
            Invoke-VBox @("createvm", "--name", $VmName, "--ostype", "Ubuntu24_LTS_64", "--register")
            Invoke-VBox @("storagectl", $VmName, "--name", "SATA", "--add", "sata", "--controller", "IntelAhci", "--bootable", "on")
            
            if (-not (Test-Path $VdiPath)) {
                New-Item -ItemType Directory -Force -Path $VmFolder | Out-Null
                Invoke-VBox @("createmedium", "disk", "--filename", $VdiPath, "--size", $DiskSizeMb, "--format", "VDI", "--variant", "Standard")
            }
            Invoke-VBox @("storageattach", $VmName, "--storagectl", "SATA", "--port", "0", "--device", "0", "--type", "hdd", "--medium", $VdiPath)
            
            if ($ResolvedIso -and (Test-Path $ResolvedIso)) {
                Invoke-VBox @("storageattach", $VmName, "--storagectl", "SATA", "--port", "1", "--device", "0", "--type", "dvddrive", "--medium", $ResolvedIso)
            }
        }

        # 3D-ускорение выключено: с VMSVGA + 3D VirtualBox часто показывает только чёрный
        # экран после запуска рабочего стола KDE. Без него рабочий стол рисуется программно.
        Invoke-VBox @("modifyvm", $VmName,
            "--memory", $MemoryMb,
            "--cpus", $CpuCount,
            "--vram", "128",
            "--graphicscontroller", "vmsvga",
            "--accelerate-3d", "off",
            "--mouse", "usbtablet",
            "--clipboard-mode", "bidirectional",
            "--drag-and-drop", "bidirectional",
            "--firmware", "efi",
            "--audio-enabled", "on",
            "--audio-out", "on",
            "--boot1", "dvd",
            "--boot2", "disk",
            "--boot3", "none",
            "--boot4", "none"
        )
        Write-Host "==> Setup completed successfully!" -ForegroundColor Green
    }

    "reconfig" {
        Write-Host "==> Updating integration settings for $VmName" -ForegroundColor Cyan
        Invoke-VBox @("modifyvm", $VmName,
            "--mouse", "usbtablet",
            "--clipboard-mode", "bidirectional",
            "--drag-and-drop", "bidirectional",
            "--graphicscontroller", "vmsvga",
            "--accelerate-3d", "off",
            "--audio-enabled", "on",
            "--audio-out", "on"
        )
        Write-Host "==> Settings updated: mouse = usbtablet, clipboard = bidirectional" -ForegroundColor Green
    }

    "start" {
        Write-Host "==> Starting VM: $VmName" -ForegroundColor Cyan
        Invoke-VBox @("startvm", $VmName, "--type", "gui")
    }

    "stop" {
        Write-Host "==> Stopping VM: $VmName" -ForegroundColor Cyan
        Invoke-VBox @("controlvm", $VmName, "acpipowerbutton")
    }

    "status" {
        Write-Host "==> VM info for ${VmName}:" -ForegroundColor Cyan
        & $VBoxManage showvminfo $VmName --machinereadable | Select-String "name=|memory=|cpus=|pointing=|clipboard=|draganddrop=|graphicscontroller=|vram=|VMState="
    }
}
