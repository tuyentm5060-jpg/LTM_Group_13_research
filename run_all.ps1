$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$py = "python"
$hostIp = "127.0.0.1"
$port = 9000
$clients = @("1", "10", "50")
$repeats = 3
$warmup = 5
$duration = 20
$payloadSize = 1024

Write-Host "[setup] activating venv if present..." -ForegroundColor Cyan
if (Test-Path "$root\.venv\Scripts\Activate.ps1") {
    . "$root\.venv\Scripts\Activate.ps1"
} elseif (Test-Path "$root\.venv\bin\Activate.ps1") {
    . "$root\.venv\bin\Activate.ps1"
}

Write-Host "[server] starting TCP server..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path (Join-Path $root "experiments\raw-data") | Out-Null
$serverOutLog = Join-Path $root "experiments\raw-data\server.out.log"
$serverErrLog = Join-Path $root "experiments\raw-data\server.err.log"
$serverProc = Start-Process -FilePath $py -ArgumentList "-m", "src.server.run_server", "--host", $hostIp, "--port", $port -WorkingDirectory $root -RedirectStandardOutput $serverOutLog -RedirectStandardError $serverErrLog -PassThru

$waited = 0
while ($waited -lt 20) {
    try {
        $socket = [System.Net.Sockets.TcpClient]::new()
        $socket.Connect($hostIp, $port)
        $socket.Close()
        Write-Host "[server] ready on ${hostIp}:$port" -ForegroundColor Green
        break
    }
    catch {
        Start-Sleep -Seconds 1
        $waited++
    }
}

if ($waited -ge 20) {
    Write-Error "Server không bắt đầu được trong 20 giây."
    Stop-Process -Id $serverProc.Id -Force
    exit 1
}

try {
    foreach ($clientCount in $clients) {
        for ($i = 1; $i -le $repeats; $i++) {
            $runId = "c${clientCount}_r${i}"
            Write-Host "[run] $runId | clients=$clientCount" -ForegroundColor Magenta
            & $py -m src.load_generator.run_load `
                --host $hostIp `
                --port $port `
                --clients $clientCount `
                --warmup $warmup `
                --duration $duration `
                --payload-size $payloadSize `
                --server-pid $serverProc.Id `
                --run-id $runId `
                --out-dir experiments/raw-data
            if ($LASTEXITCODE -ne 0) {
                throw "Load test failed for $runId"
            }
        }
    }

    Write-Host "[analysis] generating charts..." -ForegroundColor Yellow
    & $py experiments/analysis/analyze.py --in-dir experiments/raw-data --out-dir experiments/figures
    if ($LASTEXITCODE -ne 0) {
        throw "Analyze step failed"
    }

    Write-Host "[done] benchmark complete. Check experiments/raw-data and experiments/figures" -ForegroundColor Green
}
finally {
    Write-Host "[server] stopping server..." -ForegroundColor Yellow
    Stop-Process -Id $serverProc.Id -Force -ErrorAction SilentlyContinue
}
