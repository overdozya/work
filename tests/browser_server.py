"""Isolated browser-test state; never modifies the user's runtime database."""
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from atelier.server import ROOT, Server
from atelier.service import Service
from atelier.store import Store

ROOT.joinpath('.local').mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='browser-test-', dir=ROOT / '.local') as folder:
    service=Service(Store(Path(folder)/'browser.sqlite3'),mode='demo')
    service.seed()
    with Server(('127.0.0.1',0),service) as server:
        print(server.server_address[1],flush=True)
        server.serve_forever()
