# Dota 2 native signal sources — verified on THIS install

Scope: which signal sources the **Dota 2 native Linux build** actually offers,
so the collector knows what to trust and what needs a live launch to confirm.
Everything here was checked by inspecting files on disk and grepping strings out
of the installed binaries — **no GUI was launched** for this document.

Install inspected:

```
~/.steam/steam/steamapps/common/dota 2 beta/
  game/bin/linuxsteamrt64/            engine + shared libs
  game/dota/bin/linuxsteamrt64/       libclient.so, libserver.so, libhost.so
  game/dota/cfg/                      perftest.cfg, machine_convars_default.vcfg, ...
  game/core/                          core engine + pak01 vpks
```

Commands used (reproducible):

```sh
DOTA="$HOME/.steam/steam/steamapps/common/dota 2 beta"
strings -n 5 "$DOTA/game/dota/bin/linuxsteamrt64/libclient.so" > /tmp/libclient.strings
grep -E '^cl_showfps$|^cl_printfps$|^cl_resetfps$|^fps_max$' /tmp/libclient.strings
grep -aoiE 'condebug|console\.log|con_logfile|engine_no_focus_sleep|con_enable' \
     "$DOTA/game/bin/linuxsteamrt64/"*.so
sed -n '1,60p' "$DOTA/game/dota/cfg/perftest.cfg"
```

## Summary table

| source | exists on this install? | how to enable | where output goes | loggable to file? | needs live launch to confirm |
|---|---|---|---|---|---|
| MangoHud per-frame CSV | **yes** (0.8.4-1.1) | see below | `<output_folder>/<app>_<date>.csv` | **yes** (live file) | no — validated |
| `cl_showfps` cvar | yes (libclient.so) | `cl_showfps 1\|2` | on-screen | only via console log | output format yes |
| `cl_printfps` command | yes (libclient.so) | `cl_resetfps` then `cl_printfps` | console | via console log | yes |
| `cl_resetfps` command | yes (libclient.so) | console | console | via console log | yes |
| `dota_hud_netgraph` | yes (libclient.so, panorama `dota_hud_netgraph.xml`) | HUD setting / cvar | on-screen HUD | **no** (HUD only) | no |
| `net_graph` (CS-style) | **no** (string absent) | — | — | — | no |
| console logging (`console.log`) | engine has `con_logfile`, `console.log`, `con_enable` (libengine2.so) | `-console` + `con_logfile`/`-condebug`(?) | `console.log` in game dir (path to confirm) | **yes, if enabled** | **yes** (path + switch) |
| `engine_no_focus_sleep` | yes (libengine2.so) | engine cvar | internal | no | no |
| frame pacing stats | yes — `frame_sleep_time_max`, `frame_oversleep_time_max`, `frame_sleep_time_50th_percentile`, `frame_oversleep_time_95th_percentile`, `frame_*_sample_count` (libclient.so) | query as cvars | console | via console log | exact units yes |
| `fps_max`, `fps_max_ui` | yes | cvar | internal | no | no |
| `mat_vsync`, `mat_viewportscale` | yes | cvar | internal | no | no |
| `r_low_latency` | yes (libclient.so) | cvar | internal | no | no |
| `timedemo` | yes (libclient.so) | console | console | via console log | yes |
| Source 2 "perf report" | help text found: *"When a perf report is dumped at the end of the session, should it be detailed?"* (libclient.so); `perf_samples`/`perf_time` strings present | cvar (name not resolvable from strings) | session dump file | likely file | **yes** |
| `debug_spew`, `cl_dormant_spew`, `cl_ent_spew_derived_classes` | yes | cvar | console | via console log | no |
| built-in `perftest.cfg` | yes — `game/dota/cfg/perftest.cfg` | `exec_async perftest` (**needs cheats**) | console (`cl_printfps` output) | via console log | yes |

## Steam launch options actually recorded for appid 730

Read from `~/.steam/steam/userdata/STEAMID/config/localconfig.vdf` (search for
`"730"` → `LaunchOptions`). Current value (escaped quotes collapsed):

```
LD_PRELOAD="" SDL_AUDIODRIVER=pulseaudio %command% -vulkan -threads 8 -high -novid -map dota -nojoy +fps_max 144
```

This matches `docs/HISTORY-triage.md`. `~/.steam/steam/steamapps/compatdata/730`
does **not** exist, i.e. there is no Proton prefix on disk for Dota right now
(the Proton A/B from the history was done on another machine/run or removed).

## MangoHud (primary frametime source)

* Version on this box: `0.8.4-1.1`. Binary `/usr/bin/mangohud`, layer lib
  `/usr/lib/mangohud/libMangoHud.so`, implicit Vulkan layer manifest
  `/usr/share/vulkan/implicit_layer.d/MangoHud.x86_64.json`
  (layer name `VK_LAYER_MANGOHUD_overlay_x86_64`, enabled by env `MANGOHUD=1`).
* Confirmed CSV header (no `log_versioning`), one row per frame:

  ```
  fps,frametime,cpu_load,cpu_power,gpu_load,cpu_temp,gpu_temp,gpu_core_clock,
  gpu_mem_clock,gpu_vram_used,gpu_power,ram_used,swap_used,process_rss,cpu_mhz,elapsed
  ```

  `frametime` is **milliseconds**, `elapsed` is a monotonic clock in
  **nanoseconds** since logging started. The log is written **live** while the
  app runs, and the file's statx **birth time** is the epoch anchor (see
  `docs/DETECTOR-COLLECT.md`).
* Note: MangoHud's own GPU power/clock columns read 0 on this driver via its
  internal path; the collector uses NVML directly instead.

### Config snippet (written per run by `stutter collect`)

```ini
# runs/<id>/raw/mangohud.conf
output_folder=/abs/path/runs/<id>/raw/mangohud
output_file=
autostart_log=1
log_duration=0        # 0 = unlimited; keep logging the whole run
log_interval=0
fps_only=0            # MUST be 0 to keep the frametime column
```

### Launch options that work with the **native Vulkan** build

Preferred (activates MangoHud through its implicit Vulkan layer — **no new
LD_PRELOAD**, so it does not undo `LD_PRELOAD=""`):

```
LD_PRELOAD="" MANGOHUD=1 MANGOHUD_CONFIGFILE=/abs/path/runs/<id>/raw/mangohud.conf ENABLE_VKBASALT=0 %command% -vulkan
```

Wrapper form (works for native **and** Proton):

```
MANGOHUD_CONFIGFILE=/abs/path/runs/<id>/raw/mangohud.conf mangohud %command%
```

`stutter collect start` prints both, with the run's real config path. The env
var `MANGOHUD_CONFIGFILE` is used (not `MANGOHUD_CONFIG`) precisely because it
survives Steam's space-splitting of launch options.

## What still needs a live launch to confirm

1. Whether the native build writes a `console.log` (and exactly where) when
   launched with `-console`/`-condebug`. The engine contains `con_logfile` and
   the literal `console.log`, but `-condebug` itself was **not** found in
   `libengine2.so`/`libclient.so` on this build, so the switch name is unverified.
2. The exact `cl_printfps` output format and whether `cl_resetfps`/`cl_printfps`
   work from a **live spectate** session (no cheats) — `perftest.cfg` implies
   `exec_async` needs cheats, but the fps commands themselves likely do not.
3. The Source 2 perf-report cvar name and its dump path.

None of these are on the critical path: the collector's primary frametime signal
is MangoHud, and Dota's native console sources are optional cross-checks.
