#!/usr/bin/env python3
"""Where was Dota's CPU time during stalls?  perf (-a -g, -k monotonic) + MangoHud csv.
usage: stack_stall_analysis.py perf.data mangohud.csv pid mono_offset btime_epoch [min_ms]"""
import sys, subprocess, csv, collections, bisect, random, re
perf, mh, pid, off, btime = sys.argv[1], sys.argv[2], int(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5])
min_ms = float(sys.argv[6]) if len(sys.argv) > 6 else 100.0
rows = list(csv.DictReader(open(mh)))[0:0]
lines = open(mh).read().splitlines()
hdr = lines[2].split(','); ft_i = hdr.index('frametime'); el_i = hdr.index('elapsed')
frames = []
for l in lines[3:]:
    p = l.split(',')
    try: frames.append((btime + float(p[el_i]) / 1e9 - off, float(p[ft_i])))
    except Exception: pass
out = subprocess.run(['perf', 'script', '-i', perf, '-F', 'comm,pid,tid,cpu,time,ip,sym'], capture_output=True, text=True).stdout.splitlines()
samples = []  # (t, cpu, comm, [syms])
cur = None
for l in out:
    if not l.startswith(('\t', ' ')) and l.strip():
        m = re.match(r'\s*(.+?)\s+(\d+)/(\d+)\s+\[(\d+)\]\s+([\d.]+):', l)
        if m:
            cur = [float(m.group(5)), int(m.group(4)), m.group(1), int(m.group(2)), []]
            samples.append(cur)
    elif l.strip() and cur is not None:
        parts = l.split(None, 1)
        cur[4].append(parts[1].split('+')[0] if len(parts) > 1 else parts[0])
tmin = min(s[0] for s in samples); tmax = max(s[0] for s in samples)
hit = [(t - ft / 1000, t) for t, ft in frames if ft >= min_ms and tmin < t - ft / 1000 and t < tmax]
print(f'perf window {tmax-tmin:.0f}s, samples {len(samples)}, hitches>={min_ms}ms in window: {len(hit)}')
dota = [s for s in samples if s[3] == pid]
starts = [h[0] for h in hit]
def inhit(t):
    i = bisect.bisect_right(starts, t) - 1
    return i >= 0 and t <= hit[i][1]
H = collections.Counter(); C = collections.Counter(); nh = nc = 0
for s in dota:
    key = (s[1] == 0, s[2], (s[4][0] if s[4] else '?'))
    if inhit(s[0]): H[key] += 1; nh += 1
    else: C[key] += 1; nc += 1
hit_time = sum(b - a for a, b in hit); ctl_time = (tmax - tmin) - hit_time
print(f'dota samples in hitch {nh} ({nh/hit_time:.0f}/s), outside {nc} ({nc/ctl_time:.0f}/s)')
print('\n== top (cpu0?, thread, leaf symbol) during hitches, rate per second vs control')
for k, v in H.most_common(25):
    print(f'{v/hit_time:8.1f}/s vs {C[k]/ctl_time:8.1f}/s  cpu0={k[0]!s:5} {k[1]:16s} {k[2]}')
print('\n== samples by cpu during hitches (dota only)')
bycpu = collections.Counter(s[1] for s in dota if inhit(s[0])); print(bycpu.most_common(8))
print('\n== deepest common stacks (top 3 frames) on cpu0 during hitches')
St = collections.Counter(tuple(s[4][:4]) for s in dota if inhit(s[0]) and s[1] == 0)
for k, v in St.most_common(8): print(v, ' <- '.join(k))
print('\n== any process on cpu0 during hitches (all comms)')
A = collections.Counter(s[2] for s in samples if s[1] == 0 and inhit(s[0])); print(A.most_common(8))
