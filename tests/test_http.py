import json
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path
from atelier.server import Server
from atelier.service import Service
from atelier.store import Store


class HTTPBoundary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.service=Service(Store(Path(cls.temp.name)/'http.sqlite3'),mode='demo')
        cls.service.seed()
        cls.server=Server(('127.0.0.1',0),cls.service)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        cls.port=cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.temp.cleanup()

    def request(self,path,method='GET',body=None,headers=None):
        connection=HTTPConnection('127.0.0.1',self.port,timeout=5)
        connection.request(method,path,body,headers or {})
        response=connection.getresponse()
        result=(response.status,dict(response.getheaders()),response.read())
        connection.close()
        return result

    def token(self):
        return json.loads(self.request('/api/status')[2])['csrf']

    def test_health_and_static_pages_and_csp(self):
        for path in ['/', '/style.css','/app.js','/favicon.svg','/api/status','/api/cases','/api/progress']:
            status,headers,body=self.request(path)
            self.assertEqual(status,200,path)
            self.assertIn("script-src 'self'",headers['Content-Security-Policy'])
            self.assertNotIn('unsafe-inline',headers['Content-Security-Policy'])
        self.assertNotIn('GEMINI_API_KEY',self.request('/api/status')[2].decode())

    def test_host_origin_csrf_and_fetch_site_guards(self):
        self.assertEqual(self.request('/api/status',headers={'Host':'evil.example'})[0],403)
        self.assertEqual(self.request('/api/status',headers={'Origin':'https://evil.example'})[0],403)
        self.assertEqual(self.request('/api/status',headers={'Sec-Fetch-Site':'cross-site'})[0],403)
        self.assertEqual(self.request('/api/cases','POST','{}',{'Content-Type':'application/json'})[0],403)
        self.assertEqual(self.request('/api/cases','POST','{}',{'Content-Type':'application/json','X-Atelier-Token':self.token(),'Origin':'https://evil.example'})[0],403)

    def test_json_type_size_and_path_allowlist(self):
        headers={'Content-Type':'application/json','X-Atelier-Token':self.token()}
        self.assertEqual(self.request('/api/cases','POST','[]',headers)[0],400)
        self.assertEqual(self.request('/api/cases','POST','not json',headers)[0],400)
        self.assertEqual(self.request('/api/cases','POST','a'*131073,headers)[0],413)
        self.assertEqual(self.request('/.env')[0],404)
        self.assertEqual(self.request('/atelier/server.py')[0],404)
        self.assertEqual(self.request('/../.local/atelier.sqlite3')[0],404)

    def test_mutation_gate_bounds_concurrent_paid_work(self):
        self.server.gate.acquire()
        try:
            status,_,body=self.request('/api/cases','POST','{}',{'Content-Type':'application/json','X-Atelier-Token':self.token()})
            self.assertEqual(status,429)
            self.assertIn('처리',json.loads(body)['error'])
        finally:self.server.gate.release()

    def test_demo_custom_extraction_returns_explicit_configuration_error(self):
        data=json.dumps({'source':'test','domain':'test'})
        status,_,body=self.request('/api/cases','POST',data,{'Content-Type':'application/json','X-Atelier-Token':self.token()})
        self.assertEqual(status,503)
        self.assertIn('데모',json.loads(body)['error'])
