/* offcpu_sampler.c -- low-overhead per-thread state / wchan / syscall sampler.
 *
 * Spawned by detector.collect.collectors.offcpu.OffCpuSampler (see offcpu.py)
 * when a C compiler is available; a pure-Python fallback exists for hosts
 * without gcc.  Both write exactly the same files:
 *
 *   threads_blocked.csv   t_epoch,tid,comm,state,syscall,wchan
 *   threads_cpu.csv       t_epoch,tid,comm,cpu_pct
 *
 * threads_blocked.csv is *compact*: a row is written only when a thread's
 * (state, syscall, wchan) changes, plus a keepalive row every --keepalive-ms.
 * A row therefore means "this thread entered this bucket at t_epoch and stayed
 * until its next row (or the run end)".  The analysis rebuilds interval coverage
 * from that, which is what "what were the threads blocked on" needs.
 *
 * Sampling all 75-ish threads at 100 Hz needs ~225 /proc reads per tick; doing
 * that in Python costs ~3.3 ms per tick (>30% of a core) whereas here it is a
 * fraction of a millisecond, so the game's frametimes are untouched.
 *
 * Build:  cc -O2 -o offcpu_sampler offcpu_sampler.c
 * Run:    ./offcpu_sampler --pid N --blocked-out F --cpu-out G --hz 100
 */

#define _GNU_SOURCE
#include <ctype.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#define MAX_THREADS 16384
#define COMM_MAX 32
#define SC_MAX 48
#define WC_MAX 80

struct lastrec {
    int used;
    int pid;
    char state;
    char syscall[SC_MAX];
    char wchan[WC_MAX];
    char comm[COMM_MAX];
    double last_write;
    unsigned long long cpu_ticks;      /* utime+stime, latest sample */
    unsigned long long cpu_prev_ticks; /* utime+stime, last cpu flush */
    int cpu_seen;
};

static volatile sig_atomic_t stop_flag = 0;
static void on_sig(int s) { (void)s; stop_flag = 1; }

static double now_epoch(void) {
    struct timespec ts;
    clock_gettime(CLOCK_REALTIME, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec / 1e9;
}

/* read up to n-1 bytes from path; NUL-terminate.  returns length or -1. */
static int read_small(const char *path, char *buf, size_t n) {
    int fd = open(path, O_RDONLY);
    if (fd < 0) return -1;
    ssize_t r = read(fd, buf, n - 1);
    int saved = errno;
    close(fd);
    if (r < 0) { errno = saved; return -1; }
    buf[r] = '\0';
    return (int)r;
}

static void sanitize(char *s) {
    for (; *s; s++) {
        if (*s == ',' || *s == '\n' || *s == '\r') *s = '.';
        else if ((unsigned char)*s < 0x20) *s = ' ';
    }
}

static void trim_ws(char *s) {
    size_t n = strlen(s);
    while (n && isspace((unsigned char)s[n - 1])) s[--n] = '\0';
}

/* /proc/<tid>/stat -> comm (fname, trimmed), state (R/S/D...), utime+stime. */
static int parse_stat(const char *text, char *comm, size_t cl, char *state,
                      unsigned long long *ticks) {
    const char *lp = strchr(text, '(');
    const char *rp = strrchr(text, ')');
    if (!lp || !rp || rp < lp) return -1;
    size_t clen = (size_t)(rp - lp - 1);
    if (clen >= cl) clen = cl - 1;
    memcpy(comm, lp + 1, clen);
    comm[clen] = '\0';
    sanitize(comm);
    trim_ws(comm);

    const char *p = rp + 1;
    while (*p == ' ') p++;
    if (!*p) return -1;
    *state = *p;
    p++;
    /* tokens after state: [0]=ppid .. [10]=cmajflt, [11]=utime, [12]=stime */
    char buf[512];
    size_t bi = 0;
    for (const char *q = p; *q && bi < sizeof(buf) - 1; q++) buf[bi++] = *q;
    buf[bi] = '\0';

    unsigned long long vals[13];
    int k = 0;
    char *save = NULL;
    for (char *tok = strtok_r(buf, " \t", &save); tok && k < 13;
         tok = strtok_r(NULL, " \t", &save)) {
        vals[k++] = strtoull(tok, NULL, 10);
    }
    if (k < 13) return -1;
    *ticks = vals[11] + vals[12];
    return 0;
}

/* ------------------------------------------------------------------ */
/* syscall number -> name (x86_64), plus ioctl nvidia/drm detection.  */
/* ------------------------------------------------------------------ */

struct sysent { int nr; const char *name; };

static const struct sysent SYS_TABLE[] = {
    {0,"read"},{1,"write"},{2,"open"},{3,"close"},{4,"stat"},{5,"fstat"},
    {6,"lstat"},{7,"poll"},{8,"lseek"},{9,"mmap"},{10,"mprotect"},{11,"munmap"},
    {12,"brk"},{13,"rt_sigaction"},{14,"rt_sigprocmask"},{15,"rt_sigreturn"},
    {16,"ioctl"},{17,"pread64"},{18,"pwrite64"},{19,"readv"},{20,"writev"},
    {21,"access"},{22,"pipe"},{23,"select"},{24,"sched_yield"},{25,"mremap"},
    {26,"msync"},{27,"mincore"},{28,"madvise"},{32,"dup"},{33,"dup2"},
    {34,"pause"},{35,"nanosleep"},{36,"getitimer"},{37,"alarm"},{38,"setitimer"},
    {39,"getpid"},{41,"socket"},{42,"connect"},{43,"accept"},{44,"sendto"},
    {45,"recvfrom"},{46,"sendmsg"},{47,"recvmsg"},{48,"shutdown"},{49,"bind"},
    {50,"listen"},{55,"getsockopt"},{56,"clone"},{57,"fork"},{59,"execve"},
    {60,"exit"},{61,"wait4"},{62,"kill"},{72,"fcntl"},{73,"flock"},{74,"fsync"},
    {75,"fdatasync"},{76,"truncate"},{77,"ftruncate"},{78,"getdents"},{89,"readlink"},
    {95,"umask"},{96,"gettimeofday"},{97,"getrlimit"},{98,"getrusage"},
    {99,"sysinfo"},{100,"times"},{102,"getuid"},{104,"getgid"},
    {107,"geteuid"},{108,"getegid"},{131,"sigaltstack"},{137,"statfs"},
    {157,"prctl"},{158,"arch_prctl"},{186,"gettid"},{247,"waitid"},
    {202,"futex"},{203,"sched_setaffinity"},{204,"sched_getaffinity"},
    {217,"getdents64"},{218,"set_tid_address"},{219,"restart_syscall"},
    {228,"clock_gettime"},{229,"clock_getres"},{230,"clock_nanosleep"},
    {231,"exit_group"},{232,"epoll_wait"},{233,"epoll_ctl"},{234,"tgkill"},
    {257,"openat"},{262,"newfstatat"},{269,"futimesat"},{270,"pselect6"},
    {271,"ppoll"},{273,"set_robust_list"},{281,"epoll_pwait"},{288,"accept4"},
    {290,"eventfd2"},{291,"epoll_create1"},{293,"pipe2"},{302,"prlimit64"},
    {318,"getrandom"},{319,"memfd_create"},{332,"statx"},{334,"rseq"},
    {424,"pidfd_send_signal"},{425,"io_uring_setup"},{426,"io_uring_enter"},
    {441,"epoll_pwait2"},{449,"futex_waitv"},{452,"fchmodat2"},
};

static const char *sys_name(int nr) {
    size_t n = sizeof(SYS_TABLE) / sizeof(SYS_TABLE[0]);
    for (size_t i = 0; i < n; i++)
        if (SYS_TABLE[i].nr == nr) return SYS_TABLE[i].name;
    return NULL;
}

/* Linux ioctl encoding: bits 8..15 are the magic/type byte.
 * nvidia uses 'F' (0x46); DRM uses 'd' (0x64). */
#define NV_IOCTL_MAGIC 0x46
#define DRM_IOCTL_MAGIC 0x64

/* decode the "syscall" field from a /proc/<tid>/syscall line. */
static void decode_syscall(const char *line, char *out, size_t n) {
    while (*line == ' ') line++;
    if (strncmp(line, "running", 7) == 0) { snprintf(out, n, "-"); return; }
    if (*line == '-' || *line == '\0') { snprintf(out, n, "nosys"); return; }

    char *end = NULL;
    long nr = strtol(line, &end, 10);
    const char *name = (nr >= 0) ? sys_name((int)nr) : NULL;

    if (name && strcmp(name, "ioctl") == 0) {
        /* tokens: nr arg0(fd) arg1(request) ... */
        char buf[256];
        size_t bi = 0;
        for (const char *q = line; *q && bi < sizeof(buf) - 1; q++) buf[bi++] = *q;
        buf[bi] = '\0';
        char *save = NULL;
        char *tok = strtok_r(buf, " \t", &save);   /* nr */
        tok = strtok_r(NULL, " \t", &save);        /* fd = arg0 */
        tok = strtok_r(NULL, " \t", &save);        /* request = arg1 */
        unsigned long long req = tok ? strtoull(tok, NULL, 0) : 0;
        unsigned type = (unsigned)((req >> 8) & 0xffULL);
        if (type == NV_IOCTL_MAGIC)
            snprintf(out, n, "ioctl_nv");
        else if (type == DRM_IOCTL_MAGIC)
            snprintf(out, n, "ioctl_drm");
        else
            snprintf(out, n, "ioctl");
        return;
    }
    if (name) snprintf(out, n, "%s", name);
    else snprintf(out, n, "sys_%ld", nr);
}

/* ------------------------------------------------------------------ */

static struct lastrec *find_rec(struct lastrec *recs, int *nrec, int tid) {
    for (int i = 0; i < *nrec; i++)
        if (recs[i].used && recs[i].pid == tid) return &recs[i];
    if (*nrec >= MAX_THREADS) return NULL;
    struct lastrec *r = &recs[(*nrec)++];
    memset(r, 0, sizeof(*r));
    r->used = 1;
    r->pid = tid;
    return r;
}

int main(int argc, char **argv) {
    int pid = 0, hz = 100;
    double duration = 0.0, keepalive_ms = 1000.0;
    const char *blocked_out = NULL, *cpu_out = NULL;

    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--pid") && i + 1 < argc) pid = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--hz") && i + 1 < argc) hz = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--duration") && i + 1 < argc) duration = atof(argv[++i]);
        else if (!strcmp(argv[i], "--keepalive-ms") && i + 1 < argc) keepalive_ms = atof(argv[++i]);
        else if (!strcmp(argv[i], "--blocked-out") && i + 1 < argc) blocked_out = argv[++i];
        else if (!strcmp(argv[i], "--cpu-out") && i + 1 < argc) cpu_out = argv[++i];
        else if (!strcmp(argv[i], "--version")) { printf("offcpu_sampler 1\n"); return 0; }
        else { fprintf(stderr, "offcpu_sampler: unknown arg %s\n", argv[i]); return 2; }
    }
    if (pid <= 0 || !blocked_out) {
        fprintf(stderr, "usage: offcpu_sampler --pid N --blocked-out F "
                        "[--cpu-out G] [--hz 100] [--duration S] [--keepalive-ms 1000]\n");
        return 2;
    }
    if (hz < 1) hz = 1;
    if (hz > 1000) hz = 1000;

    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = on_sig;
    sigaction(SIGTERM, &sa, NULL);
    sigaction(SIGINT, &sa, NULL);

    FILE *bf = fopen(blocked_out, "w");
    if (!bf) { perror("open blocked-out"); return 1; }
    setvbuf(bf, NULL, _IOFBF, 1 << 20);
    fprintf(bf, "t_epoch,tid,comm,state,syscall,wchan\n");

    FILE *cf = NULL;
    if (cpu_out) {
        cf = fopen(cpu_out, "w");
        if (cf) {
            setvbuf(cf, NULL, _IOFBF, 1 << 16);
            fprintf(cf, "t_epoch,tid,comm,cpu_pct\n");
        }
    }

    long clk = sysconf(_SC_CLK_TCK);
    if (clk <= 0) clk = 100;

    struct lastrec *recs = calloc(MAX_THREADS, sizeof(*recs));
    if (!recs) { fclose(bf); return 1; }
    int nrec = 0;

    char tpath[256], wpath[320], spath[320], buf[4096], comm[COMM_MAX],
         state, sc[SC_MAX], wc[WC_MAX];
    long long period_ns = 1000000000LL / hz;
    double start = now_epoch();
    double next_cpu_flush = start;
    struct timespec next;
    clock_gettime(CLOCK_MONOTONIC, &next);

    while (!stop_flag) {
        double t = now_epoch();
        if (duration > 0 && (t - start) >= duration) break;

        snprintf(tpath, sizeof(tpath), "/proc/%d/task", pid);
        DIR *d = opendir(tpath);
        if (!d) break;   /* process gone */

        struct dirent *e;
        while (!stop_flag && (e = readdir(d)) != NULL) {
            if (!isdigit((unsigned char)e->d_name[0])) continue;
            int tid = atoi(e->d_name);
            if (tid <= 0) continue;

            snprintf(spath, sizeof(spath), "/proc/%d/task/%d/stat", pid, tid);
            if (read_small(spath, buf, sizeof(buf)) < 0) continue;
            unsigned long long ticks = 0;
            if (parse_stat(buf, comm, sizeof(comm), &state, &ticks) != 0) continue;

            snprintf(wpath, sizeof(wpath), "/proc/%d/task/%d/wchan", pid, tid);
            if (read_small(wpath, buf, sizeof(buf)) < 0) buf[0] = '\0';
            trim_ws(buf);
            sanitize(buf);
            snprintf(wc, sizeof(wc), "%s", buf[0] ? buf : "-");

            snprintf(spath, sizeof(spath), "/proc/%d/task/%d/syscall", pid, tid);
            if (read_small(spath, buf, sizeof(buf)) < 0) snprintf(buf, sizeof(buf), "-");
            decode_syscall(buf, sc, sizeof(sc));

            struct lastrec *r = find_rec(recs, &nrec, tid);
            if (!r) continue;
            r->cpu_ticks = ticks;
            int changed = !r->cpu_seen ||
                          r->state != state ||
                          strcmp(r->syscall, sc) != 0 ||
                          strcmp(r->wchan, wc) != 0;
            if (changed || (t - r->last_write) * 1000.0 >= keepalive_ms) {
                fprintf(bf, "%.6f,%d,%s,%c,%s,%s\n", t, tid, comm, state, sc, wc);
                r->state = state;
                snprintf(r->syscall, sizeof(r->syscall), "%s", sc);
                snprintf(r->wchan, sizeof(r->wchan), "%s", wc);
                snprintf(r->comm, sizeof(r->comm), "%s", comm);
                r->last_write = t;
                if (!r->cpu_seen) { r->cpu_prev_ticks = ticks; r->cpu_seen = 1; }
            }
        }
        closedir(d);
        fflush(bf);

        if (cf && t >= next_cpu_flush) {
            double dt = t - next_cpu_flush;
            if (dt <= 0) dt = 1.0;
            for (int i = 0; i < nrec; i++) {
                struct lastrec *r = &recs[i];
                if (!r->used || !r->cpu_seen) continue;
                unsigned long long dticks = r->cpu_ticks - r->cpu_prev_ticks;
                r->cpu_prev_ticks = r->cpu_ticks;
                if (dticks == 0) continue;
                double pct = (double)dticks / ((double)clk * dt) * 100.0;
                fprintf(cf, "%.6f,%d,%s,%.3f\n", t, r->pid, r->comm, pct);
            }
            fflush(cf);
            next_cpu_flush = t + 1.0;
        }

        next.tv_nsec += period_ns;
        while (next.tv_nsec >= 1000000000L) { next.tv_sec++; next.tv_nsec -= 1000000000L; }
        clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &next, NULL);
    }

    fclose(bf);
    if (cf) fclose(cf);
    free(recs);
    return 0;
}
