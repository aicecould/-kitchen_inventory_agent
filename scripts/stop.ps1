param(
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$PidFile = Join-Path $ProjectRoot ".run\kitchen-agent.pid"
$rootIds = [System.Collections.Generic.HashSet[int]]::new()

if (Test-Path -LiteralPath $PidFile) {
    $savedPid = [int](Get-Content -LiteralPath $PidFile -Raw)
    [void]$rootIds.Add($savedPid)
}

$projectProcesses = Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -match "uvicorn.*app\.web:app"
}
foreach ($process in $projectProcesses) {
    [void]$rootIds.Add([int]$process.ProcessId)
}

$listeners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($listeners -and $rootIds.Count -eq 0) {
    try {
        $openApi = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/openapi.json" -TimeoutSec 2
        if ($openApi.info.title -eq "Kitchen Inventory Agent") {
            foreach ($listener in $listeners) {
                [void]$rootIds.Add([int]$listener.OwningProcess)
            }
        }
    }
    catch {
        throw "Port $Port is in use, but it could not be verified as Kitchen Agent."
    }
}

if ($rootIds.Count -eq 0) {
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
    Write-Output "Kitchen Agent is not running."
    exit 0
}

$snapshot = @(Get-CimInstance Win32_Process)
$allIds = [System.Collections.Generic.HashSet[int]]::new()
foreach ($rootId in $rootIds) {
    [void]$allIds.Add($rootId)
}

do {
    $added = $false
    foreach ($process in $snapshot) {
        if ($allIds.Contains([int]$process.ParentProcessId) -and
            $allIds.Add([int]$process.ProcessId)) {
            $added = $true
        }
    }
} while ($added)

$processesToStop = $snapshot |
    Where-Object { $allIds.Contains([int]$_.ProcessId) } |
    Sort-Object ProcessId -Descending

foreach ($process in $processesToStop) {
    Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
}
foreach ($rootId in $rootIds) {
    Stop-Process -Id $rootId -Force -ErrorAction SilentlyContinue
}

for ($attempt = 0; $attempt -lt 20; $attempt++) {
    Start-Sleep -Milliseconds 150
    if (-not (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)) {
        break
    }
}

Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
    throw "Kitchen Agent processes were stopped, but port $Port is still listening."
}
Write-Output "Kitchen Agent stopped."
