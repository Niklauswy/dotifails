#!/usr/bin/env python3
"""Warm paired synthetic BGRA→LIVE→H264 comparison, never captures a device.

Run serially with --coordinated. Reports whole child pipeline CPU, not isolated
painter CPU; RSS is cumulative maximum, not incremental renderer allocation.
"""
import argparse
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'apps/capture/tests'))
from manual_live_effects_proof import run_case


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--coordinated',action='store_true');args=parser.parse_args()
    if not args.coordinated:parser.error('Reserve the serial media slot, then pass --coordinated')
    for key in ['APPIMAGE','APPDIR','ARGV0','DISPLAY','WAYLAND_DISPLAY','DBUS_SESSION_BUS_ADDRESS','HYPRLAND_INSTANCE_SIGNATURE','PYTHONPATH','PYTHONHOME']:os.environ.pop(key,None)
    with tempfile.TemporaryDirectory(prefix='wysun-live-comparison-') as folder:
        root=Path(folder);os.environ.update(HOME=folder,QT_QPA_PLATFORM='offscreen',PATH='/usr/bin:/bin',DBUS_SYSTEM_BUS_ADDRESS='unix:path='+folder+'/no-system-bus')
        for name,tail in [('XDG_CONFIG_HOME','config'),('XDG_DATA_HOME','data'),('XDG_STATE_HOME','state'),('XDG_CACHE_HOME','cache'),('XDG_RUNTIME_DIR','run')]:
            path=root/tail;path.mkdir(mode=0o700);os.environ[name]=str(path)
        for live in (False,True):
            path=root/('warm-'+str(live));path.mkdir();run_case(path,live)
        pairs=[]
        for repetition,order in enumerate(((False,True),(True,False),(False,True))):
            results={};paths={}
            for live in order:
                path=root/(str(repetition)+'-'+str(live));path.mkdir();paths[live]=path
                results[live]=run_case(path,live)
                assert results[live]['frames']==12 and results[live]['duration']==1.0
                if live:assert results[live]['marker']['baked'] and not results[live]['marker'].get('error')
            def roi(live):
                file=paths[live]/('live.mkv' if live else 'base.mkv')
                return subprocess.check_output(['ffmpeg','-v','error','-i',str(file),'-vf',r'select=eq(n\,5),crop=80:60:140:90','-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'],timeout=10)
            base,live=roi(False),roi(True);assert len(base)==len(live)==80*60*3
            changed=sum(sum(abs(base[i+j]-live[i+j]) for j in range(3))>30 for i in range(0,len(base),3))
            assert changed>20,'No visible encoded effect in the synthetic central ROI'
            pairs.append(dict(order=['live' if x else 'base' for x in order],base=results[False],live=results[True],decoded_effect_pixels_changed=changed))
        summary={}
        for name in ('base','live'):
            summary[name]={key:round(statistics.median(pair[name][key] for pair in pairs),4) for key in ('elapsed_s','child_cpu_s','child_peak_rss_kib')}
        print(json.dumps(dict(result='SYNTHETIC_LIVE_COMPARISON_OK',pairs=pairs,medians=summary,
            limits=['three warm pairs at320x240@12; not desktop/compositor benchmark','child CPU includes bridge/encode/decode/probe','peak RSS cumulative; no incremental memory claim','no portal/input/root/audio/camera; native Wayland effects require separate proof']),indent=2))

if __name__=='__main__':main()
