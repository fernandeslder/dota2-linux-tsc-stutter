// Re-align a CPU's TSC (MSR 0x10) with a reference CPU. Needs root and the `msr` kernel module (/dev/cpu/N/msr).
// WARNING: AMD Zen 4 TESTED ONLY. This writes MSR 0x10 (IA32_TSC) as root. That taints the kernel, and it can desync
// KVM guests and anything else that compares rdtsc across CPUs. Use at your own risk; read REPORT.md first.
// Why: on this machine the firmware leaves CPU0's TSC 2.95 s behind the other 31 CPUs (kernel: "Measured 7361475193
// cycles TSC warp between CPUs, turning off TSC clock"). Programs that time with rdtsc (Source 2's ThreadSpin) stall for
// up to that long when a thread migrates onto CPU0.  Kernel timekeeping uses HPET, so rewriting the TSC is safe for it.
// usage: tsc_resync [target_cpu=0] [ref_cpu=1] [--dry-run]
// guards: CPU vendor must be AuthenticAMD; |offset| must be <= 10 s (refuses above); CPU args must be distinct integers
//         in range; any failed pin/read/write exits non-zero.
// revert: this only changes the live TSC. Disable the service, remove the installed files, and reboot (the offset
//         returns to firmware state). Running tsc_resync again with swapped arguments does NOT revert anything.
#define _GNU_SOURCE
#include <errno.h>
#include <sched.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <fcntl.h>
#include <unistd.h>
#include <time.h>
#include <math.h>
#include <x86intrin.h>
#define MAX_OFFSET_S 10.0
static double now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC_RAW,&t);return t.tv_sec+t.tv_nsec*1e-9;}
static int pin(int c){cpu_set_t s;CPU_ZERO(&s);CPU_SET(c,&s);if(sched_setaffinity(0,sizeof s,&s)!=0){fprintf(stderr,"sched_setaffinity(cpu%d): %s\n",c,strerror(errno));exit(1);}return 0;}
static void sample(double*t,uint64_t*c){double best=1e9;for(int i=0;i<4000;i++){double a=now();uint64_t x=__rdtsc();double b=now();if(b-a<best){best=b-a;*t=(a+b)/2;*c=x;}}}
static double hz_of(int cpu){pin(cpu);double t0,t1;uint64_t c0,c1;sample(&t0,&c0);struct timespec d={0,400000000};nanosleep(&d,0);sample(&t1,&c1);return (c1-c0)/(t1-t0);}
static double off_of(int cpu,double hz){pin(cpu);double t;uint64_t c;sample(&t,&c);return (double)c/hz-t;}
// true iff /proc/cpuinfo reports vendor_id AuthenticAMD (the only vendor this was tested on)
static int is_amd(void){
  FILE*f=fopen("/proc/cpuinfo","r");if(!f)return 0;
  char line[256];int ok=0;
  while(fgets(line,sizeof line,f)){
    if(!strncmp(line,"vendor_id",9)){char*v=strchr(line,':');if(v){v++;while(*v==' '||*v=='\t')v++;ok=!strncmp(v,"AuthenticAMD",12)&&(v[12]=='\n'||v[12]=='\0');}break;}
  }
  fclose(f);return ok;
}
// parse a CPU number: whole string must be a non-negative integer below the configured CPU count
static int parse_cpu(const char*s,const char*what){
  char*end;errno=0;long v=strtol(s,&end,10);
  long n=sysconf(_SC_NPROCESSORS_CONF);
  if(errno||end==s||*end!='\0'||v<0||(n>0&&v>=n)){fprintf(stderr,"invalid %s cpu '%s' (expected an integer 0..%ld)\n",what,s,n>0?n-1:0);exit(2);}
  return (int)v;
}
int main(int argc,char**argv){
  int tgt=0,ref=1,dry=0,k=0;
  for(int i=1;i<argc;i++){
    if(!strcmp(argv[i],"--dry-run"))dry=1;
    else if(k==0){tgt=parse_cpu(argv[i],"target");k++;}
    else if(k==1){ref=parse_cpu(argv[i],"reference");k++;}
    else {fprintf(stderr,"usage: %s [target_cpu=0] [ref_cpu=1] [--dry-run]\n",argv[0]);return 2;}
  }
  if(tgt==ref){fprintf(stderr,"refusing: target cpu%d and reference cpu%d are the same CPU\n",tgt,ref);return 2;}
  if(!is_amd()){fprintf(stderr,"refusing: CPU vendor is not AuthenticAMD (this tool was tested on AMD Zen 4 only)\n");return 2;}
  double hz=hz_of(ref);
  double ro=0; for(int i=0;i<5;i++) ro+=off_of(ref,hz); ro/=5;
  for(int iter=0;iter<3;iter++){
    double to=0; for(int i=0;i<5;i++) to+=off_of(tgt,hz); to/=5;
    double diff=ro-to; // seconds the target is behind the reference
    printf("iter %d: target cpu%d offset %+.6f s vs ref cpu%d %+.6f s  (diff %+.6f s, %.0f cycles)\n",iter,tgt,to,ref,ro,diff,diff*hz);
    if(fabs(diff)>MAX_OFFSET_S){fprintf(stderr,"refusing: offset %.1f s exceeds the %.0f s safety cap (the known firmware skew is about 3 s); a larger offset means this is not the defect this tool was written for\n",diff,MAX_OFFSET_S);return 2;}
    if(fabs(diff)<1e-3 && iter==0){printf("already aligned (<1 ms); nothing to do\n");break;}
    if(fabs(diff)<20e-6 && iter>0){printf("aligned within 20 us\n");break;}
    if(dry){printf("dry-run: not writing\n");break;}
    char p[64];snprintf(p,sizeof p,"/dev/cpu/%d/msr",tgt);int fd=open(p,O_RDWR);if(fd<0){perror(p);return 1;}
    pin(tgt); double t;uint64_t c; uint64_t cur; sample(&t,&c);
    // read-modify-write on the target CPU itself to keep the latency small
    double a=now(); if(pread(fd,&cur,8,0x10)!=8){perror("rdmsr");close(fd);return 1;} uint64_t nv=cur+(uint64_t)(int64_t)(diff*hz);
    if(pwrite(fd,&nv,8,0x10)!=8){perror("wrmsr");close(fd);return 1;} double b=now();
    // compensate the (small) read->write latency: TSC advanced (b-a)*hz between read and write
    uint64_t cur2; if(pread(fd,&cur2,8,0x10)!=8){perror("rdmsr (verify)");close(fd);return 1;} (void)cur2;
    nv=nv+(uint64_t)((b-a)*hz*0.5); if(pwrite(fd,&nv,8,0x10)!=8){perror("wrmsr (compensate)");close(fd);return 1;}
    close(fd);
  }
  return 0;}
