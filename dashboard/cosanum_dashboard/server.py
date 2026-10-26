"""Loopback-only HTTP transport; no account, remote execution or external requests."""
import hashlib
import json
import re
import secrets
import threading
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .experiments import bootstrap, validate, prepare, run_experiment, read


class Dashboard:
    def __init__(self, assets, output, root=None):
        self.assets=Path(assets);self.runtime=Path(root) if root is not None else self.assets.parent;self.output=Path(output)
        self.spec=bootstrap(self.runtime,self.assets)
        self.token=secrets.token_urlsafe(32)
        self.executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='Cosanum')
        self.lock=threading.Lock();self.jobs={};self.active=None
        # Finished experiments survive application restarts. Malformed folders are ignored.
        if self.output.exists():
            for p in self.output.glob('experiment-*/result.json'):
                identity=p.parent.name.removeprefix('experiment-')
                if re.fullmatch(r'[0-9a-f]{32}',identity):
                    try:
                        result=read(p)
                        self.jobs[identity]=dict(id=identity,status='complete',completed=len(result['rows']),
                             total=len(result['rows']),message='Gespeichertes lokales Experiment',settings=result['settings'])
                    except (ValueError,KeyError,OSError): pass

    def submit(self,payload):
        payload=validate(payload,self.spec)
        prepare(self.runtime,payload,self.spec,payload['seed'])
        with self.lock:
            if self.active: raise RuntimeError('Ein Experiment läuft bereits. Bitte dessen Abschluss abwarten.')
            identity=uuid.uuid4().hex
            self.jobs[identity]=dict(id=identity,status='running',completed=0,total=0,
                                     message='Eingaben geprüft',settings=payload)
            self.active=identity
        self.executor.submit(self._run,identity,payload)
        return self.status(identity)

    def folder(self,identity):
        if not re.fullmatch(r'[0-9a-f]{32}',identity): raise KeyError('Unbekanntes Experiment')
        return self.output/('experiment-'+identity)

    def _run(self,identity,payload):
        def progress(done,total,message):
            with self.lock:self.jobs[identity].update(completed=done,total=total,message=message)
        try:
            run_experiment(self.runtime,self.assets,self.folder(identity),payload,progress)
            with self.lock:self.jobs[identity].update(status='complete',message='Simulation und Prüfungen abgeschlossen')
        except Exception as error:
            # Keep partial output for diagnosis; do not show it as a completed statistical result.
            with self.lock:self.jobs[identity].update(status='failed',message=str(error))
        finally:
            with self.lock:self.active=None

    def status(self,identity):
        self.folder(identity)
        with self.lock:
            if identity not in self.jobs: raise KeyError('Unbekanntes Experiment')
            return dict(self.jobs[identity])

    def export(self,identity):
        if self.status(identity)['status']!='complete': raise RuntimeError('Experiment ist noch nicht abgeschlossen.')
        folder=self.folder(identity);target=folder/'experiment.zip'
        with self.lock:
            if not target.exists():
                with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED) as archive:
                    for p in sorted(folder.rglob('*')):
                        if p.is_file() and p!=target and not p.is_symlink():
                            archive.write(p,str(p.relative_to(folder)))
        return target

    def close(self):
        self.executor.shutdown(wait=True)


def make_server(app,port=0):
    class Handler(BaseHTTPRequestHandler):
        server_version='CosanumLocal/0.1'

        def log_message(self,*args): pass  # neither tokens nor request contents in logs

        def respond(self,status,content,kind='application/json; charset=utf-8',attachment=None):
            if isinstance(content,(dict,list)):content=json.dumps(content,ensure_ascii=False,allow_nan=False).encode('utf-8')
            if isinstance(content,str):content=content.encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(content)))
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Referrer-Policy','no-referrer')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            if attachment:self.send_header('Content-Disposition','attachment; filename="'+attachment+'"')
            self.end_headers();self.wfile.write(content)

        def allowed(self,api=False):
            expected=f'127.0.0.1:{self.server.server_port}'
            if self.headers.get('Host')!=expected:
                self.respond(403,{'error':'Unerwarteter lokaler Host.'});return False
            origin=self.headers.get('Origin')
            if origin and origin!='http://'+expected:
                self.respond(403,{'error':'Fremde Website nicht zugelassen.'});return False
            if api and not secrets.compare_digest(self.headers.get('X-Cosanum-Token',''),app.token):
                self.respond(403,{'error':'Bitte die App über den Launcher öffnen.'});return False
            return True

        def do_GET(self):
            path=urlsplit(self.path).path
            if not self.allowed(path.startswith('/api/')):return
            try:
                if path=='/api/bootstrap':return self.respond(200,app.spec)
                if path=='/api/library':return self.respond(200,(app.assets/'static/library.json').read_bytes())
                if path=='/api/experiments':
                    with app.lock:jobs=list(app.jobs.values())
                    return self.respond(200,jobs)
                match=re.fullmatch(r'/api/experiments/([0-9a-f]{32})(/result|/export)?',path)
                if match:
                    identity,suffix=match.groups();job=app.status(identity)
                    if not suffix:return self.respond(200,job)
                    if job['status']!='complete':raise RuntimeError('Ergebnis noch nicht verfügbar.')
                    if suffix=='/result':return self.respond(200,(app.folder(identity)/'result.json').read_bytes())
                    return self.respond(200,app.export(identity).read_bytes(),'application/zip','Cosanum-Experiment-'+identity[:8]+'.zip')
                files={'/':'index.html','/index.html':'index.html','/app.js':'app.js','/app.css':'app.css',
                       '/help.js':'help.js','/help.css':'help.css'}
                if path not in files:return self.respond(404,{'error':'Nicht gefunden.'})
                filename=files[path];kind={'html':'text/html','css':'text/css','js':'text/javascript'}[filename.rsplit('.',1)[1]]
                return self.respond(200,(app.assets/'static'/filename).read_bytes(),kind+'; charset=utf-8')
            except KeyError:return self.respond(404,{'error':'Unbekanntes Experiment.'})
            except (ValueError,RuntimeError) as error:return self.respond(409,{'error':str(error)})

        def do_POST(self):
            if not self.allowed(api=True):return
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=16384:return self.respond(413,{'error':'Eingabe zu gross oder leer.'})
                if self.headers.get('Content-Type','').split(';')[0]!='application/json':
                    return self.respond(415,{'error':'JSON erforderlich.'})
                body=json.loads(self.rfile.read(length))
                path=urlsplit(self.path).path
                if path=='/api/experiments':return self.respond(202,app.submit(body))
                if path=='/api/shutdown':
                    with app.lock:
                        if app.active:raise RuntimeError('Zuerst das laufende Experiment abschliessen lassen.')
                    self.respond(200,{'status':'closed'})
                    threading.Thread(target=self.server.shutdown,daemon=True).start();return
                self.respond(404,{'error':'Nicht gefunden.'})
            except (ValueError,TypeError) as error:self.respond(400,{'error':str(error)})
            except RuntimeError as error:self.respond(409,{'error':str(error)})

    return ThreadingHTTPServer(('127.0.0.1',port),Handler)
