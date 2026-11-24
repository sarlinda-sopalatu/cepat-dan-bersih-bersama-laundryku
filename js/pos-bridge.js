/**
 * Menghubungkan semua perubahan dari aplikasi kasir 9 layar ke SQLite toko.
 * LocalStorage hanya cache untuk kompatibilitas UI sinkron versi lama.
 * Server menjadi penyimpanan lintas-akun yang sesungguhnya.
 */
(() => {
  'use strict';
  const CUSTOMERS_KEY='laundrykilat.customers.v1';
  const ORDERS_KEY='laundrykilat.orders.v1';
  let queue=Promise.resolve(),busy=0;
  const $=id=>document.getElementById(id);
  function message(s,isError=false) {
    const e=$('pos-sync-state');if(!e)return;
    e.textContent=s;e.classList.toggle('sync-error',isError);
  }
  async function request(route, method='GET', data) {
    const response=await fetch(route,{method,credentials:'same-origin',headers:data?{'Content-Type':'application/json'}:{},body:data?JSON.stringify(data):undefined});
    let r={};try{r=await response.json();}catch{}
    if(!response.ok)throw new Error(r.error||`HTTP ${response.status}`);
    return r;
  }
  function enqueue(fn) {
    busy++;
    message('⟳ Menyimpan ke database...');
    queue=queue.then(fn).then(()=>{
      busy--;if(!busy)message('✓ Terhubung ke database');
    }).catch(e=>{
      busy--;message('⚠ Gagal sinkronisasi',true);
      console.error('Sinkronisasi kasir gagal:',e);
      window.alert('Gagal menyimpan data ke database. Jangan tutup halaman. Periksa server dan ulangi. Detail: '+e.message);
    });
    return queue;
  }
  async function bootstrap() {
    const data=await request('/api/seller/pos-data');
    // Sumber data dari server saat membuka kasir, termasuk pesanan online pembeli.
    localStorage.setItem(CUSTOMERS_KEY,JSON.stringify(data.customers));
    localStorage.setItem(ORDERS_KEY,JSON.stringify(data.orders));
    message('✓ Terhubung ke database');
    $('pos-reload').addEventListener('click',async()=>{
      await queue;
      location.reload();
    });
  }
  function customerChanged(row){enqueue(()=>request('/api/seller/pos-customers','POST',row));}
  function orderCreated(row){enqueue(()=>request('/api/seller/pos-orders','POST',row));}
  function orderChanged(order,patch){
    if(!order.order_number)return;
    enqueue(()=>request(`/api/seller/pos-orders/${encodeURIComponent(order.order_number)}`,'PATCH',patch));
  }
  window.POSBridge={bootstrap,customerChanged,orderCreated,orderChanged};
})();
