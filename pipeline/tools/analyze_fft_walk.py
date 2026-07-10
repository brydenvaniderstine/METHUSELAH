#!/usr/bin/env python3
"""Analyze 0x7E/0x7F FFT spectral features across walk experiments.

Usage:
  python3 analyze_fft_walk.py                   # scan all pull files with step features
  python3 analyze_fft_walk.py <pull_file.txt>   # analyze one specific file
  python3 analyze_fft_walk.py <file1> <file2>   # compare two files byte-by-byte
"""
import sys, glob, re
import statistics


def analyze_fft_packets(pull_file):
    packets_7e = []
    packets_7f = []
    with open(pull_file) as f:
        for line in f:
            # Standard pull-script label ("Real step feature (1)/(2)") and the
            # bracket shorthand used in manually-transcribed files like
            # walk_experiment_20260707_decoded.txt ("[0x7E]"/"[0x7F]") both occur
            # in the corpus — match either.
            is_7e = ('Real step feature (1)' in line or '[0x7E]' in line) and 'payload=' in line
            is_7f = ('Real step feature (2)' in line or '[0x7F]' in line) and 'payload=' in line
            if is_7e:
                payload = line.split('payload=')[1].strip()
                b = bytes.fromhex(payload)
                if len(b) == 14:
                    packets_7e.append(list(b))
            elif is_7f:
                payload = line.split('payload=')[1].strip()
                b = bytes.fromhex(payload)
                if len(b) == 14:
                    packets_7f.append(list(b))

    fname = pull_file.split('/')[-1]
    print(f"\n=== {fname} ===")
    if not packets_7e and not packets_7f:
        print("  No 0x7E/0x7F packets found")
        return None

    results = {}
    for tag, packets in [('0x7E', packets_7e), ('0x7F', packets_7f)]:
        if not packets:
            print(f"  No {tag} packets found")
            results[tag] = None
            continue
        print(f"\n{tag} — {len(packets)} packets")
        print(f"  {'byte':>4}  {'min':>5}  {'max':>5}  {'mean':>7}  {'stdev':>7}  {'sum':>6}")
        byte_stats = {}
        for i in range(len(packets[0])):
            col = [p[i] for p in packets]
            mean = statistics.mean(col)
            stdev = statistics.stdev(col) if len(col) > 1 else 0.0
            s = sum(col)
            byte_stats[i] = {'min': min(col), 'max': max(col), 'mean': mean, 'stdev': stdev, 'sum': s, 'col': col}
            near500 = '  <<<' if 450 <= s <= 550 else ''
            print(f"  b[{i:2d}]  {min(col):>5}  {max(col):>5}  {mean:>7.1f}  {stdev:>7.2f}  {s:>6}{near500}")
        results[tag] = byte_stats
    return results


def compare_two_files(file1, file2):
    print("\n" + "="*60)
    print("BYTE-BY-BYTE COMPARISON")
    print("="*60)
    r1 = analyze_fft_packets(file1)
    r2 = analyze_fft_packets(file2)
    if not r1 or not r2:
        print("Cannot compare — one or both files missing step features")
        return

    for tag in ['0x7E', '0x7F']:
        if not r1.get(tag) or not r2.get(tag):
            continue
        print(f"\n{tag} comparison ({file1.split('/')[-1]} vs {file2.split('/')[-1]}):")
        print(f"  {'byte':>4}  {'mean1':>7}  {'mean2':>7}  {'Δmean':>7}  {'stdev1':>7}  {'stdev2':>7}  note")
        for i in range(14):
            s1 = r1[tag][i]
            s2 = r2[tag][i]
            delta = s2['mean'] - s1['mean']
            # Flag large relative changes
            avg_stdev = (s1['stdev'] + s2['stdev']) / 2
            flag = ''
            if avg_stdev > 0 and abs(delta) > 2 * avg_stdev:
                flag = '  *** SIGNIFICANT'
            elif abs(delta) > 30:
                flag = '  ** NOTABLE'
            print(f"  b[{i:2d}]  {s1['mean']:>7.1f}  {s2['mean']:>7.1f}  {delta:>+7.1f}  "
                  f"{s1['stdev']:>7.2f}  {s2['stdev']:>7.2f}{flag}")


if __name__ == '__main__':
    if len(sys.argv) == 1:
        found = False
        for f in sorted(glob.glob('pipeline/data/raw_pulls/**/*.txt', recursive=True)):
            try:
                with open(f) as fh:
                    content = fh.read()
                if 'Real step feature' in content or '[0x7E]' in content or '[0x7F]' in content:
                    analyze_fft_packets(f)
                    found = True
            except Exception:
                pass
        if not found:
            print("No pull files with 0x7E/0x7F step features found in pipeline/data/raw_pulls/")
    elif len(sys.argv) == 2:
        analyze_fft_packets(sys.argv[1])
    elif len(sys.argv) == 3:
        compare_two_files(sys.argv[1], sys.argv[2])
    else:
        print("Usage: analyze_fft_walk.py [file1] [file2]")
        sys.exit(1)
