def main():
    import argparse
    parser = argparse.ArgumentParser(prog='wysun recorder', description='Wysun Recorder · grabación y edición local')
    parser.add_argument('--version', action='version', version='Wysun Recorder 0.1.0')
    parser.add_argument('--quick-record', action='store_true', help='Open only the floating quick capture bar')
    parser.add_argument('--devices', action='store_true')
    parser.add_argument('--pick-color',action='store_true',help='Pick a color using the desktop portal; prints RGB JSON')
    parser.add_argument('--record', action='store_true', help='Open recording setup without starting capture')
    parser.add_argument('--recover', metavar='PROJECT_DIRECTORY')
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
