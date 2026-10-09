# CHANGES — data-collection worker (`collectors` branch)

## System configuration

**No system configuration was modified.** No packages were installed (MangoHud
0.8.4, `python-nvidia-ml-py`, `vulkan-tools`, `mesa-utils`, `pw-top`, `ss`,
`qdbus6` were already present). No `/etc` file, sysctl, service, or Steam
setting was changed, so there is nothing to back up or revert.

The only state this work writes outside the repo is `runs/.quiesce-state.json`
when `stutter quiesce on` is used; it is created by the tool and restored by
`stutter quiesce off`.

## Commands run during development (all reversible / read-only)

* `MANGOHUD=... mangohud vkcube` — short synthetic captures used to learn the
  real MangoHud CSV format and to validate the epoch mapping and overhead. Each
  run lasted < 2 minutes and launched no game.
* `strings -n 5 .../libclient.so` + `grep` over Dota's engine libraries — read
  only, used for `docs/DOTA-SIGNAL-SOURCES.md`.
* `mangohud --version`, `nvidia-smi --query-gpu=...`, `lscpu`, `journalctl`,
  `ss -tin`, `pw-top -b`, `qdbus6 org.kde.KWin ...` — read-only probes.

## Repo artifacts added

```
bin/stutter
detector/__init__.py
detector/collect/{__init__,cli,supervisor,mangohud,rundir,profiles,quiesce,env,util}.py
detector/collect/collectors/{__init__,procfs,nvidia,threads,hwmon,subproc}.py
tools/{validate_mangohud_sync,collector_overhead,validate_run_dir}.py
tests/{conftest,test_util,test_rundir,test_mangohud,test_collectors,test_profiles_cli,test_quiesce}.py
docs/{DOTA-SIGNAL-SOURCES,DETECTOR-COLLECT,VALIDATION-collect,CHANGES-collect}.md
```

`.gitignore` extended to keep generated run data out of git.
