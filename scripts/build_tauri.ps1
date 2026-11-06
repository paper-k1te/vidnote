# vid2note - Tauri 2.0 Desktop Build Script
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$env:PATH = "$env:USERPROFILE\.cargo\bin;" + $env:PATH

$pyproject = Get-Content pyproject.toml -Raw
$appVersion = [regex]::Match($pyproject, 'version = "([^"]+)"').Groups[1].Value
if (-not $appVersion) { throw "Cannot read version from pyproject.toml" }

Write-Host "==> Building vid2note v$appVersion (Tauri 2.0 Native Rust Desktop)"

# 1. Icons check
$icon = "src-tauri\icons\icon.ico"
if (-not (Test-Path $icon)) {
    Write-Host "==> Generating icons..."
    pnpm dlx @tauri-apps/cli icon assets/vidnote.png -o src-tauri/icons
}

# 2. Cargo build release
Write-Host "==> Compiling Rust desktop & tray core (Release)..."
Push-Location src-tauri
cargo build --release
Pop-Location

# 3. Output to dist-app
$distApp = "dist-app"
if (-not (Test-Path $distApp)) {
    New-Item -ItemType Directory -Force -Path $distApp | Out-Null
}

$releaseExe = "src-tauri\target\release\vid2note-desktop.exe"
if (-not (Test-Path $releaseExe)) {
    $releaseExe = "src-tauri\target\release\vidnote-desktop.exe"
}

$targetExe = "$distApp\vid2note.exe"
if (Test-Path $releaseExe) {
    Copy-Item $releaseExe $targetExe -Force
    Copy-Item $releaseExe "$distApp\vidnote.exe" -Force
    $sizeMB = [math]::Round((Get-Item $targetExe).Length / 1MB, 2)
    Write-Host "==> SUCCESS: $targetExe ($sizeMB MB)"
} else {
    throw "Release executable not found: $releaseExe"
}

# 4. Sync backend server if present
$serverExe = "dist-exe\vid2note-server.exe"
if (-not (Test-Path $serverExe)) {
    $serverExe = "dist-exe\vidnote-server.exe"
}
if (Test-Path $serverExe) {
    Copy-Item $serverExe "$distApp\vid2note-server.exe" -Force
    Copy-Item $serverExe "$distApp\vidnote-server.exe" -Force
    Write-Host "==> Synced backend engine: $distApp\vid2note-server.exe"
}

Write-Host "==> Done! Desktop app is ready at $targetExe"
