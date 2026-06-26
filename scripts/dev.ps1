# 一键启动/停止/重启/查看 高考志愿专业推荐 前后端服务（Windows）
#
# 用法:
#   .\scripts\dev.ps1 start     # 后台启动后端(uvicorn:8000) + 前端(vite:5173)
#   .\scripts\dev.ps1 stop      # 停止前后端
#   .\scripts\dev.ps1 restart   # 重启（= stop 再 start）
#   .\scripts\dev.ps1 status    # 查看运行状态（不传参数默认也是 status）
#
# 实现说明:
#   - 用 Start-Process 拉起隐藏窗口的后台 cmd 进程，stdout/stderr 合并写入
#     logs\backend.log / logs\frontend.log；进程 PID 记入 logs\*.pid。
#     相比 schtasks 不依赖系统区域/日期格式，更稳定。
#   - stop 优先按 PID 文件停止；若 PID 已失效则按端口兜底清理残留进程。
#   - 后端: python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000
#   - 前端: npm run dev (vite dev server :5173)，dev 时 vite proxy 把 /api 转发到 8000。
#
# 直接双击可用配套的 dev.bat（默认执行 start）。

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('start', 'stop', 'restart', 'status')]
    [string]$Action = 'status'
)

$ErrorActionPreference = 'Stop'

# ---------- 路径 ----------
$ScriptRoot  = Split-Path -Parent $MyInvocation.MyCommand.Path   # scripts/
$ProjectRoot = Split-Path -Parent $ScriptRoot                     # 项目根
$LogDir      = Join-Path $ProjectRoot 'logs'
$WebDir      = Join-Path $ProjectRoot 'web-ui'
$BackendLog  = Join-Path $LogDir 'backend.log'
$FrontendLog = Join-Path $LogDir 'frontend.log'
$BackendPid  = Join-Path $LogDir 'backend.pid'
$FrontendPid = Join-Path $LogDir 'frontend.pid'

# ---------- 输出工具 ----------
function Write-Section($msg) { Write-Host "`n[$msg]" -ForegroundColor Cyan }
function Write-Ok($msg)      { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Warn($msg)    { Write-Host "  [!]  $msg" -ForegroundColor Yellow }
function Write-Err($msg)     { Write-Host "  [X]  $msg" -ForegroundColor Red }

# ---------- 进程工具 ----------
# 判断某 PID 是否仍存活且是可访问进程。
function Test-PidAlive($procId) {
    if (-not $procId) { return $false }
    try { $null = Get-Process -Id $procId -ErrorAction Stop; return $true }
    catch { return $false }
}

# 安全停止一个 PID（存在且存活才 kill）。
function Stop-Pid($procId, $label) {
    if (Test-PidAlive $procId) {
        taskkill /PID $procId /T /F *> $null   # /T 连带子进程（npm->node, cmd->python）
        Write-Ok "已停止 $label (PID $procId)"
    } else {
        Write-Warn "$label 未在运行 (PID $procId 已退出)"
    }
}

# 按监听端口兜底清理残留进程：netstat 找 LISTENING 的 PID -> taskkill。
function Stop-PortResidue($port, $label) {
    $conns = netstat -ano | Select-String ":$port\s.*LISTENING"
    $pids = $conns | ForEach-Object {
        if ($_ -match '\s+(\d+)\s*$') { $matches[1] }
    } | Sort-Object -Unique
    foreach ($procId in $pids) {
        if ($procId -and $procId -ne '0') {
            taskkill /PID $procId /T /F *> $null
            Write-Warn "按端口 $port 清理残留进程 PID $procId ($label)"
        }
    }
}

# 后台拉起一条命令：隐藏窗口的 cmd /c，stdout+stderr 合并写日志，返回 PID。
function Start-BgProcess($workDir, $logFile, $cmd, $cmdArgs) {
    New-Item -ItemType Directory -Force -Path $LogDir *> $null
    # 清空旧日志（每次启动只保留本次输出，便于排错）
    if (Test-Path $logFile) { Set-Content -Path $logFile -Value $null }
    # cmd /c "cd /d <workdir> && <cmd> <args> > <log> 2>&1"  以隐藏窗口运行。
    $cmdLine = "cd /d `"$workDir`" && $cmd $cmdArgs > `"$logFile`" 2>&1"
    $p = Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', $cmdLine `
        -WindowStyle Hidden -PassThru
    return $p.Id
}

# ---------- start ----------
function Invoke-Start {
    Write-Section '启动前后端服务'

    if (-not (Test-Path (Join-Path $WebDir 'node_modules'))) {
        Write-Warn 'web-ui\node_modules 不存在，先执行 npm install（首次较慢）...'
        Push-Location $WebDir
        try { npm install } finally { Pop-Location }
    }

    # 后端：python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000
    $bePid = Start-BgProcess $ProjectRoot $BackendLog 'python' `
        '-m uvicorn app.api.main:app --host 127.0.0.1 --port 8000'
    Set-Content -Path $BackendPid -Value $bePid
    Write-Ok "后端已启动 (uvicorn :8000, PID $bePid) -> $BackendLog"

    # 前端：npm run dev (vite :5173)
    $fePid = Start-BgProcess $WebDir $FrontendLog 'npm.cmd' 'run dev'
    Set-Content -Path $FrontendPid -Value $fePid
    Write-Ok "前端已启动 (vite :5173, PID $fePid) -> $FrontendLog"

    # 等待后端就绪（最多 30s）
    Write-Host '  等待后端就绪...' -NoNewline
    $ready = $false
    foreach ($i in 1..30) {
        Start-Sleep -Seconds 1
        try {
            $resp = Invoke-WebRequest -UseBasicParsing `
                -Uri 'http://127.0.0.1:8000/api/v1/health' -TimeoutSec 2
            if ($resp.StatusCode -eq 200) { $ready = $true; break }
        } catch { }
        Write-Host '.' -NoNewline
    }
    Write-Host ''
    if ($ready) { Write-Ok '后端 /health 返回 200，已就绪' }
    else { Write-Warn '后端 30s 内未响应（可能仍在加载种子数据，查看日志确认）' }

    Write-Section '访问地址'
    Write-Host '  前端: http://localhost:5173/'
    Write-Host '  后端: http://127.0.0.1:8000/docs'
    Write-Host '  日志: .\logs\backend.log | .\logs\frontend.log'
    Write-Host '  状态: .\scripts\dev.ps1 status'
    Write-Host '  停止: .\scripts\dev.ps1 stop'
    Write-Host ''
}

# ---------- stop ----------
function Invoke-Stop {
    Write-Section '停止前后端服务'
    # 先按 PID 文件停（精准）；再按端口兜底（PID 文件丢失或 cmd 包装进程已退出时）
    foreach ($pair in @(
        @($FrontendPid, 5173, '前端'),
        @($BackendPid,  8000, '后端')
    )) {
        $pidFile, $port, $label = $pair
        if (Test-Path $pidFile) {
            $procId = (Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
            if ($procId) { Stop-Pid $procId $label }
            Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
        } else {
            Write-Warn "$label 无 PID 文件（按端口兜底）"
        }
        Stop-PortResidue $port $label
    }
    Write-Host ''
}

# ---------- status ----------
function Invoke-Status {
    Write-Section '服务状态'

    # 后端：探测 health
    $beStatus = '已停止'; $beExtra = ''
    try {
        $resp = Invoke-WebRequest -UseBasicParsing `
            -Uri 'http://127.0.0.1:8000/api/v1/health' -TimeoutSec 2
        if ($resp.StatusCode -eq 200) {
            $body = $resp.Content | ConvertFrom-Json
            $beStatus = '运行中'
            $beExtra = "seed_loaded=$($body.seed_loaded)"
        }
    } catch { }

    # 前端：探测 vite dev server 根路径
    $feStatus = '已停止'
    try {
        $resp = Invoke-WebRequest -UseBasicParsing -Uri 'http://localhost:5173/' -TimeoutSec 2
        if ($resp.StatusCode -eq 200) { $feStatus = '运行中' }
    } catch { }

    $fmt = '  {0,-6} {1,-7} {2}'
    Write-Host ($fmt -f '服务', '状态', '地址 / 备注')
    Write-Host ($fmt -f '----', '----', '------------')
    Write-Host ($fmt -f '后端', $beStatus, "http://127.0.0.1:8000/docs  $beExtra") `
        -ForegroundColor $(if ($beStatus -eq '运行中') {'Green'} else {'Gray'})
    Write-Host ($fmt -f '前端', $feStatus, 'http://localhost:5173/') `
        -ForegroundColor $(if ($feStatus -eq '运行中') {'Green'} else {'Gray'})

    # PID 文件信息
    Write-Host ''
    Write-Host '  PID 文件:' -ForegroundColor DarkGray
    foreach ($pair in @(@($BackendPid,'后端'), @($FrontendPid,'前端'))) {
        $pidFile, $label = $pair
        if (Test-Path $pidFile) {
            $procId = (Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
            $alive = if (Test-PidAlive $procId) { '存活' } else { '已退出' }
            Write-Host "    $label PID=$procId ($alive)" -ForegroundColor DarkGray
        } else {
            Write-Host "    $label 无 PID 文件" -ForegroundColor DarkGray
        }
    }
    Write-Host ''
}

# ---------- restart ----------
function Invoke-Restart {
    Invoke-Stop
    Start-Sleep -Seconds 1
    Invoke-Start
}

# ---------- 分发 ----------
switch ($Action) {
    'start'   { Invoke-Start }
    'stop'    { Invoke-Stop }
    'restart' { Invoke-Restart }
    'status'  { Invoke-Status }
}
