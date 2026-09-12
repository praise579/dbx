[CmdletBinding()]
param(
  [string]$RuntimeDirectory = (Join-Path $PSScriptRoot "..\..\src-tauri\webview2-fixed-runtime"),
  [string]$DownloadDirectory = $env:RUNNER_TEMP,
  [string]$ExpectedSha256 = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Offline portable package runtime. Unlike the Win7 build (pinned to the last
# WebView2 version supporting Windows 7), any recent Fixed Version Runtime
# works on Windows 10/11. The download is a Microsoft-signed cab re-hosted on
# the WebView2RuntimeArchive mirror; the Authenticode signature is the hard
# gate, and a pinned hash can be supplied via -ExpectedSha256 when known.
$runtimeVersion = "133.0.3065.92"
$runtimeFolderName = "Microsoft.WebView2.FixedVersionRuntime.$runtimeVersion.x64"
$archiveName = "$runtimeFolderName.cab"
$runtimeUrl = "https://github.com/westinyang/WebView2RuntimeArchive/releases/download/$runtimeVersion/$archiveName"

if ([string]::IsNullOrWhiteSpace($RuntimeDirectory)) {
  throw "A WebView2 fixed runtime directory is required."
}
if ([string]::IsNullOrWhiteSpace($DownloadDirectory)) {
  $DownloadDirectory = [System.IO.Path]::GetTempPath()
}

New-Item -ItemType Directory -Force -Path $DownloadDirectory | Out-Null
$archivePath = Join-Path $DownloadDirectory $archiveName

if (!(Test-Path $archivePath)) {
  Write-Host "Downloading WebView2 fixed runtime $runtimeVersion (x64)..."
  Invoke-WebRequest -Uri $runtimeUrl -OutFile $archivePath
}

if (![string]::IsNullOrWhiteSpace($ExpectedSha256)) {
  $actualHash = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($actualHash -ne $ExpectedSha256.ToLowerInvariant()) {
    throw "WebView2 fixed runtime SHA-256 mismatch. Expected $ExpectedSha256, got $actualHash."
  }
}

# The archive is accepted only when its original Microsoft signature is valid.
$signature = Get-AuthenticodeSignature -LiteralPath $archivePath
if ($signature.Status -ne [System.Management.Automation.SignatureStatus]::Valid -or
    $null -eq $signature.SignerCertificate -or
    $signature.SignerCertificate.Subject -notmatch "Microsoft Corporation") {
  throw "WebView2 fixed runtime does not have a valid Microsoft signature."
}

$extractDirectory = Join-Path $DownloadDirectory "dbx-webview2-fixed-runtime-$runtimeVersion"
if (Test-Path $extractDirectory) {
  Remove-Item -LiteralPath $extractDirectory -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $extractDirectory | Out-Null

$expand = Join-Path $env:SystemRoot "System32\expand.exe"
& $expand $archivePath "-F:*" $extractDirectory
if ($LASTEXITCODE -ne 0) {
  throw "Failed to extract WebView2 fixed runtime archive (exit code $LASTEXITCODE)."
}

$extractedRuntime = Join-Path $extractDirectory $runtimeFolderName
$runtimeExecutable = Join-Path $extractedRuntime "msedgewebview2.exe"
if (!(Test-Path $runtimeExecutable)) {
  throw "Extracted WebView2 runtime is missing msedgewebview2.exe."
}

if (Test-Path $RuntimeDirectory) {
  Remove-Item -LiteralPath $RuntimeDirectory -Recurse -Force
}
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $RuntimeDirectory) | Out-Null
Move-Item -LiteralPath $extractedRuntime -Destination $RuntimeDirectory

Write-Host "Prepared WebView2 fixed runtime $runtimeVersion at $RuntimeDirectory"
