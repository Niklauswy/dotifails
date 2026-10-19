"""Two explicitly authorized synthetic outputs, with atomic failure cases."""
import json
import time


def run_case(run_dir, env, command, start, wait_for):
    from loomrec.portal import PortalCancelled
    from loomrec.portal_image import capture_frame
    from loomrec.desktop_capture import read_topology
    from wayland_portal_cases import prepare_picker
    choice=prepare_picker(run_dir)
    # The runner uses auto placement for a single screen. Anchor our first
    # headless output before hotplug so Hyprland cannot legitimately move it
    # beside the explicitly positioned second screen during this color proof.
    command(['hyprctl','eval','hl.monitor({output="WYSUN-TEST-1",mode="1280x800@60",position="0x0",scale=1})'])
    wait_for(lambda:read_topology()[0].position==(0,0),'anchor first own output')
    command(['hyprctl','eval','hl.monitor({output="WYSUN-TEST-2",mode="640x480@60",position="1280x0",scale=1})'])
    command(['hyprctl','output','create','headless','WYSUN-TEST-2'])
    wait_for(lambda:len(read_topology())==2,'two owned outputs')
    command(['hyprctl','dispatch','hl.dsp.focus({monitor="WYSUN-TEST-2"})'])
    fixture=run_dir/'second-output-fixture.py'
    fixture.write_text('from PySide6.QtWidgets import QApplication,QWidget\n'
        'a=QApplication([]);w=QWidget();w.setWindowTitle("Wysun second output fixture")\n'
        'w.setStyleSheet("background:#af2b32");w.showFullScreen();a.exec()\n')
    process=start('second-output-fixture',['/usr/bin/python3',fixture])
    wait_for(lambda:any(c.get('title')=='Wysun second output fixture' for c in json.loads(command(['hyprctl','-j','clients']))),'own second output window')
    target=next(m for m in json.loads(command(['hyprctl','-j','monitors'])) if m['name']=='WYSUN-TEST-2')
    window=next(c for c in json.loads(command(['hyprctl','-j','clients'])) if c.get('title')=='Wysun second output fixture')
    # A Qt client can initially choose the primary screen despite compositor
    # focus. Place and verify the owned fixture explicitly before judging pixels.
    command(['hyprctl','dispatch','hl.dsp.window.move({window="address:'+window['address']+'",monitor="WYSUN-TEST-2",follow=false})'])
    wait_for(lambda:any(c.get('title')=='Wysun second output fixture' and c.get('monitor')==target['id']
        for c in json.loads(command(['hyprctl','-j','clients']))),'own fixture really on output2')
    blue=next(c for c in json.loads(command(['hyprctl','-j','clients'])) if c.get('title')=='Wysun synthetic opaque fixture')
    command(['hyprctl','dispatch','hl.dsp.focus({window="address:'+blue['address']+'"})'])
    (run_dir/'desktop-fixture-clients.json').write_text(command(['hyprctl','-j','clients']))
    (run_dir/'desktop-fixture-monitors.json').write_text(command(['hyprctl','-j','monitors']))
    (run_dir/'desktop-fixture-workspaces.json').write_text(command(['hyprctl','-j','workspaces']))
    time.sleep(.4);results={};events=[]
    def progress(state):
        events.append(state)
        if state['stage']=='select':choice.write_text('screen:'+state['remaining'][0])
    def color(image,x,y,expected):
        p=image.pixelColor(x,y);rgb=[p.red(),p.green(),p.blue()]
        assert all(abs(a-b)<=4 for a,b in zip(rgb,expected)),(x,y,rgb,expected)
        return rgb
    try:
        image=capture_frame('desktop',True,progress=progress)
        image.save(str(run_dir/'desktop-cursor-two-synthetic-outputs.png'))
        assert (image.width(),image.height())==(1920,800),image.size()
        results['two_outputs']={'size':[image.width(),image.height()],
            'left_rgb':color(image,320,200,[49,87,135]),'right_rgb':color(image,1600,240,[175,43,50]),
            'selections':[e['remaining'] for e in events if e['stage']=='select'],
            'contract':'two normal ScreenCast permissions selected by a declared fixture; sequential, not simultaneous'}
        image.save(str(run_dir/'desktop-cursor-two-synthetic-outputs.png'))
        def cancel_second(state):
            if state['stage']=='select':
                if state['index']==2:raise PortalCancelled('Owned fixture cancels entire second selection')
                choice.write_text('screen:WYSUN-TEST-1')
        try:capture_frame('desktop',True,progress=cancel_second)
        except PortalCancelled:results['cancel_second']='no image returned; first authorized frame discarded'
        else:raise AssertionError('Cancelled desktop unexpectedly returned a partial image')
        def duplicate(state):
            if state['stage']=='select':choice.write_text('screen:WYSUN-TEST-1')
        try:capture_frame('desktop',True,progress=duplicate)
        except RuntimeError as error:
            assert 'repetida' in str(error),str(error)
            results['duplicate']='rejected before reading a second duplicate frame; no partial image returned'
        else:raise AssertionError('Duplicate desktop unexpectedly accepted')
        # Exercise an actual compositor transform and fractional scaling, beyond
        # the separately labeled QImage fixtures. No physical output is changed.
        command(['hyprctl','eval','hl.monitor({output="WYSUN-TEST-2",mode="640x480@60",position="1280x0",scale=1.25,transform=1})'])
        wait_for(lambda:any(o.name=='WYSUN-TEST-2' and o.scale==1.25 and o.transform==1 for o in read_topology()),'fractional rotated owned output')
        time.sleep(.4)
        transformed=capture_frame('desktop',True,progress=progress)
        assert (transformed.width(),transformed.height())==(2080,1000),transformed.size()
        results['fractional_rotation']={'size':[transformed.width(),transformed.height()],
            'left_rgb':color(transformed,400,250,[49,87,135]),'right_rgb':color(transformed,1840,320,[175,43,50]),
            'fixture':'output2 physical640x480,scale1.25,transform1; output1 scale1; explicit independent consent'}
        result=dict(result='WYSUN_DESKTOP_CURSOR_NATIVE_OK',cases=results,
            limits=['picker fixture, no human consent claim','sequential snapshots','no physical monitor/hotplug test'])
        (run_dir/'desktop-cursor-results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2),flush=True)
        return result
    finally:
        process.terminate();process.wait(timeout=3)
        command(['hyprctl','output','destroy','WYSUN-TEST-2'])
