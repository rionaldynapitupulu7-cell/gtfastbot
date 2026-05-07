# 🎰 Bot Reme Telegram

## Cara Setup (via HP - Railway)

### Langkah 1: Buat Bot Telegram
1. Buka Telegram, cari @BotFather
2. Ketik `/newbot`
3. Masukkan nama bot (contoh: `Reme Game Bot`)
4. Masukkan username bot (contoh: `remeGameBot`)
5. Copy **TOKEN** yang diberikan BotFather

### Langkah 2: Edit File bot.py
Buka file `bot.py`, cari baris ini:
```python
BOT_TOKEN = "MASUKKAN_TOKEN_BOT_DISINI"
ADMIN_IDS = [123456789]
```
Ganti:
- `MASUKKAN_TOKEN_BOT_DISINI` → token dari BotFather
- `123456789` → Telegram ID kamu (cek via @userinfobot)

### Langkah 3: Deploy ke Railway (GRATIS)
1. Buka https://railway.app di HP
2. Daftar/login pakai GitHub
3. Klik **New Project** → **Deploy from GitHub repo**
4. Upload file bot.py dan requirements.txt ke GitHub dulu
5. Railway akan otomatis install dan jalankan bot

### Cara Upload ke GitHub (via HP)
1. Buka https://github.com
2. Buat repository baru (misal: `reme-bot`)
3. Upload file `bot.py` dan `requirements.txt`
4. Connect ke Railway

---

## Perintah Bot

### Untuk Pemain:
| Command | Fungsi |
|---------|--------|
| `.reme 5000 1r` | Buat/join room taruhan 5000, 1 ronde |
| `.reme 10000 3r` | Buat/join room taruhan 10000, 3 ronde |
| `.spinr` | Spin roulette |
| `.saldo` | Cek saldo |
| `.topup 50000` | Request top up 50rb |
| `.help` | Lihat menu bantuan |

### Untuk Admin:
| Command | Fungsi |
|---------|--------|
| `.konfirmasi [id]` | Konfirmasi top up |
| `.tolak [id]` | Tolak top up |
| `.addsaldo [user_id] [jumlah]` | Tambah saldo manual |
| `.setsaldo [user_id] [jumlah]` | Set saldo user |
| `.ceksaldo [user_id]` | Cek saldo user |

---

## Aturan Reme
- Angka roulette: 0-36
- Jika angka > 9, digit dijumlahkan (contoh: 34 → 3+4 = **7**)
- Pemain dengan nilai terbesar menang
- Jika seri, ronde tidak ada poin
- Tax 3% dari total pot
- Angka 0 = nilai 0 (terendah)

---

## Cara Top Up (Alur)
1. Player ketik `.topup 50000`
2. Bot kirim notif ke admin
3. Player transfer ke DANA/rekening admin
4. Player kirim bukti ke admin
5. Admin ketik `.konfirmasi [id]`
6. Saldo otomatis masuk ke player

---

## Cara Cari Telegram ID Kamu
1. Buka Telegram
2. Cari @userinfobot
3. Kirim pesan apa saja
4. Bot akan balas dengan ID kamu
