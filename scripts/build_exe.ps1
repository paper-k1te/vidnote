# 构建 Windows 单文件可执行程序（核心版）。
#
# 用法：
#   pwsh scripts/build_exe.ps1
#
# 产物：dist-exe\vidnote.exe
#
# 说明：核心版包含抓取、搜索、笔记生成；不含本地转写（faster-whisper）和
# 抽帧（PyAV/Pillow），因为它们依赖重型原生库，会让体积膨胀数倍。

$ErrorActionPreference = "Stop"

Set-Location (Split-Path -Parent $PSScriptRoot)

$python = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Error "找不到虚拟环境：$python。先运行 python -m venv .venv 并安装依赖。"
}

& $python -m pip install --quiet --upgrade pyinstaller
& $python -m PyInstaller vidnote.spec --noconfirm --distpath dist-exe --workpath build-exe

$exe = "dist-exe\vidnote.exe"
if (-not (Test-Path $exe)) {
    Write-Error "构建失败：$exe 不存在"
}

$size = [math]::Round((Get-Item $exe).Length / 1MB, 1)
Write-Host "已生成 $exe（$size MB）"

# 构建后的基本自检：能打印版本号就算通过。
$version = & $exe version
Write-Host "自检通过：$version"
