$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$normalizer = Join-Path $projectDir 'bin\normalizer.exe'
$detector = Join-Path $projectDir 'bin\bayesguard-detector.exe'
$inputPath = Join-Path $projectDir 'sample-events.tsv'
$outputPath = Join-Path $projectDir 'native-results.tsv'

Get-Content -LiteralPath $inputPath | & $normalizer | & $detector 0.5 2 |
    Set-Content -LiteralPath $outputPath -Encoding utf8
if ($LASTEXITCODE -ne 0) { throw "Native pipeline failed with exit code $LASTEXITCODE" }
Write-Output "Saved $outputPath"
