def main():
    import argparse
    parser = argparse.ArgumentParser(prog='wysun recorder', description='Wysun Recorder · grabación y edición local')
    parser.add_argument('--version', action='version', version='Wysun Recorder 0.1.0')
    parser.add_argument('--quick-record', action='store_true', help='Open only the floating quick capture bar')
    parser.add_argument('--devices', action='store_true')
    parser.add_argument('--pick-color',action='store_true',help='Pick a color using the desktop portal; prints RGB JSON')
    parser.add_argument('--record', action='store_true', help='Open recording setup without starting capture')
    parser.add_argument('--recover', metavar='PROJECT_DIRECTORY')
    parser.add_argument('--audio-devices', action='store_true', help='Print microphones and cameras as JSON')
    parser.add_argument('--prefs', action='store_true', help='Print the shell recording defaults as JSON')
    parser.add_argument('--set-pref', nargs=2, metavar=('KEY','VALUE'))
    parser.add_argument('--show', metavar='VIDEO', help='Open Wysun Recorder on this video')
    parser.add_argument('--notify-when-ready', metavar='PROJECT_DIRECTORY')
    parser.add_argument('--start', metavar='JSON', help='Start recording without a window (used by the shell); prints the project folder')
    actions=parser.add_mutually_exclusive_group()
    for action in ['status','pause','resume','stop']:
        actions.add_argument('--'+action, metavar='PROJECT_DIRECTORY')
    args = parser.parse_args()
    if args.pick_color:
        import json
        from .portal import Portal
        portal=Portal()
        try:print(json.dumps(portal.pick_color()))
        finally:portal.close()
    elif args.devices:
        import json
        from .devices import discover
        print(json.dumps(discover(), indent=2))
    elif args.audio_devices:
        import json
        from .headless import devices
        print(json.dumps(devices()))
    elif args.prefs:
        import json
        from .headless import shell_prefs
        print(json.dumps(shell_prefs()))
    elif args.set_pref:
        from .headless import set_shell_pref
        set_shell_pref(*args.set_pref)
    elif args.show:
        from .headless import request_show
        request_show(args.show)
        from .ui import main as ui_main
        ui_main()
    elif args.notify_when_ready:
        from .headless import notify_when_ready
        notify_when_ready(args.notify_when_ready)
    elif args.quick_record or args.record:
        # Preparing a recording is the shell's job now: choose, then record.
        import os
        os.execvp('wysun-shell', ['wysun-shell', 'record', 'start'])
    elif args.start:
        import json
        from .headless import start
        try:print(json.dumps(start(json.loads(args.start))))
        except Exception as exc:
            print(json.dumps(dict(error=str(exc))));raise SystemExit(1)
    elif args.recover:
        from .capture import recover_project
        print(recover_project(args.recover))
    elif any(getattr(args,name) for name in ['status','pause','resume','stop']):
        import json
        from .capture import CaptureSession
        name=next(name for name in ['status','pause','resume','stop'] if getattr(args,name))
        session=CaptureSession.attach(getattr(args,name))
        if name!='status':getattr(session,name)()
        print(json.dumps(session.status(),indent=2))
    else:
        if args.quick_record:
            import os
            os.environ['LOOMREC_QUICK_RECORD']='1'
        if args.record:
            import os
            os.environ['LOOMREC_START_RECORDING']='1'
        from .ui import main as ui_main
        ui_main()

if __name__ == '__main__':
    main()
