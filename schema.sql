PRAGMA journal_mode = WAL;
 PRAGMA foreign_keys = ON;
 CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('buyer','seller')),
  phone TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
 );
 CREATE TABLE IF NOT EXISTS shops (
  id INTEGER PRIMARY KEY AUTOINCREMENT, owner_id INTEGER NOT NULL UNIQUE REFERENCES users(id),
  name TEXT NOT NULL, city TEXT NOT NULL DEFAULT '', address TEXT NOT NULL DEFAULT '',
  phone TEXT NOT NULL DEFAULT '', description TEXT NOT NULL DEFAULT '',
  services_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
 );
 CREATE TABLE IF NOT EXISTS orders (
  id INTEGER PRIMARY KEY AUTOINCREMENT, shop_id INTEGER NOT NULL REFERENCES shops(id),
  buyer_id INTEGER REFERENCES users(id),
  order_number TEXT NOT NULL, customer_id INTEGER, customer_name TEXT NOT NULL,
  customer_phone TEXT NOT NULL DEFAULT '', customer_address TEXT NOT NULL DEFAULT '',
  needs_pickup INTEGER NOT NULL DEFAULT 0, service_id TEXT NOT NULL,
  speed_id TEXT NOT NULL, item_id TEXT, weight REAL NOT NULL DEFAULT 0,
  quantity REAL NOT NULL DEFAULT 0, photo_uri TEXT NOT NULL DEFAULT '',
  notes TEXT NOT NULL DEFAULT '', subtotal INTEGER NOT NULL DEFAULT 0,
  discount INTEGER NOT NULL DEFAULT 0, total INTEGER NOT NULL DEFAULT 0,
  payment_status TEXT NOT NULL DEFAULT 'Belum Bayar', payment_method TEXT NOT NULL DEFAULT 'Tunai',
  paid_amount INTEGER NOT NULL DEFAULT 0, entry_date TEXT NOT NULL DEFAULT '',
  estimated_date TEXT NOT NULL DEFAULT '', estimated_time TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'Menunggu Konfirmasi',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(shop_id, order_number)
 );
 CREATE INDEX IF NOT EXISTS idx_orders_buyer ON orders(buyer_id);
 CREATE INDEX IF NOT EXISTS idx_orders_shop ON orders(shop_id);
 CREATE TABLE IF NOT EXISTS pos_customers (
  shop_id INTEGER NOT NULL REFERENCES shops(id), id INTEGER NOT NULL,
  name TEXT NOT NULL, phone TEXT NOT NULL, address TEXT NOT NULL DEFAULT '',
  is_pickup_default INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (shop_id,id)
 );
 CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
  expires_at INTEGER NOT NULL
 );
