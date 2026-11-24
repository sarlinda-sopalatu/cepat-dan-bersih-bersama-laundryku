"""Laundry Kilat: server lokal Python 3.10+ (tanpa pip / framework).
Jalankan: python server.py. Firebase REST untuk autentikasi, SQLite untuk data laundry.
"""
import os, re, json, sqlite3, secrets, hashlib, math, time, threading, mimetypes
from pathlib import Path
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie
from urllib.parse import urlsplit, unquote, urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parent
for line in (ROOT / '.env').read_text(encoding='utf-8-sig').splitlines() if (ROOT / '.env').exists() else []:
    m = re.match(r'^\s*([A-Z][A-Z0-9_]*)\s*=\s*(.*)$', line)
    if m: os.environ.setdefault(m[1], m[2].strip().strip('\"\''))
PORT = int(os.getenv('PORT', '8090'))
HOST = os.getenv('HOST', '127.0.0.1')
APP_URL = os.getenv('APP_URL', f'http://localhost:{PORT}').rstrip('/')
KEY = os.getenv('FIREBASE_API_KEY', '').strip()
READY = bool(KEY and 'ISI_' not in KEY)
DATA = ROOT / 'data'
DATA.mkdir(exist_ok=True)
DB_PATH = DATA / 'laundry.sqlite'
DEMO = {'buyer':'pembeli@demo.laundry.invalid', 'seller':'toko@demo.laundry.invalid'}
SERVICE = dict(kiloan=7000, satuan=15000, dry_clean=25000, cuci_setrika=10000, setrika_saja=6000)
ITEM = dict(karpet=50000, selimut=30000, gaun=35000, sepatu=25000, helm=20000, jas=40000, bed_cover=45000, tas=20000)
SPEED = dict(reguler=1, kilat=1.25, express=1.5)
TRANSITIONS = {'Menunggu Konfirmasi':['Diproses','Dibatalkan'], 'Diproses':['Selesai','Dibatalkan'], 'Selesai':['Diambil'], 'Diambil':[], 'Dibatalkan':[]}
COOKIE = 'laundry_session'

class ApiError(Exception):
    def __init__(self, status, message, firebase_code=None):
        super().__init__(message)
        self.status, self.firebase_code = status, firebase_code

def fail(status, message):
    raise ApiError(status, message)

def connect():
    db = sqlite3.connect(DB_PATH, timeout=10, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    return db

def initialize():
    db = connect()
    try:
        db.executescript((ROOT / 'schema.sql').read_text(encoding='utf-8'))
        if 'firebase_uid' not in [r['name'] for r in db.execute('PRAGMA table_info(users)')]:
            db.execute('ALTER TABLE users ADD COLUMN firebase_uid TEXT')
        db.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_firebase_uid ON users(firebase_uid)')
        db.execute("DELETE FROM sessions WHERE user_id IN (SELECT id FROM users WHERE firebase_uid IS NULL AND email NOT LIKE '%@demo.laundry.invalid')")
    finally: db.close()

def clean(value, limit=120): return str(value if value is not None else '').strip()[:limit]
def valid_email(s): return len(s)<=254 and bool(re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',s))
def number(v, default=float('nan')):
    try:
        n=float(v)
        return n if math.isfinite(n) else default
    except (TypeError,ValueError,OverflowError): return default

def price(v): return math.floor(number(v,0)+0.5)
def digest(s): return hashlib.sha256(s.encode()).hexdigest()
def now_ms(): return int(time.time()*1000)
def demo(u): return bool(u and u['email'] in DEMO.values())
def public_user(u): return {**{k:u[k] for k in ('id','name','email','role','phone')}, 'demo':demo(u)} if u else None
def public_shop(s):
    s=dict(s); s['services']=json.loads(s.pop('services_json')); return s

def dates(speed):
    now=datetime.now(); dt=now+timedelta(hours={'reguler':72,'kilat':24,'express':6}[speed])
    return now.date().isoformat(),dt.date().isoformat(),dt.strftime('%H:%M') if speed=='express' else '14:00'

def ref_number(shop): return f'LDY-{datetime.now():%y%m%d}-{shop}-{secrets.token_hex(3).upper()}'
def cookie(token, age): return f'{COOKIE}={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={age}' + ('; Secure' if APP_URL.startswith('https:') else '')

# Batasi percobaan login/reset pada server lokal.
rate_map={}; rate_lock=threading.Lock(); profile_lock=threading.Lock()
def rate(key, limit, seconds):
    with rate_lock:
        now=time.monotonic(); recent=[t for t in rate_map.get(key,[]) if t>now-seconds]
        if len(recent)>=limit: fail(429,'Terlalu banyak percobaan. Coba lagi nanti.')
        rate_map[key]=recent+[now]
        if len(rate_map)>4000:
            for k in list(rate_map):
                if rate_map[k][-1]<now-900: del rate_map[k]

# Firebase mengelola password dan mengirim tautan reset, bukan server SMTP lokal.
def firebase(action, payload):
    if not READY: fail(503,'Firebase belum dikonfigurasi. Isi FIREBASE_API_KEY pada .env lalu restart server.')
    req=Request('https://identitytoolkit.googleapis.com/v1/accounts:'+action+'?'+urlencode({'key':KEY}), data=json.dumps(payload).encode(), headers={'Content-Type':'application/json','X-Firebase-Locale':'id'}, method='POST')
    try:
        with urlopen(req, timeout=15) as res: return json.load(res)
    except HTTPError as e:
        try: code=json.load(e).get('error',{}).get('message','UNKNOWN').split(' : ')[0]
        except (ValueError,AttributeError): code='UNKNOWN'
        messages={'EMAIL_EXISTS':'Email sudah terdaftar.','INVALID_LOGIN_CREDENTIALS':'Email atau kata sandi salah.','INVALID_PASSWORD':'Email atau kata sandi salah.','EMAIL_NOT_FOUND':'Email atau kata sandi salah.','USER_DISABLED':'Akun dinonaktifkan.','WEAK_PASSWORD':'Kata sandi tidak memenuhi kebijakan Firebase.','OPERATION_NOT_ALLOWED':'Aktifkan Email/Password di Firebase Authentication.','TOO_MANY_ATTEMPTS_TRY_LATER':'Terlalu banyak percobaan. Coba lagi nanti.','INVALID_EMAIL':'Email tidak valid.','API_KEY_INVALID':'API key Firebase salah.'}
        status=409 if code=='EMAIL_EXISTS' else 401 if code in ('INVALID_LOGIN_CREDENTIALS','INVALID_PASSWORD','EMAIL_NOT_FOUND','USER_DISABLED') else 429 if code=='TOO_MANY_ATTEMPTS_TRY_LATER' else 400
        raise ApiError(status,messages.get(code,'Firebase menolak permintaan. Periksa konfigurasi Authentication dan API key.'),code) from None
    except (URLError,TimeoutError,OSError,ValueError): fail(503,'Tidak dapat terhubung ke Firebase. Periksa internet dan coba lagi.')

class Handler(BaseHTTPRequestHandler):
    def q(self, sql, *args): return self.db.execute(sql,args)
    def one(self, sql, *args):
        r=self.q(sql,*args).fetchone(); return dict(r) if r is not None else None
    def all(self, sql, *args): return [dict(r) for r in self.q(sql,*args)]
    def respond(self, status, data, content_type='application/json; charset=utf-8', extra=None):
        if not isinstance(data,bytes): data=json.dumps(data,ensure_ascii=False,allow_nan=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Frame-Options','DENY')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'")
        for k,v in (extra or {}).items(): self.send_header(k,v)
        self.end_headers()
        if self.command!='HEAD': self.wfile.write(data)
    def body(self):
        try: size=int(self.headers.get('Content-Length','0'))
        except ValueError: fail(400,'Format data tidak valid.')
        if size<0 or size>5*1024*1024: fail(413,'Data terlalu besar (maksimal 5 MB).')
        try: b=json.loads(self.rfile.read(size) or b'{}')
        except (ValueError,UnicodeError): fail(400,'Format data tidak valid.')
        if not isinstance(b,dict): fail(400,'Format data tidak valid.')
        return b
    def token(self):
        try:
            c=SimpleCookie(self.headers.get('Cookie','')); token=c[COOKIE].value if COOKIE in c else ''
            return token if re.fullmatch(r'[a-f0-9]{64}',token) else ''
        except Exception: return ''
    def session_user(self):
        token=self.token()
        return self.one('SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>?',digest(token),now_ms()) if token else None
    def require(self, role=None):
        u=self.session_user()
        if not u: fail(401,'Silakan masuk ke akun terlebih dahulu.')
        if role and role!=u['role']: fail(403,'Akun ini tidak memiliki izin mengakses fitur tersebut.')
        return u
    def own_shop(self):
        u=self.require('seller'); s=self.one('SELECT * FROM shops WHERE owner_id=?',u['id'])
        if not s: fail(404,'Toko tidak ditemukan.')
        return s
    def login_response(self,u,status=200):
        token=secrets.token_hex(32)
        self.q('DELETE FROM sessions WHERE expires_at<=?',now_ms())
        old=self.token()
        if old: self.q('DELETE FROM sessions WHERE token_hash=?',digest(old))
        self.q('INSERT INTO sessions (token_hash,user_id,expires_at) VALUES (?,?,?)',digest(token),u['id'],now_ms()+3600000)
        return self.respond(status,{'user':public_user(u)},extra={'Set-Cookie':cookie(token,3600)})
    def create_profile(self,b,email,uid=None):
        self.q('BEGIN IMMEDIATE')
        try:
            user_id=self.q('INSERT INTO users (name,email,password_hash,role,phone,firebase_uid) VALUES (?,?,?,?,?,?)',clean(b.get('name'),80),email,'FIREBASE_ONLY',b['role'],clean(b.get('phone'),25),uid).lastrowid
            if b['role']=='seller': self.q('INSERT INTO shops (owner_id,name,city,address,phone,description,services_json) VALUES (?,?,?,?,?,?,?)',user_id,clean(b.get('shopName'),90),clean(b.get('city'),70),clean(b.get('address'),200),clean(b.get('phone'),25),'Melayani cucian Anda dengan sepenuh hati.',json.dumps(SERVICE))
            self.q('COMMIT')
        except Exception:
            self.q('ROLLBACK'); raise
        return self.one('SELECT * FROM users WHERE id=?',user_id)
    def demo_user(self,role):
        with profile_lock:
            return self.one('SELECT * FROM users WHERE email=?',DEMO[role]) or self.create_profile(dict(role=role,name='Pembeli Demo' if role=='buyer' else 'Pemilik Toko Demo',shopName='Laundry Ungu Demo',city='Makassar',address='Alamat simulasi'),DEMO[role])
    def visible(self,u,s):
        owner=self.one('SELECT email FROM users WHERE id=?',s['owner_id'])
        return bool(owner and demo(u)==demo(owner))
    def api(self,route):
        method=self.command; ip=self.client_address[0]
        if method=='GET' and route=='/api/config': return self.respond(200,{'firebase_ready':READY})
        if method=='GET' and route=='/api/session': return self.respond(200,{'user':public_user(self.session_user())})
        if method=='POST' and route=='/api/auth/demo':
            rate(('demo',ip),30,60); role=self.body().get('role')
            if role not in ('buyer','seller'): fail(400,'Pilih jenis akun demo.')
            self.demo_user('seller'); return self.login_response(self.demo_user(role))
        if method=='POST' and route=='/api/auth/register':
            rate(('register',ip),12,900); b=self.body(); name=clean(b.get('name'),80); email=clean(b.get('email'),254).lower(); password=b.get('password'); role=b.get('role')
            if len(name)<2 or not valid_email(email) or email.endswith('.invalid') or not isinstance(password,str) or not 8<=len(password)<=128 or role not in ('buyer','seller'): fail(400,'Periksa nama, email aktif, kata sandi minimal 8 karakter, dan jenis akun.')
            if role=='seller' and len(clean(b.get('shopName'),90))<3: fail(400,'Nama toko minimal 3 karakter.')
            if self.one('SELECT id FROM users WHERE email=?',email): fail(409,'Email sudah terdaftar di database lokal. Silakan masuk.')
            payload=dict(email=email,password=password,returnSecureToken=True)
            try: account=firebase('signUp',payload)
            except ApiError as e:
                if e.firebase_code!='EMAIL_EXISTS': raise
                account=firebase('signInWithPassword',payload)
            if not account.get('localId'): fail(502,'Firebase tidak mengembalikan identitas akun.')
            return self.login_response(self.create_profile(b,email,account['localId']),201)
        if method=='POST' and route=='/api/auth/login':
            rate(('login',ip),15,600); b=self.body(); email=clean(b.get('email'),254).lower(); password=b.get('password')
            if not valid_email(email) or email.endswith('.invalid') or not isinstance(password,str) or not 1<=len(password)<=128: fail(400,'Masukkan email dan kata sandi yang valid.')
            account=firebase('signInWithPassword',dict(email=email,password=password,returnSecureToken=True))
            u=self.one('SELECT * FROM users WHERE firebase_uid=?',account.get('localId',''))
            if not u or demo(u): fail(409,'Profil lokal belum tersedia. Gunakan Daftar akun dengan email dan kata sandi Firebase yang sama.')
            return self.login_response(u)
        if method=='POST' and route=='/api/auth/logout':
            if self.token(): self.q('DELETE FROM sessions WHERE token_hash=?',digest(self.token()))
            return self.respond(200,{'ok':True},extra={'Set-Cookie':cookie('',0)})
        if method=='POST' and route=='/api/auth/forgot':
            rate(('forgot',ip),4,600); email=clean(self.body().get('email'),254).lower()
            if not valid_email(email) or email.endswith('.invalid'): fail(400,'Gunakan email asli yang valid. Akun demo tidak memerlukan reset.')
            try: firebase('sendOobCode',dict(requestType='PASSWORD_RESET',email=email))
            except ApiError as e:
                if e.firebase_code!='EMAIL_NOT_FOUND': raise
            return self.respond(200,{'message':'Jika email terdaftar, Firebase mengirim tautan reset. Periksa Inbox dan Spam, lalu buka tautannya.'})
        if method=='GET' and route=='/api/shops':
            u=self.require(); rows=self.all('SELECT s.*,u.name AS owner_name FROM shops s JOIN users u ON s.owner_id=u.id ORDER BY s.id DESC')
            return self.respond(200,{'shops':[public_shop(s) for s in rows if self.visible(u,s)]})
        if method=='GET' and re.fullmatch(r'/api/shops/\d+',route):
            u=self.require(); s=self.one('SELECT * FROM shops WHERE id=?',int(route.split('/')[-1]))
            if not s or not self.visible(u,s): fail(404,'Toko tidak ditemukan.')
            return self.respond(200,{'shop':public_shop(s)})
        if method=='GET' and route=='/api/orders':
            u=self.require(); col='o.buyer_id' if u['role']=='buyer' else 's.owner_id'
            return self.respond(200,{'orders':self.all(f'SELECT o.*,s.name AS shop_name FROM orders o JOIN shops s ON o.shop_id=s.id WHERE {col}=? ORDER BY o.id DESC',u['id'])})
        if method=='POST' and route=='/api/orders':
            u=self.require('buyer'); b=self.body(); shop=self.one('SELECT * FROM shops WHERE id=?',number(b.get('shopId'),-1))
            if not shop or not self.visible(u,shop): fail(404,'Toko tidak ditemukan.')
            service,speed,item=[clean(b.get(k),30) for k in ('serviceId','speedId','itemId')]
            if service not in SERVICE or speed not in SPEED: fail(400,'Layanan atau kecepatan tidak valid.')
            is_weight=service in ('kiloan','cuci_setrika','setrika_saja'); amount=number(b.get('weight' if is_weight else 'quantity'))
            if not 0<amount<=1000 or (not is_weight and not amount.is_integer()): fail(400,'Isi berat atau jumlah cucian yang valid.')
            if item and item not in ITEM: fail(400,'Jenis barang tidak tersedia.')
            base=ITEM[item] if not is_weight and item else price(json.loads(shop['services_json']).get(service))
            if base<1: fail(400,'Tarif layanan belum diatur oleh toko.')
            total=price(base*amount*SPEED[speed]); entry,estimated,est_time=dates(speed)
            id=self.q('''INSERT INTO orders (shop_id,buyer_id,order_number,customer_name,customer_phone,customer_address,needs_pickup,service_id,speed_id,item_id,weight,quantity,notes,subtotal,total,entry_date,estimated_date,estimated_time,status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',shop['id'],u['id'],ref_number(shop['id']),u['name'],clean(b.get('phone') or u['phone'],25),clean(b.get('address'),200),int(bool(b.get('pickup'))),service,speed,item or None,amount if is_weight else 0,0 if is_weight else amount,clean(b.get('notes'),600),total,total,entry,estimated,est_time,'Menunggu Konfirmasi').lastrowid
            return self.respond(201,{'order':self.one('SELECT * FROM orders WHERE id=?',id)})
        if method=='PATCH' and re.fullmatch(r'/api/orders/\d+',route):
            u=self.require(); id=int(route.split('/')[-1]); b=self.body(); o=self.one('SELECT * FROM orders WHERE id=?',id)
            if not o: fail(404,'Pesanan tidak ditemukan.')
            if u['role']=='seller':
                if o['shop_id']!=self.own_shop()['id']: fail(403,'Pesanan bukan milik toko Anda.')
            elif o['buyer_id']!=u['id']: fail(403,'Pesanan bukan milik akun Anda.')
            status=clean(b.get('status'),30)
            if status not in TRANSITIONS: fail(400,'Status pesanan tidak valid.')
            if u['role']=='buyer' and (status!='Dibatalkan' or o['status']!='Menunggu Konfirmasi'): fail(403,'Pembeli hanya dapat membatalkan pesanan yang belum dikonfirmasi.')
            if status not in TRANSITIONS.get(o['status'],[]): fail(400,'Perubahan status tidak diperbolehkan.')
            if not self.q('UPDATE orders SET status=? WHERE id=? AND status=?',status,id,o['status']).rowcount: fail(409,'Status telah berubah. Muat ulang halaman.')
            return self.respond(200,{'order':self.one('SELECT * FROM orders WHERE id=?',id)})
        if route=='/api/seller/shop' and method in ('GET','PATCH'):
            shop=self.own_shop()
            if method=='PATCH':
                b=self.body(); name=clean(b.get('name'),90)
                if len(name)<3: fail(400,'Nama toko minimal 3 karakter.')
                services={}; submitted=b.get('services')
                if not isinstance(submitted,dict): fail(400,'Harga layanan tidak valid.')
                for id in SERVICE:
                    p=number(submitted.get(id))
                    if not 1000<=p<=1000000: fail(400,'Harga tiap layanan harus antara Rp1.000 hingga Rp1.000.000.')
                    services[id]=price(p)
                self.q('UPDATE shops SET name=?,city=?,address=?,phone=?,description=?,services_json=? WHERE id=?',name,clean(b.get('city'),70),clean(b.get('address'),200),clean(b.get('phone'),25),clean(b.get('description'),500),json.dumps(services),shop['id'])
                shop=self.own_shop()
            return self.respond(200,{'shop':public_shop(shop)})
        if method=='GET' and route=='/api/seller/pos-data':
            id=self.own_shop()['id']; return self.respond(200,{'customers':self.all('SELECT * FROM pos_customers WHERE shop_id=? ORDER BY id',id),'orders':self.all('SELECT * FROM orders WHERE shop_id=? ORDER BY id DESC',id)})
        if method=='POST' and route=='/api/seller/pos-customers':
            shop=self.own_shop(); b=self.body(); id=b.get('id')
            if type(id)!=int or not 1<=id<=2**63-1 or not clean(b.get('name')) or not clean(b.get('phone')): fail(400,'Data pelanggan tidak lengkap.')
            self.q('INSERT OR REPLACE INTO pos_customers (shop_id,id,name,phone,address,is_pickup_default) VALUES (?,?,?,?,?,?)',shop['id'],id,clean(b.get('name'),90),clean(b.get('phone'),30),clean(b.get('address'),200),int(bool(b.get('is_pickup_default'))))
            return self.respond(200,{'ok':True})
        if method=='POST' and route=='/api/seller/pos-orders':
            shop=self.own_shop(); b=self.body(); service=clean(b.get('service_id'),30); speed=clean(b.get('speed_id'),30); ref=clean(b.get('order_number'),90)
            if service not in SERVICE or speed not in SPEED: fail(400,'Layanan tidak valid.')
            if not re.fullmatch(r'LDY-[A-Z0-9-]+',ref,re.I): fail(400,'Nomor resi tidak valid.')
            id=self.q('''INSERT INTO orders (shop_id,order_number,customer_id,customer_name,customer_phone,customer_address,needs_pickup,service_id,speed_id,item_id,weight,quantity,photo_uri,notes,subtotal,discount,total,payment_status,payment_method,paid_amount,entry_date,estimated_date,estimated_time,status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',shop['id'],ref,number(b.get('customer_id'),0) or None,clean(b.get('customer_name'),90),clean(b.get('customer_phone'),30),clean(b.get('customer_address'),200),int(bool(b.get('needs_pickup'))),service,speed,clean(b.get('item_id'),30) or None,number(b.get('weight'),0),number(b.get('quantity'),0),clean(b.get('photo_uri'),2000000),clean(b.get('notes'),700),price(b.get('subtotal')),price(b.get('discount')),price(b.get('total')),clean(b.get('payment_status'),30) or 'Belum Bayar',clean(b.get('payment_method'),30) or 'Tunai',price(b.get('paid_amount')),clean(b.get('entry_date'),30),clean(b.get('estimated_date'),30),clean(b.get('estimated_time'),20),'Diproses').lastrowid
            return self.respond(201,{'id':id})
        if method=='PATCH' and re.fullmatch(r'/api/seller/pos-orders/[^/]+',route):
            shop=self.own_shop(); ref=unquote(route.split('/')[-1]); o=self.one('SELECT * FROM orders WHERE shop_id=? AND order_number=?',shop['id'],ref)
            if not o: fail(404,'Pesanan tidak ditemukan.')
            b=self.body(); status=clean(b.get('status'),30)
            if status and status not in TRANSITIONS: fail(400,'Status tidak valid.')
            if status and status!=o['status'] and status not in TRANSITIONS.get(o['status'],[]): fail(400,'Transisi status tidak diperbolehkan.')
            fields='customer_name customer_phone customer_address needs_pickup service_id speed_id item_id weight quantity notes subtotal discount total payment_status payment_method paid_amount entry_date estimated_date estimated_time'.split()
            patch={'status':status or o['status']}
            for k in fields:
                if k not in b: continue
                if k in ('subtotal','discount','total','paid_amount','weight','quantity'):
                    n=number(b[k]);
                    if not n>=0: fail(400,'Nilai pesanan tidak valid.')
                    patch[k]=n
                elif k=='needs_pickup': patch[k]=int(bool(b[k]))
                else: patch[k]=clean(b[k],700 if k=='notes' else 220)
            if 'service_id' in patch and patch['service_id'] not in SERVICE: fail(400,'Layanan tidak valid.')
            if 'speed_id' in patch and patch['speed_id'] not in SPEED: fail(400,'Paket tidak valid.')
            if not self.q('UPDATE orders SET '+','.join(k+'=?' for k in patch)+' WHERE id=? AND status=?',*patch.values(),o['id'],o['status']).rowcount: fail(409,'Status telah berubah. Muat ulang halaman.')
            return self.respond(200,{'ok':True})
        fail(404,'Endpoint tidak ditemukan.')
    def static(self, route):
        if self.command not in ('GET','HEAD'): fail(405,'Metode tidak diperbolehkan.')
        rel=unquote(route).lstrip('/') or 'index.html'
        if rel=='kasir.html':
            u=self.session_user()
            if not u or u['role']!='seller': return self.respond(302,b'',extra={'Location':'/'})
        if rel not in ('index.html','kasir.html') and not re.fullmatch(r'(css|js)/[A-Za-z0-9_./-]+',rel): fail(404,'Tidak ditemukan.')
        target=(ROOT/rel).resolve()
        if '..' in rel or not target.is_relative_to(ROOT) or target.suffix not in ('.html','.css','.js','.png','.jpg','.jpeg','.svg','.ico','.webp') or not target.is_file(): fail(404,'Halaman tidak ditemukan.')
        content={'.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.html':'text/html; charset=utf-8'}.get(target.suffix,mimetypes.guess_type(target.name)[0] or 'application/octet-stream')
        return self.respond(200,target.read_bytes(),content)
    def dispatch(self):
        self.connection.settimeout(20)
        self.db=connect()
        try:
            route=urlsplit(self.path).path
            if route.startswith('/api/'):
                origin=self.headers.get('Origin')
                if self.command not in ('GET','HEAD','OPTIONS') and origin and origin!=APP_URL: fail(403,'Asal permintaan tidak diizinkan. Buka alamat APP_URL pada .env.')
                return self.api(route)
            return self.static(route)
        except ApiError as e: self.respond(e.status,{'error':str(e)})
        except sqlite3.IntegrityError: self.respond(409,{'error':'Data sudah ada atau bertentangan dengan data lain.'})
        except (BrokenPipeError,ConnectionResetError): pass
        except Exception as e:
            # Jangan cetak password / API key atau isi permintaan.
            print('[Server]',type(e).__name__)
            self.respond(500,{'error':'Server mengalami gangguan.'})
        finally: self.db.close()
    do_GET=do_POST=do_PATCH=do_HEAD=do_OPTIONS=dispatch

if __name__=='__main__':
    initialize()
    with ThreadingHTTPServer((HOST,PORT),Handler) as server:
        print(f'\nLaundry Kilat - Python\nBuka {APP_URL}\nSQLite: data/laundry.sqlite\nFirebase Auth: '+('API key terisi (uji dengan akun asli)' if READY else 'BELUM diatur (.env); mode demo tersedia'),flush=True)
        try: server.serve_forever()
        except KeyboardInterrupt: print('\nServer dihentikan.')
