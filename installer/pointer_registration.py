#!/usr/bin/env python3
"""Explicit opt-in installation of the reviewed, root-owned mouse helper.

Never called by the default installer/session. Does not invoke pkexec, observe
input, change devices/groups/ACLs, or authorize any recording. Use --root for
isolated registration/recovery checks; physical authorization is separate.
"""
import argparse
import os
from pathlib import Path
import stat
from session_registration import register as register_files

FILES={'usr/libexec/wysun-pointer-helper':('apps/capture/privileged/wysun-pointer-helper',0o755),
       'usr/share/polkit-1/actions/org.wysun.pointer.policy':('installer/wysun-pointer.policy',0o644)}
STATE='var/lib/dotifails/pointer-helper'


def secure_paths(root):
    """A user-writable root executable/policy/parent must never be trusted."""
    root=Path(root).absolute()
    if root.resolve()!=root:raise ValueError('Helper root must not traverse symlinks: '+str(root))
    owner=0 if root==Path('/') else os.geteuid()
    for relative in [*FILES,STATE]:
        path=root/relative
        for candidate in [path,*path.parents]:
            if candidate==root.parent:break
            if not candidate.exists() and not candidate.is_symlink():continue
            info=candidate.lstat()
            if stat.S_ISLNK(info.st_mode) or info.st_uid!=owner or info.st_mode&0o022:
                raise ValueError('Helper path must be owned by the installer and not writable by other users: '+str(candidate))


def register(source,root,restore=False,dry_run=False):
    root=Path(root).absolute();secure_paths(root)
    if not dry_run:
        for relative in [*FILES,STATE+'/installed.json']:
            parent=root/relative
            for candidate in reversed(list(parent.parents)):
                if candidate==root or root in candidate.parents:
                    candidate.mkdir(mode=0o755,exist_ok=True)
    result=register_files(source,root,restore,dry_run,files=FILES,state_relative=STATE)
    if not dry_run and not result:secure_paths(root)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('install','remove'))
    parser.add_argument('--source',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--root',type=Path,default=Path('/'))
    parser.add_argument('--dry-run',action='store_true');args=parser.parse_args()
    if args.root==Path('/') and not args.dry_run and os.geteuid()!=0:parser.error('System registration requires an explicitly authorized sudo invocation.')
    return register(args.source,args.root,args.action=='remove',args.dry_run)
if __name__=='__main__':raise SystemExit(main())
