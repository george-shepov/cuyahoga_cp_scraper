#!/usr/bin/env python3
import os, shutil, argparse
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(__file__))
OUT = os.path.join(ROOT, 'out')

def find_repeats(path):
    # return list of segments that repeat consecutively
    parts = path.split(os.sep)
    repeats = []
    i = 0
    while i < len(parts)-1:
        j = i+1
        if parts[j] == parts[i]:
            # found run
            run_len = 1
            k = j+1
            while k < len(parts) and parts[k] == parts[i]:
                run_len += 1
                k += 1
            repeats.append((i, i+run_len))
            i = k
        else:
            i += 1
    return repeats


def canonical_relpath(rel):
    parts = rel.split(os.sep)
    out_parts = []
    i = 0
    while i < len(parts):
        # collapse runs of same name
        j = i+1
        while j < len(parts) and parts[j] == parts[i]:
            j += 1
        out_parts.append(parts[i])
        i = j
    return os.sep.join(out_parts)


def collect_problem_dirs(base):
    problems = []
    for root, dirs, files in os.walk(base):
        # compute relative path from base
        rel = os.path.relpath(root, base)
        if rel == '.':
            continue
        if rel.count(os.sep) < 1:
            # single-level under out, skip
            continue
        # collapse repeated segments
        canon = canonical_relpath(rel)
        if canon != rel:
            problems.append((root, rel, canon))
    return problems


def plan_moves(problems):
    moves = []
    for fullpath, rel, canon in problems:
        src = fullpath
        dst = os.path.join(OUT, canon)
        # if src equals dst skip
        if os.path.abspath(src) == os.path.abspath(dst):
            continue
        moves.append((src, dst))
    return moves


def move_contents(src, dst, apply=False):
    os.makedirs(dst, exist_ok=True)
    moved = []
    for name in os.listdir(src):
        s = os.path.join(src, name)
        d = os.path.join(dst, name)
        if os.path.exists(d):
            # avoid overwrite: find new name
            base, ext = os.path.splitext(name)
            i = 1
            while True:
                newname = f"{base}_dup{i}{ext}"
                d = os.path.join(dst, newname)
                if not os.path.exists(d):
                    break
                i += 1
        if apply:
            shutil.move(s, d)
        moved.append((s, d))
    return moved


def remove_empty_dirs(paths, apply=False):
    removed = []
    # sort descending so deepest first
    for p in sorted(paths, key=lambda x: -len(x)):
        try:
            if not os.listdir(p):
                if apply:
                    os.rmdir(p)
                removed.append(p)
        except Exception:
            continue
    return removed


def main(apply=False):
    problems = collect_problem_dirs(OUT)
    moves = plan_moves(problems)
    if not moves:
        print('No nested-repeat directories found under', OUT)
        return 0
    print('Found', len(moves), 'nested-repeat directories. Sample:')
    for src,dst in moves[:10]:
        print('  ', os.path.relpath(src, OUT), '->', os.path.relpath(dst, OUT))
    total_files = 0
    all_moved = []
    dirs_to_check = []
    for src,dst in moves:
        # move contents of src into dst
        files_here = os.listdir(src)
        total_files += len(files_here)
        dirs_to_check.append(src)
        moved = move_contents(src, dst, apply=apply)
        all_moved.extend(moved)
    removed = remove_empty_dirs(dirs_to_check, apply=apply)
    print('\nPlanned actions:')
    print('  directories to canonicalize:', len(moves))
    print('  total files/entries to move (approx):', total_files)
    print('  empty dirs removable after move (approx):', len(removed))
    if apply:
        print('\nApplied moves. Moved', len(all_moved), 'entries.')
        print('Removed', len(removed), 'empty dirs.')
    else:
        print('\nDry-run only. No filesystem changes made.')
    return 0

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--apply', action='store_true', help='Apply changes instead of dry-run')
    args = p.parse_args()
    main(apply=args.apply)
