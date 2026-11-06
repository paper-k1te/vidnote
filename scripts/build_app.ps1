# 构建桌面应用（原生窗口 + WebView2 外壳）
#
# 唯一的桌面构建：Vosk 引擎和中文模型内置，第一次转写不用下载；
# whisper 的依赖仍然按需下载。
#
# 用法：
#   powershell -File scripts/build_app.ps1
#
# 产物：
#   dist-app\vidnote-app.exe
#     单文件：内置后端、WebView2 库和窗口外壳；首次运行释放到
#     %LOCALAPPDATA%\vidnote\runtime，用户目录里只保留一个 exe。
#
# 前置条件：
#   1. 已安装 .NET Framework 4.8（Windows 10/11 自带）
#   2. 已安装 WebView2 运行时（Windows 11 自带；Win10 可能需要装一次）
#   3. 首次构建需要能访问 nuget.org 下载 WebView2 SDK

param(
    # 已废弃：完整版目标已合并进唯一的桌面构建，保留参数只为旧命令不报错。
    [switch]$Full
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$python = ".\.venv\Scripts\python.exe"
$csc = "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe"

$spec = "vidnote-app.spec"
$exeDir = "dist-exe"
$workDir = "build-exe"
$appDir = "dist-app"
$serverName = "vidnote-server.exe"

# 应用版本号：写进 exe 的版本信息，跟 pyproject.toml 保持一致。
$pyproject = Get-Content pyproject.toml -Raw
$appVersion = [regex]::Match($pyproject, 'version = "([^"]+)"').Groups[1].Value
if (-not $appVersion) { throw "无法从 pyproject.toml 读取版本号" }
$numeric = ($appVersion -replace '[^0-9.].*$', '')
$pieces = @($numeric.Split('.') | Where-Object { $_ -ne '' })
$four = (@($pieces + @('0', '0', '0', '0'))[0..3]) -join '.'
$icon = "assets\vidnote.ico"
if (-not (Test-Path $icon)) { throw "缺少图标：$icon" }

# Vosk 引擎和模型都打进 exe；本地有缓存就复制，没有就下载。
$modelFolder = "vosk-model-small-cn-0.22"
$modelDir = "assets\$modelFolder"
if (-not (Test-Path "$modelDir\am")) {
    $cached = Join-Path $env:LOCALAPPDATA "vidnote\vosk\$modelFolder"
    New-Item -ItemType Directory -Force -Path "assets" | Out-Null
    if (Test-Path "$cached\am") {
        Write-Host "==> 复制 Vosk 模型"
        Copy-Item $cached $modelDir -Recurse -Force
    } else {
        Write-Host "==> 下载 Vosk 模型"
        $zip = "assets\$modelFolder.zip"
        Invoke-WebRequest "https://alphacephei.com/vosk/models/$modelFolder.zip" -OutFile $zip -UseBasicParsing
        Expand-Archive $zip -DestinationPath "assets" -Force
        Remove-Item $zip -Force
    }
}

# 1. 编译 Python 后端
Write-Host "==> 打包后端（$spec）"
& $python -m PyInstaller $spec --noconfirm --distpath $exeDir --workpath $workDir --log-level ERROR

# 2. 准备 WebView2 SDK
$sdk = ".tools\webview2\pkg"
if (-not (Test-Path "$sdk\lib\net462\Microsoft.Web.WebView2.Core.dll")) {
    Write-Host "==> 下载 WebView2 SDK"
    New-Item -ItemType Directory -Force -Path ".tools\webview2" | Out-Null
    $index = Invoke-RestMethod "https://api.nuget.org/v3-flatcontainer/microsoft.web.webview2/index.json"
    $version = ($index.versions | Where-Object { $_ -notmatch '-' } | Select-Object -Last 1)
    $nupkg = ".tools\webview2\webview2.nupkg"
    Invoke-WebRequest "https://api.nuget.org/v3-flatcontainer/microsoft.web.webview2/$version/microsoft.web.webview2.$version.nupkg" -OutFile $nupkg -UseBasicParsing
    Copy-Item $nupkg ".tools\webview2\webview2.zip" -Force
    Expand-Archive ".tools\webview2\webview2.zip" -DestinationPath $sdk -Force
}

# 3. 写版本信息并编译窗口外壳
Write-Host "==> 编译窗口外壳（v$appVersion）"
New-Item -ItemType Directory -Force -Path "build\shell" | Out-Null
$assemblyInfo = @"
using System.Reflection;
using System.Runtime.InteropServices;

[assembly: AssemblyTitle("vidnote")]
[assembly: AssemblyDescription("vidnote - B 站视频笔记")]
[assembly: AssemblyCompany("Paperkite Studio")]
[assembly: AssemblyProduct("vidnote")]
[assembly: AssemblyCopyright("Copyright © 2026 Paperkite Studio")]
[assembly: AssemblyVersion("$four")]
[assembly: AssemblyFileVersion("$four")]
[assembly: AssemblyInformationalVersion("$appVersion")]
[assembly: ComVisible(false)]
"@
[IO.File]::WriteAllText(
    (Join-Path (Get-Location) "build\shell\AssemblyInfo.cs"),
    $assemblyInfo,
    [Text.UTF8Encoding]::new($true)
)
& $csc /nologo /target:winexe /platform:anycpu /win32manifest:shell\app.manifest `
    /win32icon:$icon `
    /out:build\shell\vidnote-app-host.exe `
    /r:"System.Net.Http.dll" /r:"System.Windows.Forms.dll" /r:"System.Drawing.dll" `
    /r:"$sdk\lib\net462\Microsoft.Web.WebView2.Core.dll" `
    /r:"$sdk\lib\net462\Microsoft.Web.WebView2.WinForms.dll" `
    shell\Program.cs build\shell\AssemblyInfo.cs

# 4. 生成单文件启动器
Write-Host "==> 生成单文件 $appDir\vidnote-app.exe"
[IO.File]::WriteAllText(
    (Join-Path (Get-Location) "build\shell\build-id.txt"),
    [DateTime]::UtcNow.ToString("yyyyMMddHHmmss"),
    [Text.UTF8Encoding]::new($false)
)
Remove-Item $appDir -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $appDir | Out-Null
& $csc /nologo /target:winexe /platform:anycpu /win32manifest:shell\app.manifest `
    /win32icon:$icon `
    /out:"$appDir\vidnote-app.exe" `
    /r:"System.Windows.Forms.dll" /r:"System.Drawing.dll" `
    /resource:"build\shell\vidnote-app-host.exe,vidnote-app-host.exe" `
    /resource:"$exeDir\$serverName,vidnote-server.exe" `
    /resource:"$sdk\lib\net462\Microsoft.Web.WebView2.Core.dll,Microsoft.Web.WebView2.Core.dll" `
    /resource:"$sdk\lib\net462\Microsoft.Web.WebView2.WinForms.dll,Microsoft.Web.WebView2.WinForms.dll" `
    /resource:"$sdk\runtimes\win-x64\native\WebView2Loader.dll,WebView2Loader.dll" `
    /resource:"build\shell\build-id.txt,build-id.txt" `
    shell\Launcher.cs build\shell\AssemblyInfo.cs

$total = [math]::Round((Get-Item "$appDir\vidnote-app.exe").Length / 1MB, 2)
Write-Host "完成：单文件 $appDir\vidnote-app.exe（$total MB）"
