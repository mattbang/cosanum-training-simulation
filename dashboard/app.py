"""Launch the local dashboard against this repository's canonical engine."""
import argparse
import json
import sys
import webbrowser
from pathlib import Path

ASSETS=Path(__file__).resolve().parent
ROOT=ASSETS.parent
sys.path.insert(0,str(ROOT/'src'))
from cosanum_dashboard.server import Dashboard, make_server


def main():
    parser=argparse.ArgumentParser(description='Cosanum Simulation: lokales Dashboard')
    parser.add_argument('--no-browser',action='store_true')
    parser.add_argument('--port',type=int,default=0)
    parser.add_argument('--output',type=Path,default=ROOT/'local-experiments')
    parser.add_argument('--self-test',action='store_true',help='Check packaged resources without opening a port')
    args=parser.parse_args()
    from cosanum_sim.inputs import verify_sources,sha
    from cosanum_dashboard.experiments import read
    expected=read(ROOT/'HANDOVER_MANIFEST.json')
    for item in expected['files']:
        p=ROOT/item['path']
        if sha(p)!=item['sha256']:raise ValueError('Veränderte Paketdatei: '+item['path'])
    verify_sources(ROOT)
    library_manifest=read(ASSETS/'static/library-manifest.json')
    if sha(ASSETS/'static/library.json')!=library_manifest['library_sha256']:
        raise ValueError('Veränderte Ergebnisbibliothek.')
    app=Dashboard(ASSETS,args.output,root=ROOT)
    if args.self_test:
        print(json.dumps(dict(status='passed',engine_version=app.spec['engine_version'],
                             dashboard_version=app.spec['dashboard_version'],defaults=app.spec['defaults'])))
        app.close();return 0
    server=make_server(app,args.port)
    url=f'http://127.0.0.1:{server.server_port}/#token={app.token}'
    print('Cosanum Simulation läuft lokal. Ergebnisse: '+str(args.output),flush=True)
    if args.no_browser:print(url,flush=True)
    else:webbrowser.open(url)
    try:server.serve_forever(poll_interval=.3)
    except KeyboardInterrupt:pass
    finally:server.server_close();app.close()
    return 0


if __name__=='__main__':
    sys.exit(main())
