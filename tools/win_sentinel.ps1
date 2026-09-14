# Watchdog for Windows-side model runs.
#
# Why it exists: WDDM lets a CUDA allocation overflow VRAM into host shared
# memory instead of raising OOM. The run just gets slow while the system commit
# charge climbs, and on 2026-09-12 that path took the whole Hyper-V stack down.
# So the commit charge has to be watched actively and the run killed on sight.
#
# Kills every python.exe whose command line matches -Match once either
# threshold is crossed, then exits.
#
# Threshold note (measured 2026-09-13, tools/win_commit_probe.py): a 10 GB CUDA
# allocation charges 10.3 GB of system commit on this box, because WDDM reserves
# a host backing store for every GPU allocation. So a *successful* 8bit Gemma run
# legitimately pushes commit from ~40 GB to ~52 GB against a 62.5 GB limit. An
# absolute ceiling in the 20-55 GB range therefore aborts healthy runs. What
# actually matters is the headroom left under the limit, so that is the trigger.
#
# Floor note: with Gemma-4-E4B 8bit resident (10.8 GiB VRAM -> ~15.4 GiB process
# commit) the *healthy* low-water mark for free commit is ~6.7 GiB, and it dips
# to ~3.5 GiB whenever another GPU-resident service on the same machine wakes up
# and takes its ~2 GiB. A 4 GiB floor therefore kills good runs on someone
# else's spike; 2.5 GiB still leaves room for Windows to breathe.
param(
  [double]$MinFreeCommitGB     = 2.5,
  [double]$ProcCommitAbortGB   = 20,
  [int]$IntervalSec            = 5,
  [string]$Match               = 'emotion-probe',
  [string]$LogPath             = ''
)

# Default the log next to the repo (tools/.. = repo root) rather than anywhere absolute.
if (-not $LogPath) {
  $LogPath = Join-Path (Split-Path $PSScriptRoot -Parent) 'logs\sentinel.log'
}

$dir = Split-Path $LogPath
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }

function Write-Log($msg) {
  $line = '{0} {1}' -f (Get-Date -Format 'HH:mm:ss'), $msg
  Add-Content -Path $LogPath -Value $line
}

$nvsmi = 'C:\Windows\System32\nvidia-smi.exe'

Write-Log ("=== sentinel start: minFreeCommit={0}G procAbort={1}G every {2}s match='{3}' ===" -f `
  $MinFreeCommitGB, $ProcCommitAbortGB, $IntervalSec, $Match)

$peakSys = 0.0
$peakProc = 0.0
$peakVram = 0

while ($true) {
  $os = Get-CimInstance Win32_OperatingSystem
  $sysCommit = ($os.TotalVirtualMemorySize - $os.FreeVirtualMemory) / 1MB
  $freeCommit = $os.FreeVirtualMemory / 1MB

  $procs = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
             Where-Object { $_.CommandLine -like "*$Match*" })
  $procCommit = 0.0
  if ($procs.Count -gt 0) {
    $procCommit = ($procs | Measure-Object -Property PageFileUsage -Sum).Sum / 1MB
  }

  $vram = 0
  try { $vram = [int](& $nvsmi --query-gpu=memory.used --format=csv,noheader,nounits | Select-Object -First 1) } catch { }

  if ($sysCommit  -gt $peakSys)  { $peakSys  = $sysCommit }
  if ($procCommit -gt $peakProc) { $peakProc = $procCommit }
  if ($vram       -gt $peakVram) { $peakVram = $vram }

  Write-Log ('sys={0:N2}G (peak {1:N2}G) free={7:N2}G  proc={2:N2}G (peak {3:N2}G, n={4})  vram={5}MiB (peak {6}MiB)' -f `
    $sysCommit, $peakSys, $procCommit, $peakProc, $procs.Count, $vram, $peakVram, $freeCommit)

  if ($freeCommit -lt $MinFreeCommitGB -or $procCommit -gt $ProcCommitAbortGB) {
    Write-Log ('!!! ABORT: freeCommit={0:N2}G proc={1:N2}G - killing {2} process(es)' -f $freeCommit, $procCommit, $procs.Count)
    foreach ($p in $procs) {
      Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
      Write-Log ('    killed pid {0}' -f $p.ProcessId)
    }
    Write-Log '=== sentinel exit after kill ==='
    break
  }

  Start-Sleep -Seconds $IntervalSec
}
