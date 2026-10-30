"""Read-only local/CAI preview. Bind loopback; consume an explicit telemetry file."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def snapshot(path):
    if path and path.exists():
        data=json.loads(path.read_text())
        return data
    return {'mode':'Not connected','status':'Prepared · training not started','stage':'Dataset prepared',
            'step':None,'total_steps':None,'gpu':None,'accuracy':None,'loss':[],
            'message':'Connect a timestamped training telemetry file to show live progress.',
            'events':['Recipe prepared: LoRA SFT → GRPO → comparison','Cluster readiness has not been checked in this session.']}

def main():
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=int(os.getenv('CDSW_APP_PORT','8096')))
    p.add_argument('--state',type=Path);a=p.parse_args()
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path in ['/', '/index.html']:
                payload=(ROOT/'docs/training-demo/dashboard.html').read_bytes();kind='text/html'
            elif self.path=='/api/status':
                try: payload=json.dumps(snapshot(a.state)).encode()
                except (ValueError,OSError):
                    self.send_error(503,'Telemetry unavailable');return
                kind='application/json'
            else:
                self.send_error(404);return
            self.send_response(200);self.send_header('Content-Type',kind+'; charset=utf-8')
            self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(payload)
        def log_message(self,*args): pass
    print(f'Monitor: http://127.0.0.1:{a.port}',flush=True)
    ThreadingHTTPServer(('127.0.0.1',a.port),Handler).serve_forever()
if __name__=='__main__':main()
