param(
  [switch]$BundleOnly
)

$workspaceRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
$frontendRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$javaHome = Join-Path $workspaceRoot ".mobile-tools\jdk-21"
$androidSdk = Join-Path $workspaceRoot ".mobile-tools\android-sdk"

if (-not (Test-Path $javaHome)) {
  throw "JDK 21 was not found at $javaHome"
}

if (-not (Test-Path $androidSdk)) {
  throw "Android SDK was not found at $androidSdk"
}

$env:JAVA_HOME = $javaHome
$env:ANDROID_HOME = $androidSdk
$env:ANDROID_SDK_ROOT = $androidSdk
$env:PATH = "$env:JAVA_HOME\bin;$env:ANDROID_SDK_ROOT\platform-tools;$env:PATH"
$androidRoot = Join-Path $frontendRoot "android"

Push-Location $androidRoot
try {
  & .\gradlew.bat --stop
} finally {
  Pop-Location
}

foreach ($staleDir in @(
  (Join-Path $androidRoot "app\build"),
  (Join-Path $androidRoot "capacitor-cordova-android-plugins\build")
)) {
  if (Test-Path $staleDir) {
    Remove-Item -Recurse -Force $staleDir -ErrorAction SilentlyContinue
  }
}

Push-Location $frontendRoot
try {
  npm run mobile:sync
  if ($LASTEXITCODE -ne 0) {
    throw "npm run mobile:sync failed with exit code $LASTEXITCODE"
  }
} finally {
  Pop-Location
}

Push-Location $androidRoot
try {
  & .\gradlew.bat bundleRelease
  if ($LASTEXITCODE -ne 0) {
    throw "Gradle bundleRelease failed with exit code $LASTEXITCODE"
  }
  if (-not $BundleOnly) {
    & .\gradlew.bat assembleRelease
    if ($LASTEXITCODE -ne 0) {
      throw "Gradle assembleRelease failed with exit code $LASTEXITCODE"
    }
  }
} finally {
  Pop-Location
}
