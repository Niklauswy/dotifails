"""Public installed PickColor with a native selector on our own solid fixture."""
import json
import os
import subprocess
from pathlib import Path
import time


def run_case(run_dir,env,command,start,wait_for):
    from wayland_test_pointer import SyntheticPointer
    pointer=SyntheticPointer(env);pointer.keyboard()
    public=Path(env['HOME'])/'.local/bin/wysun'
    def picker():
        for path in Path('/proc').iterdir():
            if not path.name.isdecimal():continue
            try:
                executable=(path/'exe').resolve()
                if executable.name in ('slurp','hyprpicker') and str(executable).startswith('/tmp/wysun-') and path.stat().st_uid==os.getuid():return True
            except (OSError,RuntimeError):pass
        return False
    try:
        reference=subprocess.check_output(['grim','-g','320,200 1x1','-t','ppm','-'],env=env)
        (run_dir/'color-reference.ppm').write_bytes(reference)
        process=start('public-pick-color',[public,'recorder','--pick-color'])
        wait_for(picker,'native slurp point selector');time.sleep(.3)
        pointer.click(320,200)
        wait_for(lambda:process.poll() is not None,'PickColor response')
        assert process.returncode==0,(run_dir/'public-pick-color.log').read_text()
        rgb=json.loads((run_dir/'public-pick-color.log').read_text())
        (run_dir/'color-pick-diagnostic.json').write_text(json.dumps(dict(reference_hex=reference[:64].hex(),reference_bytes=len(reference),selected_point=(run_dir/'selected-point.txt').read_text() if (run_dir/'selected-point.txt').exists() else 'native hyprpicker; own virtual click320,200',portal_rgb=rgb),indent=2))
        assert len(rgb)==3 and all(abs(actual*255-expected)<=2 for actual,expected in zip(rgb,[49,87,135])),rgb
        cancelled=start('public-pick-color-cancel',[public,'recorder','--pick-color'])
        wait_for(picker,'second native point selector');time.sleep(.3);pointer.press(1)
        wait_for(lambda:cancelled.poll() is not None,'PickColor cancellation')
        assert cancelled.returncode!=0,'Cancelled selection unexpectedly returned a color'
        result=dict(result='WYSUN_PUBLIC_PICK_COLOR_OK',command='installed wysun recorder --pick-color',
            backend='real Screenshot portal/hyprpicker' if 'hyprpicker' in command(['sh','-c','command -v hyprpicker || true']) else 'real Screenshot portal/slurp/grim',rgb=rgb,expected_rgb8=[49,87,135],cancelled=True,
            scope='own solid fixture and virtual input only; no physical screen or human consent claim')
        (run_dir/'native-color-results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2),flush=True)
        return result
    finally:pointer.close()
