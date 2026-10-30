# Fails (exit 1) if any acceptance criterion is unmapped, maps to a missing backlog task,
# or a required §13 plan document is missing.
$ErrorActionPreference = 'Stop'
$docs = Join-Path $PSScriptRoot '..\docs'
$errors = @()

$required = '01-product-decision.md', '02-mvp-spec.md', '03-technical-design.md',
            '04-validation-plan.md', '05-backlog.md', '06-decision-log.md', 'traceability.md'
foreach ($f in $required) {
    if (-not (Test-Path (Join-Path $docs $f))) { $errors += "Missing plan document: $f" }
}
if ($errors) { $errors | ForEach-Object { Write-Host "FAIL $_" }; exit 1 }

$spec    = Get-Content (Join-Path $docs '02-mvp-spec.md') -Raw
$backlog = Get-Content (Join-Path $docs '05-backlog.md') -Raw
$trace   = Get-Content (Join-Path $docs 'traceability.md')

$acs   = [regex]::Matches($spec, '(?m)^\| (AC-\d+) \|') | ForEach-Object { $_.Groups[1].Value }
$tasks = [regex]::Matches($backlog, '(?m)^\| ([DI]-\d+) \|') | ForEach-Object { $_.Groups[1].Value }
if (-not $acs) { $errors += 'No acceptance criteria found in 02-mvp-spec.md' }

foreach ($ac in $acs) {
    $row = $trace | Where-Object { $_ -match "^\| $ac \|" }
    if (-not $row) { $errors += "$ac not mapped in traceability.md"; continue }
    $cols = ($row -split '\|') | ForEach-Object { $_.Trim() }
    # cols: '', AC, design, tasks, eval, ''
    if (-not $cols[2]) { $errors += "$ac has no design section" }
    $refs = [regex]::Matches($cols[3], '[DI]-\d+') | ForEach-Object { $_.Value }
    if (-not $refs) { $errors += "$ac has no backlog task" }
    foreach ($t in $refs) { if ($tasks -notcontains $t) { $errors += "$ac references unknown task $t" } }
}

if ($errors) { $errors | ForEach-Object { Write-Host "FAIL $_" }; exit 1 }
Write-Host "PASS $($acs.Count) acceptance criteria mapped to $($tasks.Count) backlog tasks"
