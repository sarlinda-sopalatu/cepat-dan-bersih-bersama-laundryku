/**
 * Laundry Kilat Portal — pembeli dan penjual terhubung ke server SQLite dan Firebase Authentication.
 * Semua operasi akun, order, harga dan izin diverifikasi server (bukan localStorage).
 */
(()=>{
 'use strict';
 const $=id=>document.getElementById(id);
 const esc=x=>String(x==null?'':x).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const rupiah=x=>new Intl.NumberFormat('id-ID',{style:'currency',currency:'IDR',maximumFractionDigits:0}).format(Number(x)||0);
 const niceDate=x=>{if(!x)return '-';const d=new Date(String(x).replace(' ','T'));return isNaN(+d)?esc(x):d.toLocaleDateString('id-ID',{day:'numeric',month:'short',year:'numeric'});};
 const SERVICES=[['kiloan','⚖️','Cuci Kiloan','kg'],['satuan','👕','Cuci Satuan','pcs'],['dry_clean','🧥','Dry Clean','pcs'],['cuci_setrika','🧼','Cuci + Setrika','kg'],['setrika_saja','🔥','Setrika Saja','kg']];
 const ITEMS=[['karpet','Karpet',50000],['selimut','Selimut',30000],['gaun','Gaun',35000],['sepatu','Sepatu',25000],['helm','Helm',20000],['jas','Jas',40000],['bed_cover','Bed Cover',45000],['tas','Tas',20000]];
 const SPEED={reguler:1,kilat:1.25,express:1.5};
 const State={user:null,shops:[],orders:[],shop:null,activeShop:null,route:'home',statusFilter:'Semua',search:'',firebaseReady:false};
 let messageTimer;
 async function api(route,method='GET',data){
   const response=await fetch(route,{method,headers:data?{'Content-Type':'application/json'}:{},credentials:'same-origin',body:data?JSON.stringify(data):undefined});
   let output={};try{output=await response.json();}catch{}
   if(!response.ok)throw new Error(output.error||`Server error (${response.status})`);
   return output;
 }
 function toast(message,error=false){const t=$('toast');t.textContent=message;t.classList.toggle('error',error);t.classList.remove('hidden');clearTimeout(messageTimer);messageTimer=setTimeout(()=>t.classList.add('hidden'),4500);}
 function safeAction(fn){Promise.resolve().then(fn).catch(e=>toast(e.message||'Terjadi gangguan jaringan.',true));}
 function actionButton(form,locked){const b=form.querySelector('[type="submit"]');if(b)b.disabled=locked;}
 function showAuth(tab='login'){
   $('loading').classList.add('hidden');$('app-layout').classList.add('hidden');$('reset-feedback').classList.add('hidden');$('auth-layout').classList.remove('hidden');
   for(const name of ['login','register','forgot'])$('panel-'+name).classList.toggle('hidden',tab!==name);
   for(const b of document.querySelectorAll('[data-auth-tab]'))b.classList.toggle('selected',b.dataset.authTab===tab);
   $('auth-tabs').classList.toggle('hidden',tab==='forgot');
   $('firebase-warning').classList.toggle('hidden',State.firebaseReady);
 }
 function renderNav(){
   const options=State.user.role==='buyer'?[
     ['home','▦','Beranda'],['shops','▤','Cari toko laundry'],['orders','◷','Pesanan saya'],['profile','♙','Profil akun']
   ]:[
     ['home','▦','Dashboard'],['orders','◷','Pesanan masuk'],['store','▤','Kelola toko'],['profile','♙','Profil akun']
   ];
   $('nav-items').innerHTML=options.map(([id,icon,name])=>`<button type="button" class="nav-item ${State.route===id?'active':''}" data-nav="${id}"><span class="nav-ico">${icon}</span>${name}</button>`).join('');
 }
 function setView(route){
   if(!State.user)return;
   if(route==='shops'&&State.user.role!=='buyer')route='home';
   if(route==='store'&&State.user.role!=='seller')route='home';
   State.route=route;renderNav();
   const labels={home:State.user.role==='seller'?'Dashboard Toko':'Beranda',shops:'Cari Laundry',orders:State.user.role==='seller'?'Pesanan Masuk':'Pesanan Saya',store:'Pengaturan Toko',profile:'Profil Akun'};
   $('bread-current').textContent=labels[route];$('top-title').textContent=labels[route];
   document.querySelectorAll('.view').forEach(v=>v.classList.toggle('hidden',v.id!==`view-${route}`));
   $('sidebar').classList.remove('open');
   if(route==='orders'||route==='home')safeAction(async()=>{await loadOrders();if(State.route===route)renderCurrent();});
   else if(route==='shops')safeAction(async()=>{await loadShops();if(State.route==='shops')renderCurrent();});
   else if(route==='store')safeAction(async()=>{await loadShop();if(State.route==='store')renderCurrent();});
   else renderCurrent();
 }
 function renderCurrent(){
   if(State.route==='home')renderHome();
   if(State.route==='shops')renderShops();
   if(State.route==='orders')renderOrders();
   if(State.route==='store')renderStore();
   if(State.route==='profile')renderProfile();
 }
 function mountApp(user){
   State.user=user;$('demo-badge').classList.toggle('hidden',!user.demo);$('loading').classList.add('hidden');$('auth-layout').classList.add('hidden');$('app-layout').classList.remove('hidden');
   $('side-name').textContent=user.name;$('side-role').textContent=user.role==='seller'?'Pemilik toko':'Pembeli';
   $('top-name').textContent=user.name.split(' ')[0];$('avatar-side').textContent=user.name.charAt(0).toUpperCase();$('avatar-top').textContent=user.name.charAt(0).toUpperCase();
   setView('home');
 }
 async function loadOrders(){const r=await api('/api/orders');State.orders=r.orders||[];}
 async function loadShops(){const r=await api('/api/shops');State.shops=r.shops||[];}
 async function loadShop(){const r=await api('/api/seller/shop');State.shop=r.shop;}
 const doneStatuses=['Selesai','Diambil'];
 const isActive=o=>!['Dibatalkan','Diambil'].includes(o.status);
 function metric(icon,n,label){return `<article class="metric"><div class="metric-icon">${icon}</div><div><b>${esc(n)}</b><small>${esc(label)}</small></div></article>`;}
 function intro(heading,description,right=''){return `<div class="page-heading"><div><span class="page-eyebrow">LAUNDRY KILAT</span><h1>${heading}</h1><p>${description}</p></div>${right}</div>`;}
 function renderHome(){
   const buyer=State.user.role==='buyer',orders=State.orders;
   const total=orders.length,active=orders.filter(isActive).length,done=orders.filter(o=>doneStatuses.includes(o.status)).length;
   if(buyer){
     $('view-home').innerHTML=`
       <div class="hero-banner"><div><span class="eyebrow">LEBIH NYAMAN, LEBIH PRAKTIS</span><h2>Halo, ${esc(State.user.name.split(' ')[0])}! 👋</h2><p>Nggak perlu repot antre. Pilih laundry favorit, pesan layanan, dan pantau cucian kapan saja.</p><button class="btn" data-nav="shops">Cari laundry terdekat <span>→</span></button></div><div class="banner-illustration">🧺</div></div>
       <div class="metric-grid">${metric('🧾',total,'Total pesanan')}${metric('🫧',active,'Pesanan aktif')}${metric('✅',done,'Pesanan selesai')}${metric('🏪',State.shops.length,'Toko tersedia')}</div>
       <div class="section-head"><div><h2>Pesanan terbaru</h2><p>Perkembangan laundry Anda dalam satu layar</p></div><button class="section-link" data-nav="orders">Lihat semua →</button></div>
       ${orders.length?`<div class="order-list">${orders.slice(0,3).map(o=>orderCard(o,true)).join('')}</div>`:empty('📦','Belum ada pesanan','Pilih toko laundry, buat pesanan pertama Anda, dan pantau prosesnya di sini.','<button class="btn secondary" data-nav="shops">Jelajahi toko →</button>')}
       <div class="section-head"><div><h2>Toko laundry pilihan</h2><p>Mulai dari layanan kiloan sampai cuci satuan</p></div><button class="section-link" data-nav="shops">Semua toko →</button></div>
       ${State.shops.length?`<div class="shop-grid">${State.shops.slice(0,3).map(shopCard).join('')}</div>`:empty('🏪','Belum ada toko terdaftar','Toko akan tampil setelah pemilik laundry membuat akun.')}`;
   } else {
     const revenue=orders.filter(o=>o.status!=='Dibatalkan').reduce((v,o)=>v+(Number(o.total)||0),0);
     const pending=orders.filter(o=>o.status==='Menunggu Konfirmasi').length;
     $('view-home').innerHTML=`
       <div class="hero-banner"><div><span class="eyebrow">PANEL PEMILIK TOKO</span><h2>Selamat datang, ${esc(State.user.name.split(' ')[0])} 👋</h2><p>Kelola pesanan masuk, pantau transaksi, dan atur layanan toko laundry Anda dengan mudah.</p><button class="btn" data-nav="orders">Lihat pesanan masuk <span>→</span></button></div><div class="banner-illustration">🏪</div></div>
       <div class="metric-grid">${metric('🧾',total,'Total pesanan')}${metric('🔔',pending,'Menunggu konfirmasi')}${metric('🫧',orders.filter(o=>o.status==='Diproses').length,'Sedang diproses')}${metric('💸',rupiah(revenue),'Nilai transaksi*')}</div>
       <div class="section-head"><div><h2>Pesanan terbaru</h2><p>Pesanan dari pembeli online dan kasir toko</p></div><button class="section-link" data-nav="orders">Kelola pesanan →</button></div>
       ${orders.length?`<div class="order-list">${orders.slice(0,4).map(o=>orderCard(o,true)).join('')}</div>`:empty('📥','Belum ada pesanan','Pesanan pelanggan akan otomatis muncul di sini ketika mereka memilih toko Anda.')}
       <div class="section-head"><h2>Alat bantu pemilik toko</h2></div>
       <div class="store-performance"><div class="panel"><h3>🧾 Mode kasir lengkap</h3><p>Gunakan alur kasir asli: data pelanggan, quality control, diskon, nota, PDF, dan label QR.</p><a href="/kasir.html" class="btn secondary">Buka kasir lengkap →</a></div><div class="panel"><h3>⚙️ Kelola toko dan harga</h3><p>Atur nama toko, alamat, nomor kontak, dan tarif yang ditampilkan kepada pembeli.</p><button class="btn secondary" data-nav="store">Pengaturan toko →</button></div></div><p class="text-muted" style="font-size:11px;margin-top:12px">*Nilai transaksi dihitung dari total pesanan yang tidak dibatalkan, bukan bukti pembayaran masuk.</p>`;
   }
 }
 function empty(icon,title,body,action=''){return `<div class="empty-state"><div class="empty-icon">${icon}</div><h3>${title}</h3><p>${body}</p>${action}</div>`;}
 function shopCard(s){const price=Math.min(...Object.values(s.services||{}).map(Number).filter(v=>v>0));return `<article class="shop-card"><div class="shop-cover">🏪</div><div class="shop-info"><div class="shop-meta"><span>📍 ${esc(s.city||'Lokasi belum diisi')}</span><span class="open">● Menerima pesanan</span></div><h3>${esc(s.name)}</h3><p>${esc(s.description||s.address||'Jasa laundry dengan layanan profesional.')}</p><div class="shop-pricing"><span>Harga mulai</span><strong>${rupiah(Number.isFinite(price)?price:0)}</strong></div><button class="btn primary" data-order-shop="${s.id}">🧺 Pesan di toko ini →</button></div></article>`;}
 function renderShops(){
   const q=State.search.trim().toLowerCase();const shops=State.shops.filter(s=>[s.name,s.city,s.address,s.description].join(' ').toLowerCase().includes(q));
   $('view-shops').innerHTML=`${intro('Temukan laundry favorit ✨','Pilih toko dan layanan yang cocok untuk kebutuhanmu.',`<div class="search-wrap">⌕ <input id="shop-search" type="search" value="${esc(State.search)}" placeholder="Cari nama toko atau kota..." aria-label="Cari toko laundry"></div>`)}${shops.length?`<div class="shop-grid">${shops.map(shopCard).join('')}</div>`:empty('🔎','Toko tidak ditemukan','Coba gunakan nama atau lokasi yang berbeda.')}`;
 }
 function statusChip(s){const cls=s==='Menunggu Konfirmasi'?'pending':s==='Diproses'?'processing':doneStatuses.includes(s)?'done':'cancelled';return `<span class="chip ${cls}">● ${esc(s)}</span>`;}
 function svcName(id){return SERVICES.find(s=>s[0]===id)?.[2]||id;}
 function speedName(id){return ({reguler:'Reguler',kilat:'Kilat',express:'Express'})[id]||id;}
 function orderCard(o,compact=false){
   const seller=State.user.role==='seller';
   let actions='';
   if(!compact){
     if(seller){
       if(o.status==='Menunggu Konfirmasi')actions=`<button class="btn primary btn-sm" data-status-id="${o.id}" data-next-status="Diproses">✓ Terima pesanan</button><button class="btn danger btn-sm" data-status-id="${o.id}" data-next-status="Dibatalkan">Tolak</button>`;
       if(o.status==='Diproses')actions=`<button class="btn secondary btn-sm" data-status-id="${o.id}" data-next-status="Selesai">✓ Tandai selesai</button>`;
       if(o.status==='Selesai')actions=`<button class="btn secondary btn-sm" data-status-id="${o.id}" data-next-status="Diambil">✓ Sudah diambil</button>`;
     } else if(o.status==='Menunggu Konfirmasi')actions=`<button class="btn danger btn-sm" data-status-id="${o.id}" data-next-status="Dibatalkan">Batalkan pesanan</button>`;
   }
   return `<article class="order-card"><div><span class="order-small">#${esc(o.order_number)}</span><h3>${esc(seller?o.customer_name:(o.shop_name||'Toko laundry'))}</h3><div class="order-detail-row"><span>🧺 ${esc(svcName(o.service_id))}</span><span>⚡ ${esc(speedName(o.speed_id))}</span><span>📦 ${o.weight?esc(o.weight)+' kg':esc(o.quantity)+' pcs'}</span><span>📅 ${niceDate(o.created_at)}</span></div><p>${o.needs_pickup?'🚚 Antar-jemput diminta · ':''}${o.notes?'📝 '+esc(o.notes):'Estimasi selesai: '+niceDate(o.estimated_date)}</p>${seller&&o.customer_phone?`<p>📱 ${esc(o.customer_phone)} ${o.customer_phone.match(/^\+?[0-9 -]{8,20}$/)?`<a href="https://wa.me/${esc(normalizePhone(o.customer_phone))}" target="_blank" rel="noopener noreferrer" class="order-small">Hubungi via WhatsApp ↗</a>`:''}</p>`:''}</div><div class="order-actions">${statusChip(o.status)}<div class="order-price">${rupiah(o.total)}</div>${actions?`<div class="order-status-controls">${actions}</div>`:''}</div></article>`;
 }
 function normalizePhone(phone){let p=String(phone).replace(/\D/g,'');return p.startsWith('0')?'62'+p.slice(1):p;}
 function renderOrders(){
   const tabs=['Semua','Menunggu Konfirmasi','Diproses','Selesai','Diambil','Dibatalkan'];
   const visible=State.statusFilter==='Semua'?State.orders:State.orders.filter(o=>o.status===State.statusFilter);
   const title=State.user.role==='seller'?'Kelola pesanan masuk 📦':'Riwayat pesanan 📦';
   $('view-orders').innerHTML=`${intro(title,State.user.role==='seller'?'Terima dan perbarui status pesanan pelanggan secara langsung.':'Pantau status pesanan dari toko yang kamu pilih.',State.user.role==='buyer'?'<button class="btn primary" data-nav="shops">+ Pesan laundry</button>':'<a class="btn secondary" href="/kasir.html">Buka kasir →</a>')}<div class="filter-tabs">${tabs.map(t=>`<button class="filter-tab ${State.statusFilter===t?'active':''}" data-filter="${esc(t)}">${esc(t)}</button>`).join('')}</div>${visible.length?`<div class="order-list">${visible.map(o=>orderCard(o)).join('')}</div>`:empty('🗃️','Belum ada pesanan','Tidak ada pesanan dengan status yang dipilih.')}`;
 }
 function renderStore(){
   const s=State.shop;if(!s)return $('view-store').innerHTML=empty('⌛','Memuat toko...','');
   $('view-store').innerHTML=`${intro('Pengaturan toko 🏪','Ubah profil toko dan harga layanan yang akan dilihat oleh pembeli.')}<div class="grid-2"><div class="panel"><div class="section-head" style="margin:0 0 20px"><h2>Informasi toko</h2></div><form id="form-shop" class="settings-form"><label>Nama toko<input name="name" minlength="3" required value="${esc(s.name)}"></label><div class="form-two"><label>Kota<input name="city" value="${esc(s.city)}" placeholder="Makassar"></label><label>WhatsApp toko<input name="phone" value="${esc(s.phone)}" placeholder="08xxxxxxxxxx"></label></div><label>Alamat toko<input name="address" value="${esc(s.address)}" placeholder="Alamat lengkap"></label><label>Deskripsi<textarea name="description" rows="3">${esc(s.description)}</textarea></label><div class="section-head"><h2>Tarif layanan</h2></div><div class="service-price-grid">${SERVICES.map(([id,icon,title])=>`<div class="service-price"><label for="price-${id}">${icon} ${esc(title)}</label><input id="price-${id}" name="price-${id}" type="number" min="1000" max="1000000" step="500" required value="${Number(s.services[id])||0}"></div>`).join('')}</div><button type="submit" class="btn primary">💾 Simpan perubahan toko</button></form></div><div style="display:grid;gap:17px;align-content:start"><div class="panel"><h3>✨ Pratinjau toko</h3><div class="shop-cover" style="border-radius:12px">🏪</div><h3 style="margin:15px 0 5px">${esc(s.name)}</h3><p class="text-muted">📍 ${esc(s.address||s.city||'Belum mengisi lokasi')}</p><p>${esc(s.description||'')}</p><p class="text-muted">📱 ${esc(s.phone||'Belum mengisi WhatsApp')}</p></div><div class="info-card"><span>💡</span><div><strong>Informasi penting</strong><br>Harga kiloan menggunakan satuan kilogram. Layanan satuan/dry clean bisa memiliki harga khusus untuk barang seperti jas, selimut, dan sepatu. Pesanan pembeli dihitung otomatis oleh server.</div></div><div class="panel"><h3>🧾 Kasir laundry</h3><p class="text-muted">Aplikasi kasir lengkap dari website awal masih bisa digunakan untuk pelanggan walk-in dan pembuatan nota.</p><a class="btn secondary" href="/kasir.html">Buka kasir →</a></div></div></div>`;
 }
 function renderProfile(){
   const u=State.user;
   $('view-profile').innerHTML=`${intro('Profil akun 👤','Informasi akun yang digunakan saat masuk ke Laundry Kilat.')}<div class="panel profile-card"><div class="profile-head"><div class="avatar">${esc(u.name[0]?.toUpperCase())}</div><div><h2>${esc(u.name)}</h2><p>${u.role==='buyer'?'Akun pembeli':'Akun pemilik toko'}</p></div></div><div class="profile-fields"><div class="profile-field"><small>Nama lengkap</small><b>${esc(u.name)}</b></div><div class="profile-field"><small>Email</small><b>${esc(u.email)}</b></div><div class="profile-field"><small>Jenis akun</small><b>${u.role==='buyer'?'🛍️ Pembeli':'🏪 Pemilik toko'}</b></div><div class="profile-field"><small>Nomor telepon</small><b>${esc(u.phone||'Belum diisi')}</b></div></div><div class="info-card" style="margin-top:22px"><span>🔐</span><div><strong>Keamanan akun</strong><br>${u.demo?'Ini akun simulasi lokal; reset sandi tidak tersedia.':'Kata sandi dikelola Firebase Authentication. Untuk mengganti kata sandi, keluar dari akun lalu pilih menu <b>Lupa kata sandi?</b>. Data transaksi disimpan di SQLite lokal.'}</div></div><button type="button" class="btn outline" id="logout-profile" style="margin-top:22px">↪ Keluar akun</button></div>`;
 }
 function openOrderModal(id){
   const s=State.shops.find(x=>x.id===Number(id));if(!s)return toast('Toko tidak ditemukan.',true);
   State.activeShop=s;$('order-shop-id').value=s.id;$('modal-shop-name').textContent=s.name+' · '+(s.city||'Toko laundry');
   $('order-service').innerHTML=SERVICES.map(([id,icon,title,unit])=>`<option value="${id}">${icon} ${title} · ${rupiah(s.services[id])}/${unit}</option>`).join('');
   $('order-item').innerHTML='<option value="">Umum (tarif layanan)</option>'+ITEMS.map(([id,name,price])=>`<option value="${id}">${name} · ${rupiah(price)}/pcs</option>`).join('');
   $('order-phone').value=State.user.phone||'';$('form-order').reset();$('order-shop-id').value=s.id;$('order-phone').value=State.user.phone||'';
   $('order-modal').classList.remove('hidden');document.body.style.overflow='hidden';updateEstimate();
 }
 function closeOrderModal(){$('order-modal').classList.add('hidden');document.body.style.overflow='';}
 function updateEstimate(){
   const shop=State.activeShop;if(!shop)return;
   const service=$('order-service').value,speed=$('order-speed').value;
   const weight=['kiloan','cuci_setrika','setrika_saja'].includes(service);
   $('order-item-row').classList.toggle('hidden',weight);
   const label=$('order-qty-label');label.firstChild.textContent=weight?'Berat cucian (kg)':'Jumlah barang (pcs)';
   const q=$('order-quantity');q.step=weight?'0.1':'1';q.min=weight?'0.1':'1';
   if(!weight&&q.value.includes('.'))q.value='1';
   const item=$('order-item').value;
   const base=!weight&&item?(ITEMS.find(i=>i[0]===item)?.[2]||0):Number(shop.services[service])||0;
   $('order-estimate').textContent=rupiah(Math.round(base*(Number(q.value)||0)*(SPEED[speed]||1)));
 }
 async function onLogin(form){const f=new FormData(form);const data=await api('/api/auth/login','POST',{email:f.get('email'),password:f.get('password')});form.reset();await Promise.all([loadShops(),loadOrdersAfterAuth(data.user)]);mountApp(data.user);toast('Selamat datang, '+data.user.name+'!');}
 async function loadOrdersAfterAuth(user){const r=await api('/api/orders');State.orders=r.orders||[];if(user.role==='seller'){const s=await api('/api/seller/shop');State.shop=s.shop;}}
 async function onRegister(form){const f=new FormData(form);const obj=Object.fromEntries(f.entries());if(obj.role==='seller'&&!obj.shopName?.trim())throw new Error('Isi nama toko terlebih dahulu.');const result=await api('/api/auth/register','POST',obj);form.reset();$('seller-register-fields').classList.add('hidden');form.querySelector('[name=shopName]').required=false;document.querySelectorAll('.role-card').forEach(c=>c.classList.toggle('active',c.querySelector('input').checked));await Promise.all([loadShops(),loadOrdersAfterAuth(result.user)]);mountApp(result.user);toast('Akun '+(result.user.role==='buyer'?'pembeli':'pemilik toko')+' berhasil dibuat!');}
 async function logout(){await api('/api/auth/logout','POST',{});State.user=null;State.orders=[];State.shop=null;State.activeShop=null;showAuth('login');toast('Anda telah keluar dari akun.');}
 function bind(){
   document.addEventListener('click',e=>{
     const demo=e.target.closest('[data-demo]');if(demo){demo.disabled=true;safeAction(async()=>{try{const r=await api('/api/auth/demo','POST',{role:demo.dataset.demo});await Promise.all([loadShops(),loadOrdersAfterAuth(r.user)]);mountApp(r.user);toast('Mode demonstrasi aktif.');}finally{demo.disabled=false;}});return;}
     const tab=e.target.closest('[data-auth-tab]');if(tab){showAuth(tab.dataset.authTab);return;}
     const toggler=e.target.closest('[data-toggle-password]');if(toggler){const inp=toggler.parentElement.querySelector('input');inp.type=inp.type==='password'?'text':'password';return;}
     const nav=e.target.closest('[data-nav]');if(nav){setView(nav.dataset.nav);return;}
     const order=e.target.closest('[data-order-shop]');if(order){openOrderModal(order.dataset.orderShop);return;}
     const filter=e.target.closest('[data-filter]');if(filter){State.statusFilter=filter.dataset.filter;renderOrders();return;}
     const status=e.target.closest('[data-status-id]');if(status){safeAction(async()=>{
       const id=Number(status.dataset.statusId),next=status.dataset.nextStatus;
       if(next==='Dibatalkan'&&!window.confirm('Yakin ingin membatalkan pesanan ini?'))return;
       status.disabled=true;
       try {await api('/api/orders/'+id,'PATCH',{status:next});await loadOrders();renderCurrent();toast('Status pesanan diperbarui menjadi '+next+'.');}
       finally{status.disabled=false;}
     });return;}
     if(e.target.closest('[data-close-modal]')){closeOrderModal();return;}
   });
   $('goto-forgot').addEventListener('click',()=>showAuth('forgot'));
   $('menu-toggle').addEventListener('click',()=>$('sidebar').classList.toggle('open'));
   $('logout-side').addEventListener('click',()=>safeAction(logout));
   $('dashboard-main').addEventListener('click',e=>{if(e.target.closest('#logout-profile'))safeAction(logout);});
   $('order-modal').addEventListener('click',e=>{if(e.target===$('order-modal'))closeOrderModal();});
   document.addEventListener('keydown',e=>{if(e.key==='Escape')closeOrderModal();});
   $('form-register').addEventListener('change',e=>{if(e.target.name==='role'){
      const seller=e.target.value==='seller';$('seller-register-fields').classList.toggle('hidden',!seller);
      $('form-register').querySelector('[name="shopName"]').required=seller;
      document.querySelectorAll('.role-card').forEach(c=>c.classList.toggle('active',c.querySelector('input').checked));
   }});
   for(const [id,fn] of [['form-login',onLogin],['form-register',onRegister]])$(id).addEventListener('submit',e=>{e.preventDefault();const form=e.currentTarget;actionButton(form,true);safeAction(async()=>{try{await fn(form);}finally{actionButton(form,false);}});});
   $('form-forgot').addEventListener('submit',e=>{e.preventDefault();const form=e.currentTarget;actionButton(form,true);safeAction(async()=>{try{const f=new FormData(form);const result=await api('/api/auth/forgot','POST',{email:f.get('email')});$('reset-feedback').textContent=result.message;$('reset-feedback').classList.remove('hidden');toast(result.message);form.reset();}finally{actionButton(form,false);}});});
   $('dashboard-main').addEventListener('input',e=>{if(e.target.id==='shop-search'){State.search=e.target.value;const start=e.target.selectionStart;renderShops();const input=$('shop-search');input.focus();input.setSelectionRange(start,start);}});
   $('dashboard-main').addEventListener('submit',e=>{if(e.target.id!=='form-shop')return;e.preventDefault();const form=e.target;actionButton(form,true);safeAction(async()=>{try{
      const f=new FormData(form),services={};for(const [id] of SERVICES)services[id]=Number(f.get('price-'+id));
      const r=await api('/api/seller/shop','PATCH',{name:f.get('name'),city:f.get('city'),address:f.get('address'),phone:f.get('phone'),description:f.get('description'),services});
      State.shop=r.shop;renderStore();toast('Informasi toko berhasil disimpan.');
   }finally{actionButton(form,false);}});});
   for(const id of ['order-service','order-speed','order-item','order-quantity'])$(id).addEventListener('input',updateEstimate);
   $('form-order').addEventListener('submit',e=>{e.preventDefault();const form=e.currentTarget;actionButton(form,true);safeAction(async()=>{try{
      const f=new FormData(form),serviceId=f.get('serviceId');const weight=['kiloan','cuci_setrika','setrika_saja'].includes(serviceId);
      const amount=Number(f.get('amount'));if(!weight&&!Number.isInteger(amount))throw new Error('Jumlah barang harus bilangan bulat.');
      const request={shopId:Number(f.get('shopId')),serviceId,speedId:f.get('speedId'),itemId:f.get('itemId'),weight:weight?amount:0,quantity:weight?0:amount,phone:f.get('phone'),address:f.get('address'),pickup:f.has('pickup'),notes:f.get('notes')};
      const result=await api('/api/orders','POST',request);
      await loadOrders();closeOrderModal();State.statusFilter='Semua';setView('orders');toast('Pesanan #'+result.order.order_number+' berhasil dikirim ke toko!');
   }finally{actionButton(form,false);}});});
 }
 async function start(){bind();try{
   const [session,config]=await Promise.all([api('/api/session'),api('/api/config')]);State.firebaseReady=!!config.firebase_ready;
   if(session.user){State.user=session.user;await Promise.all([loadShops(),loadOrdersAfterAuth(session.user)]);mountApp(session.user);}else showAuth('login');
 }catch(error){showAuth('login');toast('Gagal terhubung ke server: '+error.message,true);}}
 document.addEventListener('DOMContentLoaded',start);
})();
