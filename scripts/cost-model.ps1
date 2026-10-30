# Recomputes the cost model (docs/03-technical-design.md §8) for the current design and compares it
# with the reviewed baseline (commit 14748b6) and the cost gates. Fails (exit 1) if any scenario is
# worse than its baseline or breaks a gate. Prices are placeholders until D-7. See docs/SOP.md.
param([double]$PIn = 3, [double]$POut = 15)   # EUR per million input / output tokens
$ErrorActionPreference = 'Stop'

function Cost($in, $out, $retry) { (($in * $PIn) + ($out * $POut)) / 1e6 * (1 + $retry) }

# Token estimates per step (thousands). Current design (03a P3, P5):
# - omission explanations are templates (no model call), so report wording only covers non-omissions
# - contradiction detection and presentation-only listing are deterministic (no tokens)
# - screenshots add one vision call at parse time
$scenarios = @(
    @{ Name = 'Typical (3k words, earlier cached)'; In = 17;  Out = 4.5; Retry = 0.10; Base = 0.13; Gate = 0.20 },
    @{ Name = 'First comparison (both extracted)';  In = 22;  Out = 6;   Retry = 0.10; Base = 0.17; Gate = 0.20 },
    @{ Name = 'Heavy (20 pages, at input cap)';     In = 70;  Out = 15;  Retry = 0.20; Base = 0.52; Gate = 0.60 },
    @{ Name = 'Worst case (heavy, all retried)';    In = 100; Out = 22;  Retry = 1.00; Base = 1.26; Gate = 1.50 },
    @{ Name = 'Screenshot vision parse (2 passes)';  In = 3;   Out = 1;   Retry = 0.10; Base = $null; Gate = 0.13 }
)

$fail = @()
Write-Host ('{0,-38} {1,8} {2,9} {3,7}  {4}' -f 'Scenario', 'Cost EUR', 'Baseline', 'Gate', 'Result')
foreach ($s in $scenarios) {
    $c = [math]::Round((Cost ($s.In * 1000) ($s.Out * 1000) $s.Retry), 3)
    $ok = $c -le $s.Gate
    if ($s.Base -ne $null -and $c -gt $s.Base + 0.005) { $ok = $false; $fail += "$($s.Name) worse than baseline" }
    if ($c -gt $s.Gate) { $fail += "$($s.Name) exceeds gate $($s.Gate)" }
    $base = if ($s.Base -ne $null) { '{0:N2}' -f $s.Base } else { 'n/a' }
    Write-Host ('{0,-38} {1,8:N3} {2,9} {3,7:N2}  {4}' -f $s.Name, $c, $base, $s.Gate, $(if ($ok) { 'ok' } else { 'FAIL' }))
}
# The screenshot gate is one allowance unit (≈ a typical comparison), since P2 reserves 1 unit for it.

# Unit economics at target price (Gate 4 is judged on observed usage; this is a sensitivity, not a gate).
$typ = Cost 17000 4500 0.10; $first = Cost 22000 6000 0.10
Write-Host ''
Write-Host 'Unit-economics sensitivity at target price (Gate 4 limit 30%, judged on real usage):'
foreach ($p in @(@{ Plan = 'Individual'; Units = 25; Price = 12 }, @{ Plan = 'Team'; Units = 100; Price = 49 })) {
    $a = $p.Units * $typ / $p.Price * 100; $b = $p.Units * $first / $p.Price * 100
    Write-Host ('  {0,-10} full allowance, follow-up revisions: {1,5:N1}%   every comparison a new project: {2,5:N1}%' -f $p.Plan, $a, $b)
}

if ($fail) { $fail | ForEach-Object { Write-Host "FAIL $_" }; exit 1 }
Write-Host 'PASS cost model no worse than baseline 14748b6 and within cost gates'
