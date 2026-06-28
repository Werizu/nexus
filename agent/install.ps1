# NEXUS Agent Quick Installer
# Usage (elevated PowerShell):  irm https://werizu.github.io/nexus/install.ps1 | iex

$ErrorActionPreference = "Stop"

$InstallDir = "$env:ProgramFiles\NEXUS Agent"

Write-Host ""
Write-Host "  NEXUS Agent Installer" -ForegroundColor Cyan
Write-Host ""

# Check admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "  [!] Bitte als Administrator ausfuehren!" -ForegroundColor Red
    Write-Host "  Rechtsklick auf PowerShell -> Als Administrator ausfuehren" -ForegroundColor Yellow
    exit 1
}

# Check Python
Write-Host "  [1/6] Python pruefen..." -ForegroundColor Yellow
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "  [!] Python nicht gefunden. Bitte installieren: https://python.org" -ForegroundColor Red
    Write-Host "      (oder: winget install -e --id Python.Python.3.12)" -ForegroundColor Yellow
    exit 1
}
Write-Host "  OK: $(python --version 2>&1)" -ForegroundColor Green

# Prompt: Brain IP + NEXUS-Login
Write-Host "  [2/6] Anmeldung..." -ForegroundColor Yellow
$defaultBrain = if ($env:NEXUS_BRAIN) { $env:NEXUS_BRAIN } else { "100.122.236.58" }
$BrainIP = Read-Host "  Brain IP (Enter = $defaultBrain)"
if ([string]::IsNullOrWhiteSpace($BrainIP)) { $BrainIP = $defaultBrain }
$NexusUser = Read-Host "  NEXUS Benutzername"
$NexusPassSecure = Read-Host "  NEXUS Passwort" -AsSecureString
$NexusPass = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($NexusPassSecure))

# Login + Geraete-Registrierung -> eindeutige MQTT-Credentials vom Brain
try {
    $login = Invoke-RestMethod -Uri "http://${BrainIP}:8000/api/v1/auth/login" -Method Post `
        -Body (@{ username = $NexusUser; password = $NexusPass } | ConvertTo-Json) `
        -ContentType "application/json"
    $token = $login.token
} catch {
    Write-Host "  [!] Login fehlgeschlagen — Benutzername/Passwort/Brain-IP pruefen." -ForegroundColor Red
    exit 1
}
try {
    $reg = Invoke-RestMethod -Uri "http://${BrainIP}:8000/api/v1/agent/register" -Method Post `
        -Headers @{ Authorization = "Bearer $token" } `
        -Body (@{ hostname = $env:COMPUTERNAME; os = "windows"; name = $env:COMPUTERNAME } | ConvertTo-Json) `
        -ContentType "application/json"
} catch {
    Write-Host "  [!] Registrierung am Brain fehlgeschlagen." -ForegroundColor Red
    exit 1
}
$NexusPass = $null  # NEXUS-Passwort nicht weiter vorhalten
Write-Host "  OK: Registriert als '$($reg.device_id)' (Owner: $NexusUser)" -ForegroundColor Green

# Create directory with full permissions
Write-Host "  [3/6] Verzeichnis erstellen..." -ForegroundColor Yellow
New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
icacls $InstallDir /grant "Benutzer:F" /T /Q 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    icacls $InstallDir /grant "Users:F" /T /Q 2>&1 | Out-Null
}
Write-Host "  OK: $InstallDir" -ForegroundColor Green

# Download files
Write-Host "  [4/6] Dateien herunterladen..." -ForegroundColor Yellow
$base = "https://raw.githubusercontent.com/Werizu/nexus/main/agent"
@("nexus_agent.py", "nexus_service.py", "requirements.txt") | ForEach-Object {
    Invoke-WebRequest -Uri "$base/$_" -OutFile "$InstallDir\$_" -UseBasicParsing
    Write-Host "  OK: $_" -ForegroundColor Green
}

# Write config (mit eindeutigen MQTT-Creds vom Brain — kein NEXUS-Passwort)
$port = if ($reg.port) { $reg.port } else { 1883 }
@"
mqtt:
  broker: "$BrainIP"
  port: $port
  client_id: "$($reg.username)"
agent:
  device_id: "$($reg.device_id)"
  name: "$env:COMPUTERNAME"
  report_interval: 10
auth:
  username: "$($reg.username)"
  password: "$($reg.password)"
alerts:
  cpu: 90
  ram: 90
  disk: 90
  gpu_temp: 85
  gpu_load: 95
  cooldown: 300
"@ | Out-File "$InstallDir\config.yaml" -Encoding UTF8

# Install dependencies
Write-Host "  [5/6] Dependencies installieren..." -ForegroundColor Yellow
python -m pip install --quiet --upgrade pip 2>&1 | Out-Null
python -m pip install --quiet -r "$InstallDir\requirements.txt" 2>&1 | Out-Null
Write-Host "  OK: Alle Dependencies installiert" -ForegroundColor Green

# Autostart via Scheduled Task (robust — kein pywin32-Dienst)
Write-Host "  [6/6] Autostart einrichten..." -ForegroundColor Yellow
$taskName = "NEXUS Agent"
# Altlasten entfernen (Task + evtl. kaputter Dienst aelterer Versionen).
# In cmd kapseln (>nul 2>&1), damit stderr NICHT als PowerShell-Fehler abbricht.
cmd /c "schtasks /End /TN ""$taskName"" >nul 2>&1"
cmd /c "schtasks /Delete /TN ""$taskName"" /F >nul 2>&1"
cmd /c "sc stop NexusAgent >nul 2>&1"
cmd /c "sc delete NexusAgent >nul 2>&1"

# pythonw -> laeuft ohne Konsolenfenster
$pythonw = (Get-Command python).Source -replace 'python\.exe$', 'pythonw.exe'
if (-not (Test-Path $pythonw)) { $pythonw = (Get-Command python).Source }
$agentPath = "$InstallDir\nexus_agent.py"

$action    = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$agentPath`""
$trigger   = New-ScheduledTaskTrigger -AtLogOn
$settings  = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero)
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
Start-ScheduledTask -TaskName $taskName
Write-Host "  OK: Autostart-Task '$taskName' angelegt + gestartet" -ForegroundColor Green

# Verify — Log auf erfolgreiche MQTT-Verbindung pruefen
Start-Sleep 6
$log = "$InstallDir\nexus-agent.log"
$connected = $false
if (Test-Path $log) { if ((Get-Content $log -Tail 12) -match "Connected to MQTT") { $connected = $true } }

Write-Host ""
if ($connected) {
    Write-Host "  OK: Verbunden! Dein PC erscheint jetzt im NEXUS-Dashboard." -ForegroundColor Green
} else {
    Write-Host "  [!] Noch kein 'Connected' im Log — laeuft Tailscale? Letzte Zeilen:" -ForegroundColor Yellow
    if (Test-Path $log) { Get-Content $log -Tail 8 | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray } }
}
Write-Host ""
Write-Host "  Status:       Get-ScheduledTask -TaskName 'NEXUS Agent'" -ForegroundColor Gray
Write-Host "  Logs:         Get-Content `"$InstallDir\nexus-agent.log`" -Tail 20" -ForegroundColor Gray
Write-Host "  Deinstall.:   schtasks /Delete /TN 'NEXUS Agent' /F; Remove-Item -Recurse -Force `"$InstallDir`"" -ForegroundColor Gray
Write-Host ""
