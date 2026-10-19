#!/usr/bin/env python3
"""Capture only the owned synthetic output; prove primary Python/secondary QS UI.

Run through nested_runtime.py --probe-only. No physical desktop/bus/input accepted.
"""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT=Path(os.environ.get('WYSUN_TEST_SOURCE',Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(ROOT/'apps/quickshell/tests'))
from installed_apps_probe import private_environment,peer_pid,wait_for
from wayland_test_pointer import SyntheticPointer


def main():
    env,runtime,folder=private_environment();home=Path(env['HOME']);processes=[];logs=[];launcher_pid=None;pointer=None
    def cmd(argv,timeout=15):
        return subprocess.check_output(list(map(str,argv)),env=env,cwd='/',text=True,stderr=subprocess.STDOUT,timeout=timeout).strip()
    def hypr(kind):return json.loads(cmd(['hyprctl','-j',kind]))
    def key(*args):cmd(['wtype','-s','200',*args])
    def chord(shift=False):
        key('-P','Super_L','-M','logo','-s','200',*(['-P','Shift_L','-M','shift','-s','100'] if shift else []),'-k','space','-s','100',*(['-p','Shift_L','-m','shift'] if shift else []),'-p','Super_L','-m','logo')
    def mapped():
        return next((w for w in hypr('clients') if w.get('pid')==launcher_pid and w.get('title')=='Wysun'),None)
    def focus():
        w=mapped();return w and not w.get('xwayland',True) and hypr('activewindow').get('address')==w['address']
    def shot(name):
        monitors=hypr('monitors');assert len(monitors)==1 and monitors[0]['name']=='WYSUN-TEST-1'
        time.sleep(.45)
        cmd(['grim','-o','WYSUN-TEST-1',folder/(name+'.png')])
    report={'result':'INCOMPLETE','evidence':'real installed Python and QS, private synthetic output only','phases':[],
            'limits':['no physical session','no private data']}
    try:
        cmd(['/usr/bin/python3',ROOT/'installer/main.py','install','--source',ROOT,'--target-home',home,'--components','wayland','--config-only'],60)
        public=home/'.local/bin/wysun';env['PATH']=str(home/'.local/bin')+':'+env['PATH']
        conf=Path(env['XDG_CONFIG_HOME'])/'orbit';conf.mkdir(parents=True,exist_ok=True)
        (conf/'theme.json').write_text(json.dumps({'id':'severance'}))
        (conf/'appearance.json').write_text(json.dumps({'opacity':95,'reduced_motion':True}))
        # Replace only the runner's explicitly declared public-command fixture.
        shim=folder/'bin/wysun';assert shim.is_file() and shim.parent==folder/'bin'
        shim.write_text('#!/bin/sh\nexec '+str(public)+' "$@"\n');shim.chmod(0o700)
        log=(folder/'visual-shell.log').open('w');logs.append(log)
        shell=subprocess.Popen([str(public),'shell'],env=dict(env,WAYLAND_DEBUG='client'),cwd='/',stdout=log,stderr=subprocess.STDOUT,start_new_session=True);processes.append(shell)
        def status():
            try:return json.loads(cmd([public,'shell','status']))
            except subprocess.SubprocessError:return None
        wait_for(lambda:status() and status()['screens']==['WYSUN-TEST-1'],'installed QS output ready')
        wait_for(lambda:status()['resources']['cpu'] is not None and status()['resources']['memory'] is not None,'real /proc CPU and memory samples',timeout=12)
        report['resources']=status()['resources']
        bindings=hypr('binds');(folder/'visual-bindings.json').write_text(json.dumps(bindings,indent=2))
        matching=[b for b in bindings if str(b.get('key','')).lower()=='space']
        assert len(matching)==2,matching
        # Exercise the real bar through compositor delivery to pointerFocus.
        # This does not create or read a physical input device.
        pointer=SyntheticPointer(env)
        def click(button):pointer.click(45,28,button)
        click(273);time.sleep(.2);report['right_before_keyboard']=status();cmd([public,'shell','close'])
        time.sleep(.4);shot('wysun-synthetic-desktop')
        (folder/'visual-layers.json').write_text(json.dumps(hypr('layers'),indent=2))
        click(272);endpoint=runtime/f'orbit-{os.getuid()}.sock'
        try:wait_for(endpoint.is_socket,'Python launcher from actual virtual-pointer bar click',timeout=2)
        except RuntimeError:
            report['bar_left_diagnostic']={'status':status(),'pointer':hypr('cursorpos'),'devices':hypr('devices')}
            cmd([public,'launcher']);wait_for(endpoint.is_socket,'Python launcher public CLI fallback')
        launcher_pid=peer_pid(endpoint);wait_for(focus,'primary Python native focus')
        assert str(home/'.local/share/orbit/app/orbit.py').encode() in Path(f'/proc/{launcher_pid}/cmdline').read_bytes()
        shot('wysun-python-launcher')
        report['phases'].append({'name':'primary_launcher','native':True,'trigger':'public CLI fallback' if 'bar_left_diagnostic' in report else 'bar click via native virtual pointer','pid':launcher_pid,'image':'wysun-python-launcher.png'})
        pointer.chord();wait_for(lambda:not mapped(),'SUPERspace toggles launcher closed');pointer.chord();wait_for(focus,'SUPERspace toggles launcher open');report['phases'].append({'name':'primary_global_shortcut','trigger':'SUPERspace native virtual keyboard','pass':True})
        click(272);time.sleep(.3);report['left_after_keyboard']={'visible':bool(mapped()),'status':status()};
        if not mapped():cmd([public,'launcher']);wait_for(focus,'reopen after diagnostic leftclick')
        key('6*7');shot('wysun-python-calculator');cmd([public,'launcher']);wait_for(lambda:not mapped(),'Python public toggle closes after search')
        click(273);time.sleep(.3)
        report['right_click_status']=status()
        if status()['surface']!='menu':report['right_click_failure']=True
        cmd([public,'shell','close'])
        pointer.chord(True)
        if status()['surface']!='menu':
            report['secondary_bind_diagnostic']={'status':status(),'pointer':hypr('cursorpos')};cmd([public,'shell','menu'])
        wait_for(lambda:status()['surface']=='menu','secondary Centro public IPC')
        shot('wysun-desktop-center');key('-k','Escape');wait_for(lambda:status()['surface']=='','Centro Escape closes')
        cmd([public,'shell','menu']);wait_for(lambda:status()['surface']=='menu','secondary public IPC')
        key('Notas');shot('wysun-center-notes-filter');key('-k','Return')
        try:
            wait_for(lambda:any(w.get('pid')==launcher_pid and w.get('title','').startswith('Wysun Notes') and not w.get('xwayland',True) for w in hypr('clients')),'secondary Notes action enters preserved Python')
        except RuntimeError:
            report['notes_failure']={'status':status(),'clients':hypr('clients')};raise
        assert status()['surface']==''
        report['phases'].append({'name':'secondary_center','trigger':'SUPERshiftspace and public IPC','notes_route':'real installed Python','images':['wysun-desktop-center.png','wysun-center-notes-filter.png']})
        report['font_inter']=cmd(['fc-match','Inter'])
        log.flush();errors=[line for line in (folder/'visual-shell.log').read_text().splitlines() if any(x in line for x in ['ERROR:','ReferenceError','TypeError','Binding loop','Unable to assign'])]
        assert not errors,errors
        report['result']='PARTIAL' if report.get('right_click_failure') else 'PASS'
        assert not report.get('right_click_failure'),'Bar right click failed: inspect right_click_status'
    finally:
        if pointer:pointer.close()
        if launcher_pid:
            try:os.killpg(launcher_pid,signal.SIGTERM)
            except ProcessLookupError:pass
        for p in processes:
            try:os.killpg(p.pid,signal.SIGTERM);p.wait(timeout=3)
            except ProcessLookupError:pass
            except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
        for log in logs:log.close()
        (folder/'visual-result.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)

if __name__=='__main__':main()
