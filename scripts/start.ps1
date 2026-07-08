param(
    [int]$Port = 8000,
    [switch]$NoReload
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$RunDirectory = Join-Path $ProjectRoot ".run"
$PidFile = Join-Path $RunDirectory "kitchen-agent.pid"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Virtual environment not found: $Python"
}

if (Test-Path -LiteralPath $PidFile) {
    $existingPid = [int](Get-Content -LiteralPath $PidFile -Raw)
    if (Get-Process -Id $existingPid -ErrorAction SilentlyContinue) {
        throw "Kitchen Agent is already running (PID $existingPid)."
    }
    Remove-Item -LiteralPath $PidFile -Force
}

$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    throw "Port $Port is already in use by PID $($listener.OwningProcess)."
}

New-Item -ItemType Directory -Path $RunDirectory -Force | Out-Null
$arguments = @(
    "-m", "uvicorn", "app.web:app",
    "--host", "127.0.0.1",
    "--port", $Port.ToString()
)
if (-not $NoReload) {
    $arguments += "--reload"
}

$process = Start-Process `
    -FilePath $Python `
    -ArgumentList $arguments `
    -WorkingDirectory $ProjectRoot `
    -WindowStyle Hidden `
    -PassThru

Set-Content -LiteralPath $PidFile -Value $process.Id -Encoding ascii

for ($attempt = 0; $attempt -lt 30; $attempt++) {
    Start-Sleep -Milliseconds 250
    if ($process.HasExited) {
        Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
        throw "Kitchen Agent exited during startup with code $($process.ExitCode)."
    }
    try {
        $response = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/status" -TimeoutSec 1
        if ($null -ne $response.ready) {
            Write-Output "Kitchen Agent started (PID $($process.Id))."
            Write-Output "Open http://127.0.0.1:$Port"
            exit 0
        }
    }
    catch {
        # Continue polling until the startup deadline.
    }
}

Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
throw "Kitchen Agent did not become ready on port $Port."
