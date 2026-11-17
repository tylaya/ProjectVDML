$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $ProjectRoot "backend"
$FrontendDir = Join-Path $ProjectRoot "frontend"
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$BackendPort = 8000
$FrontendPort = 5173

function Ensure-FileFromExample {
    param(
        [string]$Source,
        [string]$Destination
    )

    if (-not (Test-Path $Destination)) {
        if (-not (Test-Path $Source)) {
            Write-Host "File contoh tidak ditemukan: $Source" -ForegroundColor Red
            return
        }
        Copy-Item -Path $Source -Destination $Destination
        Write-Host "Membuat file konfigurasi: $Destination" -ForegroundColor Yellow
    }
}

function Test-PortIsFree {
    param(
        [int]$Port
    )

    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
    try {
        $listener.Start()
        return $true
    }
    catch {
        return $false
    }
    finally {
        $listener.Stop()
    }
}

function Ensure-PythonEnv {
    if (-not (Test-Path $VenvPython)) {
        Write-Host "Membuat virtual environment Python di $ProjectRoot\.venv ..." -ForegroundColor Yellow
        py -3.12 -m venv "$ProjectRoot\.venv"
        if (-not (Test-Path $VenvPython)) {
            Write-Error "Virtual environment gagal dibuat. Pastikan Python 3.12 tersedia di PATH."
            exit 1
        }
    }

    & $VenvPython -m pip install --upgrade pip | Out-Null
    & $VenvPython -m pip install -r "$BackendDir\requirements.txt" | Out-Null
}

function Ensure-FrontendDeps {
    if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
        Write-Host "Menginstall dependency frontend ..." -ForegroundColor Yellow
        Push-Location $FrontendDir
        npm install
        Pop-Location
    }
}

function Start-WindowedCommand {
    param(
        [string]$Title,
        [string]$WorkingDirectory,
        [string]$Command
    )

    Start-Process powershell `
        -ArgumentList @("-NoExit", "-Command", $Command) `
        -WorkingDirectory $WorkingDirectory `
        -WindowStyle Normal

    Write-Host "Menjalankan $Title di jendela terpisah ..." -ForegroundColor Green
}

function Open-BrowserIfReady {
    param(
        [string]$Url
    )

    Start-Sleep -Seconds 5
    try {
        Start-Process $Url
    }
    catch {
        Write-Host "Browser tidak terbuka otomatis. Buka manual: $Url" -ForegroundColor Yellow
    }
}

Write-Host "=== SIGAP-VD admin launcher ===" -ForegroundColor Cyan
Write-Host "Project root: $ProjectRoot" -ForegroundColor Cyan

if (-not (Test-PortIsFree -Port $BackendPort)) {
    Write-Host "Port $BackendPort sudah dipakai. Tutup proses yang memakai port tersebut terlebih dahulu." -ForegroundColor Red
    exit 1
}

if (-not (Test-PortIsFree -Port $FrontendPort)) {
    Write-Host "Port $FrontendPort sudah dipakai. Tutup proses yang memakai port tersebut terlebih dahulu." -ForegroundColor Red
    exit 1
}

Ensure-FileFromExample -Source (Join-Path $BackendDir ".env.example") -Destination (Join-Path $BackendDir ".env")
Ensure-FileFromExample -Source (Join-Path $FrontendDir ".env.example") -Destination (Join-Path $FrontendDir ".env.local")

Ensure-PythonEnv
Ensure-FrontendDeps

$BackendCommand = @"
Set-Location '$ProjectRoot'
. '.\.venv\Scripts\Activate.ps1'
Set-Location '$BackendDir'
$env:ADMIN_EMAILS = 'your.admin@unklab.ac.id'
uvicorn main:app --reload --host 0.0.0.0 --port $BackendPort
"@

$FrontendCommand = @"
Set-Location '$FrontendDir'
$env:VITE_API_URL = 'http://localhost:$BackendPort'
$env:VITE_GOOGLE_CLIENT_ID = 'replace-with-google-oauth-web-client-id'
npm run dev -- --host 0.0.0.0 --port $FrontendPort
"@

Start-WindowedCommand -Title "Backend API (Admin)" -WorkingDirectory $ProjectRoot -Command $BackendCommand
Start-Sleep -Seconds 2
Start-WindowedCommand -Title "Frontend Vite (Admin)" -WorkingDirectory $ProjectRoot -Command $FrontendCommand

Write-Host "" 
Write-Host "Mode: admin / staff" -ForegroundColor Cyan
Write-Host "Backend URL: http://localhost:$BackendPort" -ForegroundColor Cyan
Write-Host "Frontend URL: http://localhost:$FrontendPort" -ForegroundColor Cyan
Write-Host "API docs: http://localhost:$BackendPort/docs" -ForegroundColor Cyan
Write-Host "" 
Write-Host "Pastikan backend/.env dan frontend/.env.local sudah berisi email admin dan Google Client ID yang valid." -ForegroundColor Yellow
Write-Host "Launcher admin selesai. Kedua terminal akan tetap terbuka sampai ditutup manual." -ForegroundColor Green

Open-BrowserIfReady -Url "http://localhost:$FrontendPort"
