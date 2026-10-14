param(
    [string]$Toolchains = (Join-Path $PSScriptRoot '..\..\work\toolchains')
)

$ErrorActionPreference = 'Stop'
$projectDir = $PSScriptRoot
$toolchains = (Resolve-Path -LiteralPath $Toolchains).Path
$zig = Join-Path $toolchains 'zig14\zig-aarch64-windows-0.14.1\zig.exe'
$env:RUSTUP_HOME = Join-Path $toolchains 'rustup'
$env:CARGO_HOME = Join-Path $toolchains 'cargo'
$env:PATH = "$(Join-Path $env:CARGO_HOME 'bin');$env:PATH"
$env:RUSTFLAGS = '-C linker=rust-lld'
$cargo = Join-Path $env:CARGO_HOME 'bin\cargo.exe'
$binDir = Join-Path $projectDir 'bin'
$localCache = Join-Path $toolchains 'zig14-cache'
$globalCache = Join-Path $toolchains 'zig14-global-cache'
New-Item -ItemType Directory -Force $binDir, $localCache, $globalCache | Out-Null

$windowObject = Join-Path $toolchains 'bayesguard-window.obj'
& $zig build-obj (Join-Path $projectDir 'zig-normalizer\window.zig') -O ReleaseSafe `
    "-femit-bin=$windowObject" --cache-dir $localCache --global-cache-dir $globalCache
if ($LASTEXITCODE -ne 0) { throw 'Zig window feature build failed' }
$env:RUSTFLAGS = "-C linker=rust-lld -C link-arg=$windowObject"
& $cargo build --release --features zig-window --manifest-path (Join-Path $projectDir 'rust-detector\Cargo.toml')
if ($LASTEXITCODE -ne 0) { throw 'Rust build failed' }
Copy-Item -LiteralPath (Join-Path $projectDir 'rust-detector\target\release\bayesguard-detector.exe') `
    -Destination (Join-Path $binDir 'bayesguard-detector.exe') -Force
Copy-Item -LiteralPath (Join-Path $projectDir 'rust-detector\target\release\live.exe') `
    -Destination (Join-Path $binDir 'bayesguard-live.exe') -Force
Copy-Item -LiteralPath (Join-Path $env:RUSTUP_HOME 'toolchains\stable-aarch64-pc-windows-gnullvm\bin\libunwind.dll') `
    -Destination (Join-Path $binDir 'libunwind.dll') -Force

$normalizer = Join-Path $binDir 'normalizer.exe'
$trialExe = Join-Path $toolchains 'normalizer-try.exe'
& $zig build-exe (Join-Path $projectDir 'zig-normalizer\main.zig') -O ReleaseSafe `
    "-femit-bin=$trialExe" --cache-dir $localCache --global-cache-dir $globalCache 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Output 'Zig could not launch its embedded linker; linking the object separately.'
    $object = Join-Path $toolchains 'normalizer-arm64.obj'
    & $zig build-obj (Join-Path $projectDir 'zig-normalizer\entry.zig') -O ReleaseSafe `
        "-femit-bin=$object" --cache-dir $localCache --global-cache-dir $globalCache
    if ($LASTEXITCODE -ne 0) { throw 'Zig object build failed' }
    $libs = foreach ($name in 'kernel32.lib', 'ntdll.lib', 'compiler_rt.lib') {
        $item = Get-ChildItem -LiteralPath $globalCache -Filter $name -Recurse -File |
            Select-Object -First 1
        if ($null -eq $item) { throw "Missing Zig generated library: $name" }
        $item.FullName
    }
    & $zig lld-link "/out:$normalizer" /entry:zig_entry /subsystem:console $object $libs
    if ($LASTEXITCODE -ne 0) { throw 'Separate Zig link failed' }
} else {
    Copy-Item -LiteralPath $trialExe -Destination $normalizer -Force
}

Write-Output "Built native tools in $binDir"
