# Fails (exit 1) if any acceptance criterion is unmapped, maps to a missing backlog task, is not
# tagged in 03a-pipeline-logic.md, a required §13 plan document is missing, or an architecture
# decision (AD-n) has no ADR.
# The product plans (01, 04, 05, 06) are private and gitignored: checked when present (locally),
# skipped in a public checkout such as CI. Without 05 the backlog-task lookup is skipped.
# How to run and change the plan: docs/SOP.md. Decision records: docs/adr/ (index in docs/SOP.md).
$ErrorActionPreference = 'Stop'
$docs = Join-Path $PSScriptRoot '..\docs'
$errors = @()

$required = '02-mvp-spec.md', '03-technical-design.md', '03a-pipeline-logic.md', 'traceability.md'
$private  = '01-product-decision.md', '04-validation-plan.md', '05-backlog.md', '06-decision-log.md'
foreach ($f in $required) {
    if (-not (Test-Path (Join-Path $docs $f))) { $errors += "Missing plan document: $f" }
}
if ($errors) { $errors | ForEach-Object { Write-Host "FAIL $_" }; exit 1 }
$havePrivate = -not ($private | Where-Object { -not (Test-Path (Join-Path $docs $_)) })

$spec    = Get-Content (Join-Path $docs '02-mvp-spec.md') -Raw
$backlog = if ($havePrivate) { Get-Content (Join-Path $docs '05-backlog.md') -Raw } else { '' }
$trace   = Get-Content (Join-Path $docs 'traceability.md')
$logic   = Get-Content (Join-Path $docs '03a-pipeline-logic.md') -Raw

$acs   = [regex]::Matches($spec, '(?m)^\| (AC-\d+) \|') | ForEach-Object { $_.Groups[1].Value }
$tasks = [regex]::Matches($backlog, '(?m)^\| ([DI]-\d+) \|') | ForEach-Object { $_.Groups[1].Value }
if (-not $acs) { $errors += 'No acceptance criteria found in 02-mvp-spec.md' }

foreach ($ac in $acs) {
    if ($logic -notmatch "\b$ac\b") { $errors += "$ac not covered in 03a-pipeline-logic.md" }
    $row = $trace | Where-Object { $_ -match "^\| $ac \|" }
    if (-not $row) { $errors += "$ac not mapped in traceability.md"; continue }
    $cols = ($row -split '\|') | ForEach-Object { $_.Trim() }
    # cols: '', AC, design, tasks, eval, ''
    if (-not $cols[2]) { $errors += "$ac has no design section" }
    $refs = [regex]::Matches($cols[3], '[DI]-\d+') | ForEach-Object { $_.Value }
    if (-not $refs) { $errors += "$ac has no backlog task" }
    if ($havePrivate) {
        foreach ($t in $refs) { if ($tasks -notcontains $t) { $errors += "$ac references unknown task $t" } }
    }
}

$design = Get-Content (Join-Path $docs '03-technical-design.md') -Raw
$adrDir = Join-Path $docs 'adr'
$adrText = if (Test-Path $adrDir) { (Get-ChildItem $adrDir -Filter '*.md' | Get-Content -Raw) -join "`n" } else { '' }
$decisions = [regex]::Matches($design, '(?m)^\| (AD-\d+) \|') | ForEach-Object { $_.Groups[1].Value }
foreach ($ad in $decisions) {
    if ($adrText -notmatch "\($ad\)") { $errors += "$ad has no ADR in docs/adr" }
}

if ($errors) { $errors | ForEach-Object { Write-Host "FAIL $_" }; exit 1 }
$taskNote = if ($havePrivate) { "$($tasks.Count) backlog tasks" } else { 'backlog tasks (private plans absent, task lookup skipped)' }
Write-Host "PASS $($acs.Count) acceptance criteria mapped to $taskNote; $($decisions.Count) architecture decisions have ADRs"
