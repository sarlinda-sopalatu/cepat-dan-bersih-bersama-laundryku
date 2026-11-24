# Laundry Kilat — Purple Neumorphism + Firebase

Aplikasi laundry dua peran: pembeli/pelanggan dan pemilik toko. Versi ini mempertahankan portal pemesanan dan kasir 9 layar (pelanggan, layanan, QC, diskon, pembayaran, jadwal, nota, QR, dan lain-lain). Firebase Authentication mengelola kata sandi dan pengiriman email reset. Profil, toko, pelanggan, dan transaksi berada di SQLite lokal, bukan Firestore.

## 1. Jalankan dari terminal Visual Studio Code (Windows 10/11)

1. Ekstrak ZIP. Buka VS Code → File → Open Folder → pilih folder `laundry-kilat-python-ungu` (folder yang berisi `server.py`).
2. Buka Terminal → New Terminal (PowerShell).
3. Periksa Python:
   ```powershell
   python --version
   ```
   Gunakan Python 3.10 atau lebih baru. Jika tidak dikenali, instal dari https://www.python.org/downloads/windows/ dan aktifkan opsi Add Python to PATH jika tersedia, kemudian buka ulang VS Code. Jika tersedia perintah `py`, Anda dapat menggunakan `py --version` dan `py server.py` sebagai alternatif. Semua modul server adalah bawaan Python (http.server, sqlite3, urllib); tidak perlu pip install, Flask, Django, Node.js, PHP, XAMPP, Live Server, Firebase CLI, atau hosting.
4. Jalankan:
   ```powershell
   python server.py
   ```
5. Buka Chrome atau Edge, ketik `http://localhost:8090`. Jangan membuka index.html dengan klik ganda; fitur server tidak akan bekerja lewat file://. Biarkan terminal menyala. Untuk berhenti tekan Ctrl+C.
6. Untuk percobaan tanpa konfigurasi Firebase, buka Akun demonstrasi → Pembeli atau Pemilik toko. Akun demo lokal tidak menggunakan email/password, dan hanya berinteraksi dengan toko/pesanan simulasi. Jangan gunakan informasi pribadi. Untuk berpindah peran, logout dahulu. Mode demo bukan akun produksi.

## 2. Konfigurasi Firebase Authentication (sekali saja)

1. Masuk ke https://console.firebase.google.com/ dengan akun Google.
2. Klik Add project / Create a project. Buat proyek baru khusus Laundry Kilat (misalnya `laundry-kilat` dengan ID unik). Analytics opsional.
3. Di Build → Authentication → Get started, buka Sign-in method, pilih Email/Password, aktifkan opsi Email/Password lalu Save. Email link sign-in tidak diperlukan.
4. Klik ikon roda gigi → Project settings → General. Pada Your apps klik ikon web `</>`; masukkan nama `Laundry Kilat Web`, jangan centang Firebase Hosting, lalu Register app.
5. Pada konfigurasi SDK temukan `apiKey: "..."`. Salin hanya nilainya, tanpa tanda kutip. Anda tidak perlu menyalin keseluruhan SDK; server menggunakan Firebase Auth REST API.
6. Di VS Code buka file `.env` yang sudah disediakan. Jika file tidak ada, jalankan `Copy-Item .env.example .env`. Isi seperti berikut:
   ```env
   PORT=8090
   HOST=127.0.0.1
   APP_URL=http://localhost:8090
   FIREBASE_API_KEY=ISI_WEB_API_KEY_FIREBASE
   ```
   Jangan memakai API key proyek Puskesmas atau proyek lain. Simpan Ctrl+S. Jangan memasukkan password Gmail, service-account key, atau app password. Jangan mengganti proyek Firebase setelah membuat akun nyata tanpa migrasi data.
7. Authentication → Templates → Password reset. Pertahankan URL aksi reset bawaan Firebase. Anda tidak perlu mengatur SMTP, membuat halaman reset publik, atau men-deploy website. Firebase sendiri menyediakan halaman untuk mengganti password melalui link. Bila menggunakan konfigurasi domain/action handler khusus, kembalikan ke default Firebase. Untuk pengiriman email, koneksi internet diperlukan.
8. Hentikan server dengan Ctrl+C, jalankan `python server.py` lagi. Terminal harus menampilkan `Firebase Auth: API key terisi (uji dengan akun asli)`. Pesan ini berarti key terisi, bukan bukti bahwa key valid.

## 3. Daftar akun dan uji reset email asli

1. Buka `http://localhost:8090` → Daftar akun → pilih Pembeli atau Pemilik toko.
2. Isi nama, nomor WhatsApp opsional, email aktif yang Anda miliki, dan sandi minimal 8 karakter. Pemilik toko juga mengisi nama toko, lokasi dan alamat. Klik Buat akun. Di Firebase Console → Authentication → Users, akun baru akan terlihat. Profil dan peran tersimpan di SQLite lokal. Untuk melihat toko nyata dari pembeli, buat akun pemilik toko nyata terlebih dahulu.
3. Logout → Lupa kata sandi? → masukkan email yang sama → Kirim tautan reset. Aplikasi menggunakan endpoint `accounts:sendOobCode` dengan `requestType: PASSWORD_RESET`. Jika email terdaftar, Firebase akan mengirim tautan ke email tersebut, bukan ke alamat pemilik konfigurasi.
4. Buka Inbox/Spam, cari email reset dari Firebase. Buka tautan yang diterima, isi kata sandi baru, dan simpan di halaman resmi Firebase. Tidak perlu server web lokal dapat diakses dari internet.
5. Kembali ke `http://localhost:8090` dan masuk dengan kata sandi baru. Kata sandi lama tidak berlaku untuk login baru. Sesi lokal yang sudah aktif dapat bertahan hingga maksimal 1 jam atau logout. Akun demo tidak bisa direset.

## 4. Jika email tidak masuk

- Pastikan email terdaftar di Authentication → Users dan benar-benar dapat diakses. Respons reset bersifat umum untuk menjaga privasi alamat email.
- Pastikan Email/Password aktif, API key benar, file `.env` disimpan, dan server sudah dimulai ulang.
- Periksa internet, Spam/Junk, Promotions, dan kapasitas kotak masuk. Firebase memiliki kuota serta pembatasan percobaan pengiriman; jangan terus menekan tombol.
- Coba dari Firebase Console → Authentication → Users → menu akun → Reset password sebagai diagnosis. Periksa template password reset dan pastikan URL aksi bawaan tidak diubah.
- Bila port 8090 sudah digunakan, ubah PORT dan APP_URL secara konsisten (contoh PORT=8091 dan APP_URL=http://localhost:8091), restart, lalu buka URL baru.
- Jika muncul `python is not recognized`, periksa instalasi Python dan PATH atau coba `py server.py`.

## 5. Struktur file

- `index.html` — login, pendaftaran, lupa password, dashboard dua peran.
- `css/portal.css`, `css/style.css`, `css/neumorphism.css` — tampilan ungu dan responsif, bayangan soft UI.
- `js/portal.js` — interaksi form, menu, pemesanan, akun demo.
- `server.py` — backend Python: HTTP, Firebase Auth REST, SQLite, izin akses pembeli/pemilik toko.
- `schema.sql` — struktur database SQLite.
- `tests/test_server.py` — pengujian API lokal dan simulasi Firebase. Jalankan `python -m unittest discover -s tests -v`.
- `kasir.html`, `js/app.js`, `js/pos-bridge.js` — kasir dan sinkronisasi database lokal.
- `.env`, `.env.example` — konfigurasi project Firebase.
- `data/laundry.sqlite` — dibuat otomatis saat server berjalan. Cadangkan setelah server berhenti; jangan hapus jika data penting. Akun cloud Firebase tetap ada meskipun database lokal dihapus. Jangan menggunakan database lama tanpa migrasi profil/UID; ZIP ini memulai database baru.

## 6. Lingkup dan batasan

Ini aplikasi pengembangan lokal. Akun nyata dan reset memakai layanan cloud Firebase, tetapi transaksi tidak tersinkron antar-laptop/server. Aplikasi berjalan pada loopback 127.0.0.1; desain responsif dapat diperiksa dengan mengecilkan browser. Akses dari HP lain membutuhkan konfigurasi jaringan lokal terpisah. Akun demo memakai data bersama di laptop ini; bukan untuk informasi asli. Untuk penggunaan publik, diperlukan HTTPS, penguatan sesi, pengujian keamanan, backup, dan kebijakan perlindungan data. Tidak ada biaya hosting untuk menjalankan versi lokal; Firebase tunduk pada kuota dan ketentuan paket Anda.

Referensi resmi:
- https://firebase.google.com/docs/auth/web/password-auth
- https://firebase.google.com/docs/reference/rest/auth
- https://firebase.google.com/docs/auth/web/manage-users

Pengujian: lihat tests/test_server.py untuk pengujian API lokal dan respons Firebase simulasi (bukan pengiriman email nyata). Uji email nyata setelah memasukkan API key proyek Anda. HTML/CSS/JavaScript tetap dipakai di browser; seluruh server dan akses database kini menggunakan Python.
"# cepat-dan-bersih-bersama-laundryku" 
