# Dota 2 stutter on Linux — research (2026-10-08)

Research-only task. No system changes made. All web sources accessed 2026-10-08;
publish dates given where known. **Fact** = verified in a cited source or in the
game's own convar/command dumps. **Speculation** is labeled as such.

Our machine (from HISTORY-triage): RTX 4080 Laptop, dGPU-only (MUX Discrete,
iGPU disabled), KDE Plasma 6 Wayland, CachyOS, Ryzen 9 7945HX (16c/32t, 2 CCDs),
NVIDIA 615.71.09, native Dota 2 `-vulkan -threads 8`, `+fps_max 144`.
Symptom: sparse 1–2 s freezes every ~30–90 s (GPU util collapses to ~3%, P0 —
GPU starved, stall is CPU/engine/presentation-side); an earlier hard periodic
cycle was reportedly removed by `LD_PRELOAD=""`.

## (a) NVIDIA Wayland / KDE Plasma 6, driver 595–615, open vs proprietary module

- **Fact — 615.71.09 (New Feature Branch, released 2026-09-09):** adds
  VK_NV_low_latency2 (out-of-box Proton NVIDIA Reflex for Vulkan-native games),
  fixes low-latency on Wayland/display swapchains, fixes Smooth Motion
  startup/alt-tab hangs, fixes an Xid 109 on Wayland (PRAGMATA), fixes a Vulkan
  fd leak, adds `RmDisableDisplayGlitchPerfLimit` module token, fixes a
  Blackwell nested-divergence correctness issue that "may come with a modest
  performance cost". Stable-branch recommendation at the time: 595 series
  (595.99.02). No Dota-specific or 4080-Laptop-specific regression in the notes.
  ([GamingOnLinux 2026-09-09](https://www.gamingonlinux.com/2026/09/nvidia-driver-615-71-09-released-for-linux-with-vulkan-proton-improvements-with-nvidia-reflex/),
  [Phoronix 2026-09-09](https://www.phoronix.com/news/NVIDIA-615.71.09-Linux-Driver))
- **Fact — 595-series regression report, same GPU class + DE:**
  [CachyOS/distribution#378](https://github.com/CachyOS/distribution/issues/378)
  (open, 2026-03-15): RTX 4080, KDE Plasma Wayland, 595.45.04 (from 590.48.01) →
  severe multi-second lag opening apps/games, `kwin_wayland: Libinput: event
  processing lagging behind`. Reinstalling driver / lowering refresh did not help.
  One commenter: same userspace, symptom disappears on an older kernel
  (kernel-version-dependent). Unresolved.
- **Fact — 570 Vulkan regression:**
  [NVIDIA forum thread](https://forums.developer.nvidia.com/t/570-vulkan-regression-on-both-x11-and-wayland/336006)
  (2025): Vulkan fps roughly halved going 550→570 on X11 *and* Wayland.
  Precedent that NFB Vulkan perf regressions happen; 595.84 notes mention fixing
  "many games" plus regressions from the 580 series.
- **Fact — open vs proprietary kernel module:** the open modules are NVIDIA's
  GPL kernel modules (NOT Nouveau; userspace stays proprietary) and are now the
  default, mandatory on Blackwell. For Ada (our 4080) both work.
  ([bigiron.cc guide](https://www.bigiron.cc/guides/the-nvidia-driver-stack-on-debian-open-vs-proprietary),
  [falcao.org field report](https://falcao.org/posts/nvidia-fedora-kde-wayland/)).
  Open ≠ automatically smoother: [open-gpu-kernel-modules#898](https://github.com/NVIDIA/open-gpu-kernel-modules/issues/898)
  (framerate drops to 0 + stutter on Wayland/wlroots) and an
  [nvidia-open KWin hang](https://forums.developer.nvidia.com/t/bug-kwin-wayland-complete-hang-in-nvidia-open/381542)
  (nvidia-modeset wedge, DRM atomic blocks forever) are open-module bugs.
  Laptop-specific: [nvidia-powerd causes microstutters](https://forums.developer.nvidia.com/t/nvidia-powerd-service-causes-microstutters/370960)
  (jagged MangoHud frametime line for seconds at a time) — directly relevant to a
  7945HX+4080 laptop. Which module is installed here is a local check
  (`pacman -Q | grep nvidia`; `cat /sys/module/nvidia/version` won't say —
  use `dkms status` / package name `*-nvidia-open`).
- **Fact — KDE prerequisites for NVIDIA Wayland:**
  [KDE wiki](https://community.kde.org/Plasma/Wayland/Nvidia): explicit sync
  needs Plasma ≥ 6.1, driver ≥ 495.44 (XWayland apps usable ≥ 555), XWayland ≥
  24.1 against flicker, `nvidia_drm.modeset=1`. All satisfied here in principle;
  verify locally.
- **Speculation:** whether 615.71.09 itself regressed Dota on Ada laptops is
  unknown — no report found naming 615 + Dota + stutter. The 595.99.02 stable
  branch is the documented fallback if a driver A/B is ever approved.

## (b) Native Source 2 build vs Proton/DXVK

- **Fact — native-only stutter is reported, but NOT universal:**
  [Dota-2-Vulkan#480](https://github.com/ValveSoftware/Dota-2-Vulkan/issues/480)
  (native Linux Vulkan micro-stutter at stable FPS, fps cap 100) and
  [Dota-2#3501](https://github.com/ValveSoftware/Dota-2/issues/3501) (open,
  2026-07-05: renderer stutter; `SDL_VIDEODRIVER=wayland` vs `x11` made no
  difference — but AMD GPU, so weak evidence for us).
- **Fact — counterpoint: both can stutter:**
  [Dota-2#3377](https://github.com/ValveSoftware/Dota-2/issues/3377) (open,
  2025-12-16): on 7.40, serious freezes (100 ms–4 s every 15–30 s) on **both**
  native and Proton (Experimental + GE 10-27). So the user's "Proton is smooth"
  observation is machine/config-specific evidence, not proof Proton is
  categorically fine.
- **Fact — SDL/Wayland path:** native Dota goes through SDL2; forcing
  `SDL_VIDEODRIVER=wayland` to bypass XWayland is a known trick
  ([r/linux_gaming guide, 2018](https://www.reddit.com/r/linux_gaming/comments/7rz7zw/guide_to_running_dota_2_on_wayland_natively/)).
  One NVIDIA-forum datapoint
  ([kode54](https://forums.developer.nvidia.com/t/performance-loss-wine-walyand-sdl-wayland/353495/2))
  measured ~20 fps *loss* with SDL/Wine Wayland vs XWayland in their setup —
  direction is not guaranteed; A/B it. Steam client itself runs in XWayland.
- **Speculation:** the native-build-lead theory (HISTORY) is consistent with the
  util-collapse signature (engine thread stalls → GPU idles) but unproven;
  needs the Proton-vs-native A/B under the detector.

## (c) Periodic (~4 s) and sparse (30–90 s) hitches — suspects

- **Fact — Steam overlay Vulkan layer is unstable in exactly this era:**
  [steam-for-linux#13669](https://github.com/ValveSoftware/steam-for-linux/issues/13669)
  (2026-09-30→10-02): overlay's `VulkanSteamOverlayPresent` stack-overflowed and
  killed Vulkan games (incl. via Proton) when the swapchain was recreated.
  Per-game overlay OFF was **not** enough; only
  `DISABLE_VK_LAYER_VALVE_steam_overlay_1` (or equivalent layer disable) avoided
  it. Fixed in the Oct 1 beta client. Older: [steam-for-linux#9736](https://github.com/ValveSoftware/steam-for-linux/issues/9736)
  (overlay open → full-system freeze), [#9586](https://github.com/ValveSoftware/steam-for-linux/issues/9586)
  (new overlay crashes games). Matches the user's `LD_PRELOAD=""` effect
  (stripping the overlay hook removed the hard cycle) better than any other
  single suspect. Overlay code changes roughly monthly — re-test each client
  update.
- **Fact — steamwebhelper CPU spikes fit the signature:** multiple reports of
  webhelper pinning CPU (100%) with GPU dropping to 0% for seconds and games
  stuttering
  ([Steam forums](https://steamcommunity.com/discussions/forum/0/4349988612571275273/),
  [r/Steam](https://www.reddit.com/r/Steam/comments/1brg71h/steamwebhelper_high_cpu_usage/)).
  Detector can correlate directly (threads.csv: webhelper CPU vs hitch times).
- **Fact — NVIDIA shader-cache eviction causes recompile stutter:**
  [NVIDIA forum](https://forums.developer.nvidia.com/t/pre-compiled-shader-cache-cleaned-by-nvidia-driver-causing-stutter-when-launching-vulkan-apps/336196):
  driver deletes cached shaders once over its size limit (raised 128 MB→1024 MB
  back in 460; modern DXVK/Vulkan games exceed it) → stutter returns. Steam
  pre-caching discussion notes first-run compile stutter is expected
  ([Steam forums](https://steamcommunity.com/app/570/discussions/0/4040355479661350314/)).
  Fits *sparse* hitches, not a 4 s rhythm.
- **Fact — ntsync/esync/fsync apply to Proton only.** Native build does not use
  them; relevant solely to the Proton A/B arm (check `PROTON_USE_NTSYNC` /
  kernel ntsync availability then).
- **Weak-evidence — `-threads` / job system on 32-thread 7945HX:** no citable
  thread found tying `-threads` to Dota stutter; support is the user's own
  history (`-threads 8` helped in the hybrid era) plus the engine exposing
  `cojob_lock_hold_warning_threshold_ms` / `cojob_max_no_yield_time_us` (seen in
  the convar dump). Treat as medium hypothesis, test empirically.
- **Fact — allocator:** user already tried `libmimalloc` with no effect
  (HISTORY #23). Deprioritize.
- **Fact — GPU power:** user's own logs show P4/P5/P8 dips at low util; plus the
  nvidia-powerd laptop thread above. Clock-lock A/B was tried pre-detector
  (unmeasured) — re-test under measurement.
- **Fact — VRR/multi-display:** 570 release notes fixed VRR with multiple
  displays; [KDE Discuss gaming-freeze thread](https://discuss.kde.org/t/long-stutters-freezing-when-playing-games/49137)
  (Aug 2026) and the
  [OBS-masks-stutter thread](https://discuss.kde.org/t/kde-plasma-wayland-nvidia-low-fps-stutters/27064)
  (compositor/scanout hint: keeping the compositor busy changes behavior).
- **Weak — btrfs:** `autodefrag` runs a background defrag thread
  ([docs](https://www.ucartz.com/clients/knowledgebase/1248/How-to-Tune-Btrfs-Filesystem-for-Better-Performance.html));
  generic, no Dota link. Check mount opts locally; correlate via disk.csv.
- **Weak — baloo:** indexer causes IO/CPU spikes on KDE
  ([guide](https://cdkagaya.design.blog/2025/05/02/how-to-control-baloo-file-indexer-resource-usage-on-kde/),
  [ArchWiki](https://wiki.archlinux.org/title/Baloo)); user already purged it.
  Keep as correlation column, not an A/B.
- **Fact — closest machine-class report:**
  [Dota-2#3384](https://github.com/ValveSoftware/Dota-2/issues/3384) (open,
  2025-12-28): RTX 3090 + Plasma Wayland + 590.48.01 → FPS collapse then full
  lockup after 20–25 min; **X11 works perfectly**. Different symptom (lockup vs
  hitch) but same stack.
- **Fact — kernel variant matters for Source 2 on CachyOS:**
  [linux-cachyos#801](https://github.com/CachyOS/linux-cachyos/issues/801)
  (closed, 2026-04-08): CS2/Dota 2 severe stutter + GPU util drop to 25% on
  `linux-cachyos` 6.12/6.19, **fully fixed by `linux-cachyos-lts`**. Reproduced
  on vanilla kernel too. A kernel A/B (needs reboot → orchestrator approval) is
  justified.

## (d) Dota's own perf logging — VERIFIED against the game's dumps

Checked `SteamTracking/GameTracking-Dota2` `DumpSource2/convars.txt`
(~555 kB) and `commands.txt` (5191 entries), fetched 2026-10-08. VERIFIED:

| Name | Exists? | Notes |
|---|---|---|
| `cl_showfps` | YES (release) | 0–4; **mode 4 = "Show FPS and Log to file"** — best detector-usable in-game source |
| `cl_printfps` / `cl_resetfps` | YES | dump `cl_showfps` info / reset |
| `cl_showpos` | YES | position overlay (not perf) |
| `cl_showtick`, `cl_showmem` | YES | tick/time bitmask; mem overlay |
| `fps_max` (def 120), `fps_max_tools`, `fps_max_ui` | YES (release/archive) | user's `+fps_max 144` is valid |
| `vprof_on/off/reset`, `vprof_generate_report*` | YES, **developmentonly** | may need dev/tools mode; test in demo first |
| `engine_frametime_print_report` | YES (developmentonly) | "performance report from vprof 'lite' profiler" |
| `cl_frame_perf_sample_buffer_max`, `cl_frametime_summary_report_detailed` | YES | frame sampling + end-of-session perf report |
| `timedemo`/`timedemoquit`, `host_framerate`, `startmovie` | YES | deterministic replay benchmark path exists |
| `stats_print_gpu`, `stat_dropdown*` | YES, developmentonly | — |
| `panorama_show_fps` | YES, developmentonly | UI-layer FPS |
| `net_graph` | **NO — 0 hits in both dumps** | Source 1 leftover; does NOT exist in Dota 2 Source 2 |
| `showbudget` | **NO — 0 hits** | does not exist |
| `perf` / `stat_fps` / UE-style `stat_*` | **NO** | do not exist |
| `-condebug` | UNVERIFIED | no convar by that name; as a *launch option* it is Source 1 heritage — test once, check for `console.log` |
| `-perfdebug` | NO evidence found | treat as nonexistent unless a source turns up |

Full list browsable at [source2.wiki/Convars](https://www.source2.wiki/Convars)
→ [Dota 2 schema explorer](https://s2v.app/SchemaExplorer/dota2/convars).

## (e) "VAC blocks Proton for Dota 2 matchmaking" — directionally TRUE

- **Fact:** [Dota-2#2696](https://github.com/ValveSoftware/Dota-2/issues/2696)
  (2024-05-05, closed as not planned): forcing Proton → "connected with VAC /
  unable to play online matches". A
  [workshop-tools guide](https://www.reddit.com/r/DotA2/comments/1cdc04p/guide_installing_workshop_tools_on_linux/)
  (r/DotA2, 2024-05) states Proton Dota "will no longer pass VAC's automated
  checks, preventing matchmaking, custom games (except self-hosted), **and
  spectating**". Mechanism precision: it is the native VAC module check failing
  under Wine/Proton, not a "Valve bans Proton" policy.
- **Consequence for us:** the detector's live-spectate runs under a Proton
  client may ALSO be VAC-blocked — verify with one short Proton spectate
  attempt. Fallbacks if blocked: Proton **demo replay** (local, no server) or
  compare native-spectate vs Proton-bot-match/demo. The user's "Proton smooth
  but can't play online" is consistent with this.

## (f) Tracker/forum consensus for hybrid-laptop Dota hitching

ValveSoftware/Dota-2 (#3384 lockup/Wayland/NVIDIA, #3501 renderer stutter,
#3377 7.40 freezes on native+Proton, #2696 VAC/Proton); steam-for-linux (#13669
overlay Vulkan kill, Oct 2026); CachyOS (#801 kernel-variant Source 2 stutter
fixed by LTS; #378 595-driver KDE lag, RTX 4080); NVIDIA forums (570 Vulkan
regression, nvidia-powerd microstutter, shader-cache eviction); KDE Discuss
(gaming freezes, compositor/VRR threads) + KDE NVIDIA-Wayland wiki. No single
known-issue thread matches "sparse 30–90 s 1–2 s freezes, RTX 4080 laptop,
dGPU-only, 615.71.09" exactly — hence measurement first.

## Ranked hypotheses (likelihood × testability on our box)

1. **Steam overlay Vulkan layer** (High). Evidence: LD_PRELOAD="" history;
   #13669 proves layer instability Sep–Oct 2026. Test: `LD_PRELOAD=""` vs unset;
   `DISABLE_VK_LAYER_VALVE_steam_overlay_1=1`; in-game overlay on/off — each as
   detector A/B arms. Revert: unset env / re-enable. Detector: hitch-rate delta
   + overlay CPU in threads.csv.
2. **steamwebhelper CPU contention** (High). Evidence: GPU-0%/CPU-100% reports;
   matches util-collapse signature. Test: correlate webhelper threads vs hitch
   timestamps (no change needed); then Steam `-no-browser` / overlay-off arms.
   Revert: normal Steam launch.
3. **NVIDIA power/clocks on laptop (incl. nvidia-powerd)** (Medium-high).
   Evidence: P-state dips in user logs; powerd microstutter thread. Test:
   `nvidia-smi -pm 1`, `-lgc` lock, stop `nvidia-powerd.service` — one at a
   time. Revert: `-rgc`, restart service. Detector: gpu.csv clocks/pstate vs
   hitches.
4. **KWin Wayland presentation (compositing/VRR/scanout)** (Medium-high).
   Evidence: #3384 (X11 clean), KDE gaming threads. Test: VRR off, tearing
   settings, fullscreen vs borderless, gamescope arm. Revert: restore settings.
   Detector: kwin.log/journal around hitches; interval analysis (compositor
   rhythms).
5. **Source 2 job system vs 32 threads (`-threads`)** (Medium). Evidence: user
   history only. Test: `-threads 8` / `16` / unset A/B. Detector: threads.csv
   top-thread saturation + CCD migration (CCD0 = cpu 0–7,16–23 — verify
   `lscpu -e`). Revert: restore `-threads 8`.
6. **Kernel variant (cachyos vs cachyos-lts)** (Medium, high impact if true).
   Evidence: #801. Test: boot LTS + one spectate run (needs approval — reboot).
   Revert: reboot to default kernel.
7. **Shader/pipeline compile (sparse hitches)** (Medium for sparse, Low for
   4 s rhythm). Evidence: cache-eviction thread; first-run stutter notes. Test:
   warmed-cache vs cleared-cache (`~/.local/share/Steam/steamapps/shadercache/570`
   backup + clear) runs. Revert: restore backup.
8. **fps_max / cap-vs-VRR interaction** (Medium-low). Test: `+fps_max 144 / 0 /
   120`. Revert: 144.
9. **Collector overhead, esp. nvidia-smi polling** (method control, per SPEC).
   Test: MangoHud-only vs full-collector runs; lite profile. (History note:
   user's old tests ran 1 Hz nvidia-smi logging during gameplay.)
10. **btrfs/autodefrag, baloo, PipeWire xruns, local-LLM-on-GPU** (Low, correlate
    don't A/B yet). Detector: disk.csv/sys.csv/pipewire.log; `nvidia-smi pmon`
    for unexpected compute apps.
11. **mimalloc/tcmalloc** (Low — already tried, no effect). Skip unless all else fails.
12. **Driver 615.71.09 regression proper** (Unknown). No evidence for/against;
    595.99.02 is the documented fallback — driver swap is disruptive, keep last.

## A/B list — exact options/env/cvars worth testing (one variable each)

Launch options: `-vulkan` vs unset (verify default renderer first);
`-threads 8` vs `-threads 16` vs unset; `-high` vs unset; `-novid -nojoy` (keep);
`+fps_max 144` vs `+fps_max 0` vs `+fps_max 120`;
`SDL_VIDEODRIVER=wayland` vs `=x11` vs unset; `SDL_AUDIODRIVER=pipewire` vs unset;
`LD_PRELOAD=""` vs unset; `DISABLE_VK_LAYER_VALVE_steam_overlay_1=1`;
`VK_PRESENT_MODE_IMMEDIATE_KHR=1` (retest under measurement);
`ENABLE_VKBASALT=0`; Steam client `-no-browser` (webhelper arm);
`taskset -c 0-7,16-23` vs unset; Proton Experimental/GE vs native (demo or
spectate — check VAC first); `__GL_MaxFramesAllowed=1` (history: worse — keep as
negative control only). In-game: Reflex on/off, vsync off, fps cap, AA/FXAA,
compute shaders, fog/caustics. In-console (verify live): `cl_showfps 4`
(frametime log source), `engine_frametime_print_report`,
`vprof_on; vprof_generate_report` (dev-only? — test in demo), `timedemo` replay
for a deterministic load. System (backup + CHANGES note + approval where
noted): clock lock, powerd stop, RTD3 `power/control`, vm.dirty sysctl
(already applied), VRR toggle, LTS kernel boot, shader-cache clear (backup).

## Known gaps / speculation flags

- No source found for Dota `-threads` semantics on >16-thread CPUs, `-condebug`
  producing console.log on Source 2, or `-perfdebug` existing at all — all three
  need one live check each, not more reading.
- Whether 615.71.09 regressed anything vs 595.99.02 on Ada laptops: unknown.
- Whether Proton DotaTV spectate is VAC-blocked (guide says yes): untested —
  decides the Proton A/B design.
- `vprof`/dev-only commands may need a dev launch flag that could affect
  matchmaking/spectate eligibility — test in demo mode first.
- Native default renderer (Vulkan vs legacy GL) in the current build: verify
  from console.log at launch; determines what `-vulkan` actually changes.
