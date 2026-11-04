# 构建桌面应用（原生窗口 + WebView2 外壳）
#
# 用法：
#   powershell -File scripts/build_app.ps1          # 轻量版（约 16 MB）
#   powershell -File scripts/build_app.ps1 -Full    # 完整版（含 Vosk + whisper 转写）
#
# 产物：
#   dist-app\     或 dist-app-full\
#     vidnote-app.exe                        C# WinForms 外壳（.NET Framework 4.8，系统自带）
#     vidnote-server.exe                     Python 后端（PyInstaller 打包）
#     Microsoft.Web.WebView2.*.dll           WebView2 托管库
#     WebView2Loader.dll                     WebView2 原生加载器
#
# 前置条件：
#   1. 已安装 .NET Framework 4.8（Windows 10/11 自带）
#   2. 已安装 WebView2 运行时（Windows 11 自带；Win10 可能需要装一次）
#   3. 首次构建需要能访问 nuget.org 下载 WebView2 SDK

param(
    [switch]$Full
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$python = ".\.venv\Scripts\python.exe"
$csc = "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe"

$spec = if ($Full) { "vidnote-full.spec" } else { "vidnote.spec" }
$exeDir = if ($Full) { "dist-exe-full" } else { "dist-exe" }
$workDir = if ($Full) { "build-exe-full" } else { "build-exe" }
$appDir = if ($Full) { "dist-app-full" } else { "dist-app" }
$serverName = if ($Full) { "vidnote-server.exe" } else { "vidnote.exe" }

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

# 3. 编译外壳
Write-Host "==> 编译外壳"
New-Item -ItemType Directory -Force -Path "build\shell" | Out-Null
& $csc /nologo /target:winexe /platform:anycpu /out:build\shell\vidnote-app.exe `
    /r:"System.Net.Http.dll" /r:"System.Windows.Forms.dll" /r:"System.Drawing.dll" `
    /r:"$sdk\lib\net462\Microsoft.Web.WebView2.Core.dll" `
    /r:"$sdk\lib\net462\Microsoft.Web.WebView2.WinForms.dll" `
    shell\Program.cs

# 4. 组装
Write-Host "==> 组装 $appDir"
Remove-Item $appDir -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $appDir | Out-Null
Copy-Item "build\shell\vidnote-app.exe" "$appDir\"
Copy-Item "$exeDir\$serverName" "$appDir\vidnote-server.exe"
Copy-Item "$sdk\lib\net462\Microsoft.Web.WebView2.Core.dll" "$appDir\"
Copy-Item "$sdk\lib\net462\Microsoft.Web.WebView2.WinForms.dll" "$appDir\"
Copy-Item "$sdk\runtimes\win-x64\native\WebView2Loader.dll" "$appDir\"

$total = [math]::Round((Get-ChildItem $appDir -File | Measure-Object Length -Sum).Sum / 1MB, 2)
Write-Host "完成：$appDir\vidnote-app.exe（整包 $total MB）"
