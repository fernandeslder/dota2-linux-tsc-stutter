// Per-CPU TSC offset check: pins to each CPU, samples (CLOCK_MONOTONIC_RAW, rdtsc) pairs, reports each CPU's TSC
// offset relative to CPU1 in seconds. A healthy machine shows offsets of ~microseconds; this one shows seconds on cpu0.
#define _GNU_SOURCE
#include <sched.h>
#include <stdlib.h>
#include <stdio.h>
#include <stdint.h>
#include <time.h>
#include <x86intrin.h>
static double now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC_RAW,&t);return t.tv_sec+t.tv_nsec*1e-9;}
static void pin(int c){cpu_set_t s;CPU_ZERO(&s);CPU_SET(c,&s);sched_setaffinity(0,sizeof s,&s);}
static void sample(double*t,uint64_t*c){double best=1e9;for(int i=0;i<2000;i++){double a=now();uint64_t x=__rdtsc();double b=now();if(b-a<best){best=b-a;*t=(a+b)/2;*c=x;}}}
int main(int argc,char**argv){
  int n=argc>1?atoi(argv[1]):32; double hz=0;
  { pin(1); double t0,t1;uint64_t c0,c1; sample(&t0,&c0); struct timespec d={0,300000000};nanosleep(&d,0); sample(&t1,&c1); hz=(c1-c0)/(t1-t0);}
  printf("TSC rate (measured on cpu1): %.3f MHz\n",hz/1e6);
  double ref=0;
  for(int cpu=0;cpu<n;cpu++){ pin(cpu); double t;uint64_t c; sample(&t,&c); double off=(double)c/hz - t; if(cpu==1)ref=off; printf("cpu%-2d tsc_offset_s=%+.6f\n",cpu,off);}
  for(int cpu=0;cpu<n;cpu++){}
  return 0;}
