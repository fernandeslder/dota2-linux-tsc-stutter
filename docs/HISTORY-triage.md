# User history doc triage (source: "Fixing Ntsync Autoload Dependency Error.pdf", a Gemini chat, ~Sep 19 2026)
Treat as evidence, not truth: no reliable stutter measurement existed. Item status = what the USER reported tried.
Machine fact discovered: lspci now shows ONLY the NVIDIA GPU -> MUX already set to Discrete (dGPU-only) in BIOS; the
AMD iGPU is disabled. (Brief's "with its Radeon iGPU" is stale.) Steam launch options currently:
`LD_PRELOAD="" SDL_AUDIODRIVER=pulseaudio %command% -vulkan -threads 8 -high -novid -map dota -nojoy +fps_max 144`

| # | item | status | user-reported effect (unmeasured) |
|---|------|--------|-----------------------------------|
| 1 | LD_PRELOAD="" (strip Steam overlay hook) | tried | "resolved hard periodic cycle"; kept |
| 2 | `-threads 16` / `-threads 8` | tried | 8 "almost completely fixes it" (hybrid mode era) |
| 3 | `taskset -c 0-7,16-23` (CCD0 pin) | tried | no clear effect |
| 4 | `__GL_MaxFramesAllowed=1` | tried | "even worse"; removed |
| 5 | `__NV_PRIME_RENDER_OFFLOAD=1`, `__GLX_VENDOR_LIBRARY_NAME=nvidia`, `__VK_LAYER_NV_optimus`, `VK_ICD_FILENAMES` | tried | stutter returned / mixed; moot now (dGPU-only) |
| 6 | `prime-run` | untried | - |
| 7 | gamescope wrapper (various flags) | suggested, not confirmed tried | - |
| 8 | Disable mouse polling rate >1000 Hz | untried(?) | - |
| 9 | Steam: no downloads during gameplay; in-game vsync off, fps cap 144, AA off/FXAA | partly | - |
| 10 | In-game: NVIDIA Reflex Enabled/Boost, Compute Shaders off, Atmospheric Fog/Caustics off | unclear | - |
| 11 | CPU governor performance + EPP performance | tried (already) | CPU already at 5 GHz |
| 12 | `powerprofilesctl`/platform_profile performance | currently performance | - |
| 13 | BIOS MUX -> Discrete graphics | tried | "stutter not consistent but every ~1 min freezes 1-2 s" |
| 14 | Switch to X11 session (plasma-x11-session) | tried, display broke, reverted | - |
| 15 | sysctl vm.dirty_background_ratio=5, vm.dirty_ratio=10 (`/etc/sysctl.d/99-game-stutter.conf`) | tried | - |
| 16 | KDE: screen tearing "allow fullscreen" off | tried | - |
| 17 | Baloo purge/disable (baloo_file) + KRunner plugin trimming + Task Manager badge/progress off | tried | "stutters are back" |
| 18 | `nvidia-smi -pm 1`, `-lgc 1200,2280 / 1500,2445 / 1800,2445`, `-lmc 9001,9001` | tried | P-state dips seen in log (P4/P5/P8 at low util, e.g. at fps_max cap) |
| 19 | `echo on > /sys/bus/pci/devices/0000:01:00.0/power/control` (disable RTD3) | tried | still bad |
| 20 | `+fps_max 0` (uncapped) | tried | - |
| 21 | `VK_PRESENT_MODE_IMMEDIATE_KHR=1`, `ENABLE_VKBASALT=0` | tried | no help |
| 22 | **Proton Experimental / Proton GE (Windows build)** | tried | **"Proton works very well" (smooth) — but "can't play online with a compatibility layer installed"** |
| 23 | `LD_PRELOAD=/usr/lib/libmimalloc.so` | tried (loaded confirmed) | "same still stuttering" |
| 24 | `SDL_VIDEODRIVER=wayland`, `SDL_IM_MODULE=none` | suggested at end; unclear if tried | - |
| 25 | `gamescope -W 2560 -H 1440 -r 144 --backend wayland --force-grab-cursor -f` | suggested at end; unclear | - |
| 26 | Test with nvidia-smi logging: GPU util 40-60%, 60-105 W, P0, clocks 2445 MHz, util drop events to P4/P5 | observation | dips to ~3% util every ~30-60 s are the "freeze" moments (CPU/engine stall, GPU idles) |

## Key evidence extracted
- **Proton (Windows dota2.exe via DXVK) ran smoothly; the native Linux build stutters** -> strong lead: native Source2
  build / its SDL/Vulkan/Wayland/XWayland path, not hardware, not kernel, not thermals. The Gemini claim that "VAC blocks
  Proton for matchmaking" is UNVERIFIED and likely false (verify via research); spectating is unaffected anyway.
- Log shows util collapse (3-5%) with GPU in P0 -> GPU is starved: the stall is CPU/engine/presentation-side.
- nvidia-smi polling at 1 Hz was running during the user's tests (collector effect is a hypothesis to test).
- Dips/freezes every ~30-60 s (sparse pattern) + earlier "periodic hard cycle" removed by LD_PRELOAD="".
- Known-suspect not yet examined: Steam overlay / gameoverlayrenderer, steamwebhelper CPU, a local LLM server (GPU), KWin.

## Re-test at the end (promising): Proton vs native A/B; -threads values; SDL_VIDEODRIVER=wayland vs x11 (XWayland);
LD_PRELOAD="" ; gamescope; mimalloc; fps_max 144 vs 0; vm.dirty sysctl; Reflex; baloo off; gpu clock lock; RTD3 off.

## Outcome (2026-10-09)
Root cause was not in this list: firmware leaves CPU0's TSC 2.95 s behind (REPORT.md). Re-test results for the promising items are in REPORT.md section 6. `-threads 8` is the only item with a small measurable benefit after the root-cause fix; Proton gave no advantage; everything else was neutral. "Proton works very well" in the notes was not reproduced (Proton stalled the same way before the fix, and ~2/min after).
