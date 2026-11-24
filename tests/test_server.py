import unittest, tempfile, threading, json, http.cookiejar
from pathlib import Path
from unittest.mock import patch
from urllib.request import build_opener, HTTPCookieProcessor, Request
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
import server

class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(); cls.old=server.DB_PATH
        server.DB_PATH=Path(cls.tmp.name)/'test.sqlite'; server.initialize()
        cls.http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        cls.base='http://127.0.0.1:'+str(cls.http.server_port)
        cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True); cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown(); cls.http.server_close(); cls.thread.join(); server.DB_PATH=cls.old; cls.tmp.cleanup()
    def client(self): return build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def call(self,c,path,method='GET',data=None,expected=200):
        req=Request(self.base+path, data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json'},method=method)
        try: r=c.open(req,timeout=4)
        except HTTPError as e: r=e
        with r:
            self.assertEqual(r.code,expected,(path,r.code)); body=r.read()
            return json.loads(body) if 'application/json' in r.headers.get('Content-Type','') else body
    def test_demo_and_pos(self):
        b,s=self.client(),self.client()
        self.call(b,'/api/orders',expected=401)
        self.assertIn(b'Laundry',self.call(b,'/'))
        self.call(b,'/.env',expected=404)
        self.call(b,'/api/auth/demo','POST',{'role':'buyer'})
        self.call(s,'/api/auth/demo','POST',{'role':'seller'})
        shop=self.call(b,'/api/shops')['shops'][0]
        self.call(b,'/api/seller/pos-data',expected=403)
        order=self.call(b,'/api/orders','POST',dict(shopId=shop['id'],serviceId='kiloan',speedId='kilat',weight=2),201)['order']
        self.assertEqual(order['total'],17500)
        self.assertIn(order['id'],[o['id'] for o in self.call(s,'/api/orders')['orders']])
        self.call(b,f"/api/orders/{order['id']}",'PATCH',{'status':'Selesai'},403)
        self.call(s,f"/api/orders/{order['id']}",'PATCH',{'status':'Diproses'})
        self.call(s,'/api/seller/shop','PATCH',dict(name='Laundry Demo Baru',services=server.SERVICE))
        self.call(s,'/api/seller/pos-customers','POST',dict(id=100,name='Tes',phone='08123'))
        self.call(s,'/api/seller/pos-orders','POST',dict(order_number='LDY-TEST-100',customer_id=100,customer_name='Tes',service_id='kiloan',speed_id='reguler',weight=1,total=7000),201)
        self.call(s,'/api/seller/pos-orders/LDY-TEST-100','PATCH',dict(status='Selesai',paid_amount=7000,payment_status='Lunas'))
        pos=self.call(s,'/api/seller/pos-data'); self.assertEqual(pos['customers'][0]['name'],'Tes'); self.assertTrue(any(o['status']=='Selesai' for o in pos['orders']))
        self.assertIn(b'Laundry',self.call(s,'/kasir.html'))
        self.call(b,'/api/auth/logout','POST',{}); self.assertIsNone(self.call(b,'/api/session')['user'])
    def test_firebase_simulation(self):
        c=self.client(); calls=[]
        def fake(action,payload):
            calls.append((action,payload)); return {'localId':'uid-test'} if action!='sendOobCode' else {'email':payload['email']}
        with patch.object(server,'firebase',side_effect=fake):
            u=self.call(c,'/api/auth/register','POST',dict(name='User Test',email='test@example.com',password='password123',role='seller',shopName='Toko Test'),201)['user']; self.assertFalse(u['demo'])
            self.assertTrue(all(s['name']!='Laundry Demo Baru' for s in self.call(c,'/api/shops')['shops']))
            self.call(c,'/api/auth/logout','POST',{})
            self.call(c,'/api/auth/forgot','POST',{'email':'test@example.com'})
            self.assertEqual(calls[-1],('sendOobCode',{'requestType':'PASSWORD_RESET','email':'test@example.com'}))
            self.call(c,'/api/auth/login','POST',dict(email='test@example.com',password='newpassword123'))
            self.assertEqual(self.call(c,'/api/session')['user']['id'],u['id'])
        db=server.connect(); self.assertEqual(db.execute('SELECT password_hash FROM users WHERE id=?',(u['id'],)).fetchone()[0],'FIREBASE_ONLY'); db.close()
if __name__=='__main__': unittest.main()
