"""Real local TLS transport tests; synthetic images, no vendor/phone/CA install."""
import io
import json
from pathlib import Path
import ssl
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib import request, error
from unittest.mock import patch
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from app.dev_tls import ensure_tls, private_ipv4
from app.phone_gateway import Gateway, ca_bootstrap, ROOT


class LocalBackend(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass
    def do_GET(self):
        if self.path == "/api/redirect":
            self.send_response(302)
            self.send_header("Location", "https://example.com/")
            self.end_headers()
            return
        self.reply({"ok":True,"path":self.path,"host":self.headers.get("Host"),"origin":self.headers.get("Origin"),"auth":self.headers.get("Authorization")})
    def do_POST(self):
        body=json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.reply({"received":body,"origin":self.headers.get("Origin"),"auth":self.headers.get("Authorization")})
    def reply(self, body):
        raw=json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


class GatewayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.root=Path(cls.temp.name)
        (cls.root/'web').mkdir()
        (cls.root/'web/index.html').write_text('<html>Flutter test shell</html>',encoding='utf-8')
        (cls.root/'web/main.dart.js').write_text('console.log("test")',encoding='utf-8')
        (cls.root/'private.txt').write_text('must not serve',encoding='utf-8')
        cls.tls=ensure_tls(cls.root/'tls','127.0.0.1')
        cls.backend=ThreadingHTTPServer(('127.0.0.1',0),LocalBackend)
        threading.Thread(target=cls.backend.serve_forever,daemon=True).start()
        cls.gateway=Gateway(('127.0.0.1',0),upstream=f'http://127.0.0.1:{cls.backend.server_port}',web_root=cls.root/'web',token='unit-test-session')
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version=ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(cls.tls['cert'],cls.tls['key'])
        cls.gateway.socket=context.wrap_socket(cls.gateway.socket,server_side=True)
        threading.Thread(target=cls.gateway.serve_forever,daemon=True).start()
        cls.base='https://127.0.0.1:'+str(cls.gateway.server_port)
        cls.client=request.build_opener(request.ProxyHandler({}),request.HTTPSHandler(context=ssl.create_default_context(cafile=cls.tls['ca'])))
    @classmethod
    def tearDownClass(cls):
        cls.gateway.shutdown();cls.gateway.server_close()
        cls.backend.shutdown();cls.backend.server_close();cls.temp.cleanup()
    def setUp(self):
        self.gateway.deadline=time.monotonic()+60
    def call(self,path='/',body=None,headers=None,raw=None):
        request_headers=headers or {}
        if body is not None:
            request_headers={'Content-Type':'application/json',**request_headers}
            raw=json.dumps(body).encode()
        req=request.Request(self.base+path,data=raw,headers=request_headers)
        try:
            with self.client.open(req,timeout=3) as response:return response.status,response.headers,response.read()
        except error.HTTPError as exc:
            with exc:return exc.code,exc.headers,exc.read()
    def auth(self,**extra):
        return {'Authorization':'Bearer unit-test-session',**extra}
    def test_real_tls_static_and_public_health(self):
        code,headers,data=self.call()
        self.assertEqual(code,200);self.assertIn(b'Flutter test shell',data)
        self.assertEqual(headers['Permissions-Policy'],'camera=(self), microphone=(self), geolocation=()')
        self.assertEqual(self.call('/gateway/health')[0],200)
        self.assertNotIn(b'unit-test-session',self.call('/gateway/health')[2])
    def test_token_required_wrong_and_expired(self):
        self.assertEqual(self.call('/api/health')[0],401)
        self.assertEqual(self.call('/api/health',headers={'Authorization':'Bearer wrong'})[0],401)
        self.gateway.deadline=time.monotonic()-1
        self.assertEqual(self.call('/api/health',headers=self.auth())[0],401)
    def test_authorized_forwarding_never_leaks_bearer_or_origin(self):
        code,_,raw=self.call('/api/health',headers=self.auth(Origin=self.base))
        value=json.loads(raw)
        self.assertEqual(code,200);self.assertIsNone(value['auth']);self.assertIsNone(value['origin'])
        self.assertEqual(value['host'],f'127.0.0.1:{self.backend.server_port}')
        code,_,raw=self.call('/api/media/validate',body={'consent':True,'image_data':'synthetic fixture'},headers=self.auth())
        self.assertEqual(code,200);self.assertTrue(json.loads(raw)['received']['consent'])
    def test_origin_and_host_rebinding_rejected(self):
        self.assertEqual(self.call('/api/health',headers=self.auth(Origin='https://evil.example'))[0],403)
        self.assertEqual(self.call('/api/health',headers=self.auth(Host='evil.example:9443'))[0],403)
        self.assertEqual(self.call('/api/health',headers=self.auth(**{'Sec-Fetch-Site':'cross-site'}))[0],403)
    def test_path_traversal_and_hidden_files_not_served(self):
        for path in ('/../private.txt','/%2e%2e/private.txt','/.env','/%5c..%5cprivate.txt',
                     '/server-key.pem%20','/server-key.pem.','/main.dart.js::$DATA'):
            self.assertEqual(self.call(path)[0],404)
        self.assertIn('text/javascript',self.call('/main.dart.js')[1]['Content-Type'])
    def test_private_roots_cannot_be_used_as_static_or_parent_directory(self):
        for web_root in (ROOT, ROOT/'artifacts', ROOT/'artifacts/private', ROOT/'artifacts/private/iphone'):
            with self.assertRaises(ValueError):
                Gateway(('127.0.0.1',0),upstream=f'http://127.0.0.1:{self.backend.server_port}',web_root=web_root)
        # Explicit protected roots also apply to embedders using a different directory.
        with self.assertRaises(ValueError):
            Gateway(('127.0.0.1',0),upstream=f'http://127.0.0.1:{self.backend.server_port}',web_root=self.root,protected_roots=(self.root/'tls',))
    def test_second_gateway_cannot_share_live_pairing_port(self):
        with self.assertRaises(OSError):
            Gateway(('127.0.0.1',self.gateway.server_port),upstream=f'http://127.0.0.1:{self.backend.server_port}',web_root=self.root/'web')
    def test_json_type_body_limit_and_no_redirect(self):
        self.assertEqual(self.call('/api/ask',raw=b'x',headers=self.auth(**{'Content-Type':'text/plain'}))[0],415)
        self.assertEqual(self.call('/api/ask',raw=b'x',headers=self.auth(**{'Content-Type':'application/json','Content-Length':str(4*1024*1024)}))[0],413)
        code,_,_=self.call('/api/redirect',headers=self.auth())
        self.assertEqual(code,502) # redirect response is not a valid JSON backend
    def test_public_ca_bootstrap_serves_only_certificate(self):
        ca=Path(self.tls['ca_der']).read_bytes()
        http=ca_bootstrap(('127.0.0.1',0),ca)
        threading.Thread(target=http.serve_forever,daemon=True).start()
        opener=request.build_opener(request.ProxyHandler({}))
        try:
            with opener.open(f'http://127.0.0.1:{http.server_port}/ca.cer') as response:self.assertEqual(response.read(),ca)
            with self.assertRaises(error.HTTPError) as denied:opener.open(f'http://127.0.0.1:{http.server_port}/server-key.pem')
            denied.exception.close()
        finally:http.shutdown();http.server_close()
    def test_upstream_only_loopback_and_bounded_session(self):
        for upstream in ('https://example.com','http://localhost:8765','http://127.0.0.1:8765/path','http://name:secret@127.0.0.1:8765'):
            with self.assertRaises(ValueError):Gateway(('127.0.0.1',0),upstream=upstream,web_root=self.root)


class TlsPreparationTest(unittest.TestCase):
    def test_certificate_san_lifetimes_reuse_and_no_trust_install(self):
        with tempfile.TemporaryDirectory() as root:
            first=ensure_tls(root,'192.168.1.20');second=ensure_tls(root,'192.168.1.20')
            self.assertEqual(first['ca_sha256'],second['ca_sha256'])
            self.assertFalse(first['trust_store_modified'])
            cert=x509.load_pem_x509_certificate(Path(first['cert']).read_bytes())
            ca=x509.load_der_x509_certificate(Path(first['ca_der']).read_bytes())
            self.assertEqual(ca.fingerprint(hashes.SHA256()).hex(),first['ca_sha256'])
            self.assertLessEqual((cert.not_valid_after_utc-cert.not_valid_before_utc).days,31)
            with self.assertRaises(ValueError):ensure_tls(root,'192.168.1.21')
    def test_reject_public_unspecified_and_partial_keys(self):
        for host in ('8.8.8.8','0.0.0.0','224.0.0.1','::1'):
            with self.assertRaises(ValueError):private_ipv4(host)
        with tempfile.TemporaryDirectory() as root:
            Path(root,'ca.pem').write_text('not a certificate')
            with self.assertRaises(ValueError):ensure_tls(root,'127.0.0.1')
