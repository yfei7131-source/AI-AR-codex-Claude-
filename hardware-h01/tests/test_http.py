import json, threading, unittest
import base64, io
from PIL import Image
from unittest.mock import patch
from urllib.request import urlopen, Request
from http.server import ThreadingHTTPServer
from app.server import Handler

class HttpTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.port=cls.server.server_address[1]
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close()
    def get(self,path):
        with urlopen(f'http://127.0.0.1:{self.port}{path}') as r: return r.status,json.load(r)
    def post(self,path,payload):
        req=Request(f'http://127.0.0.1:{self.port}{path}',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
        with urlopen(req) as r:return r.status,json.load(r)
    def test_health(self):
        _,obj=self.get('/api/health');self.assertTrue(obj['ok'])
    def test_ask_hud(self):
        image=io.BytesIO();Image.new('RGB',(2,2),'white').save(image,format='PNG')
        data='data:image/png;base64,'+base64.b64encode(image.getvalue()).decode()
        with patch('app.server.PROVIDER', __import__('app.provider',fromlist=['DemoProvider']).DemoProvider()):
            _,obj=self.post('/api/ask',{'kind':'translate','question':'翻译这段文字','image_data':data,'consent':True,'mode':'demo'})
        self.assertEqual(obj['hud']['title'],'AR 翻译')
    def test_task_consent(self):
        _,o=self.post('/api/tasks/draft',{'text':'记录温度'})
        t=o['task'];self.assertEqual(t['status'],'awaiting_confirmation')
        _,c=self.post('/api/tasks/confirm',{'id':t['id']})
        self.assertEqual(c['task']['status'],'confirmed_local_only')
    def test_delete(self):
        self.post('/api/notes',{'text':'临时记录'})
        self.post('/api/privacy/delete',{})
        _,state=self.get('/api/state')
        self.assertEqual(state['notes'],[])

if __name__=='__main__': unittest.main()
