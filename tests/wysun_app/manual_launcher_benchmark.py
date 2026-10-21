#!/usr/bin/env python3
"""Deterministic launcher microbenchmark; never opens media or reads user data.

Use --source for preserved-source vs changed-source comparisons. Offscreen results
measure application logic/Qt only. A real native Qt platform needs a coordinated
private compositor runtime; this script never starts or modifies a compositor.
"""
import argparse
import json
import os
from pathlib import Path
import resource
import statistics
import sys
import tempfile
import time

start=time.perf_counter()
parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,default=Path(__file__).resolve().parents[2] / 'apps/wysun');parser.add_argument('--platform',choices=['offscreen','wayland','xcb'],default='offscreen');args=parser.parse_args()
with tempfile.TemporaryDirectory(prefix='wysun-launcher-bench-') as folder:
    home=Path(folder)
    os.environ['HOME']=str(home);os.environ['QT_QPA_PLATFORM']=args.platform;os.environ['ORBIT_REDUCED_MOTION']='1'
    for name,suffix in [('XDG_CONFIG_HOME','config'),('XDG_DATA_HOME','data'),('XDG_CACHE_HOME','cache'),('XDG_STATE_HOME','state')]:
        path=home/suffix;path.mkdir(mode=0o700);os.environ[name]=str(path)
    if args.platform=='offscreen':
        path=home/'run';path.mkdir(mode=0o700);os.environ['XDG_RUNTIME_DIR']=str(path)
    sys.path.insert(0,str(args.source.resolve()))
    from PySide6.QtWidgets import QApplication
    from desktop_v3 import OrbitV3
    from data_v2 import StoreV2
    app=QApplication([])
    if args.platform not in app.platformName():raise RuntimeError('Qt loaded '+app.platformName()+', expected '+args.platform)
    store=StoreV2(home/'store')
    for i in range(30):store.save_snippet('Synthetic snippet '+str(i),'s'+str(i),'Fixture text '+str(i))
    before=time.perf_counter();window=OrbitV3(store,test=True);construct_ms=(time.perf_counter()-before)*1000
    window.apps=[dict(kind='app',title='Synthetic App '+str(i),subtitle='fixture only',path='/tmp/not-launched.desktop',key='own'+str(i),tag='app',icon='application-x-executable') for i in range(1000)]
    window.show_mode('home');app.processEvents();first_ms=(time.perf_counter()-start)*1000
    def timed(fn):
        before=time.perf_counter();fn();app.processEvents();return (time.perf_counter()-before)*1000
    warm=[]
    for _ in range(6):window.hide();warm.append(timed(lambda:window.show_mode('home')))
    search=[]
    for query in ('Synthetic App 9','Synthetic App 999','Synthetic App 99','no result','2+4',''):
        def render(q=query):window.search.setText(q);window.render()
        search.append(timed(render))
    navigation=[]
    for mode in ('snippets','calculator','emoji','clipboard','home'):
        navigation.append(dict(mode=mode,ms=round(timed(lambda m=mode:window.set_mode(m)),3)))
    first=resource.getrusage(resource.RUSAGE_SELF);t=time.perf_counter()
    while time.perf_counter()-t<.5:app.processEvents();time.sleep(.01)
    last=resource.getrusage(resource.RUSAGE_SELF);idle=last.ru_utime+last.ru_stime-first.ru_utime-first.ru_stime
    print(json.dumps(dict(source=str(args.source),platform=app.platformName(),fixture_apps=1000,fixture_snippets=30,process_to_first_ui_ms=round(first_ms,3),construct_ms=round(construct_ms,3),warm_open_ms=[round(x,3) for x in warm],warm_median_ms=round(statistics.median(warm),3),search_render_ms=[round(x,3) for x in search],navigation=navigation,idle_cpu_s_per_half_second=round(idle,4),peak_rss_kib=last.ru_maxrss,scope='Qt/application only; excludes compositor/input latency and debounce')))
    window.hide()
    for utility in window.utilities.values():
        if hasattr(utility,'timer'):utility.timer.stop()
    store.db.close()
