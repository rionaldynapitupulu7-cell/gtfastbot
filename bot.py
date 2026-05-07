import logging
import random
import string
import sqlite3
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# ===== KONFIGURASI =====
BOT_TOKEN = "8636129984:AAHNPZjd8aGBUPiXlcjLIugjCeWiNeam2kU"
ADMIN_IDS = [8695568315]  # Ganti dengan Telegram ID admin
TAX_PERCENT = 3  # Tax 3%

# ===== ROULETTE SEQUENCE =====
ROULETTE = [0,32,15,19,4,21,2,25,17,34,6,27,13,36,11,30,8,23,10,5,24,16,33,1,20,14,31,9,22,18,29,7,28,12,35,3,26]

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ===== DATABASE =====
def init_db():
    conn = sqlite3.connect('reme_bot.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        saldo INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS rooms (
        room_id TEXT PRIMARY KEY,
        player1_id INTEGER,
        player2_id INTEGER,
        taruhan INTEGER,
        total_ronde INTEGER,
        ronde_sekarang INTEGER DEFAULT 1,
        skor1 INTEGER DEFAULT 0,
        skor2 INTEGER DEFAULT 0,
        spin1 INTEGER DEFAULT -1,
        spin2 INTEGER DEFAULT -1,
        status TEXT DEFAULT 'waiting',
        chat_id INTEGER
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS topup (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        jumlah INTEGER,
        bukti TEXT,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()

def get_user(user_id, username=None):
    conn = sqlite3.connect('reme_bot.db')
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = c.fetchone()
    if not user:
        c.execute('INSERT INTO users (user_id, username, saldo) VALUES (?, ?, 0)', (user_id, username))
        conn.commit()
        c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = c.fetchone()
    conn.close()
    return user

def get_saldo(user_id):
    conn = sqlite3.connect('reme_bot.db')
    c = conn.cursor()
    c.execute('SELECT saldo FROM users WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def update_saldo(user_id, jumlah):
    conn = sqlite3.connect('reme_bot.db')
    c = conn.cursor()
    c.execute('UPDATE users SET saldo = saldo + ? WHERE user_id = ?', (jumlah, user_id))
    conn.commit()
    conn.close()

def set_saldo(user_id, jumlah):
    conn = sqlite3.connect('reme_bot.db')
    c = conn.cursor()
    c.execute('UPDATE users SET saldo = ? WHERE user_id = ?', (jumlah, user_id))
    conn.commit()
    conn.close()

def get_username(user_id):
    conn = sqlite3.connect('reme_bot.db')
    c = conn.cursor()
    c.execute('SELECT username FROM users WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else str(user_id)

# ===== HELPER =====
def generate_room_id():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))

def hitung_reme(angka):
    """Hitung nilai reme: jika >9, jumlahkan digit"""
    if angka <= 9:
        return angka
    digits = [int(d) for d in str(angka)]
    total = sum(digits)
    # Kalau masih > 9, jumlahkan lagi
    while total > 9:
        total = sum(int(d) for d in str(total))
    return total

def spin_roulette():
    return random.choice(ROULETTE)

def get_room_by_player(user_id):
    conn = sqlite3.connect('reme_bot.db')
    c = conn.cursor()
    c.execute('''SELECT * FROM rooms WHERE (player1_id = ? OR player2_id = ?) 
                 AND status IN ("waiting", "playing")''', (user_id, user_id))
    room = c.fetchone()
    conn.close()
    return room

def get_room(room_id):
    conn = sqlite3.connect('reme_bot.db')
    c = conn.cursor()
    c.execute('SELECT * FROM rooms WHERE room_id = ?', (room_id,))
    room = c.fetchone()
    conn.close()
    return room

def update_room(room_id, **kwargs):
    conn = sqlite3.connect('reme_bot.db')
    c = conn.cursor()
    for key, val in kwargs.items():
        c.execute(f'UPDATE rooms SET {key} = ? WHERE room_id = ?', (val, room_id))
    conn.commit()
    conn.close()

def delete_room(room_id):
    conn = sqlite3.connect('reme_bot.db')
    c = conn.cursor()
    c.execute('DELETE FROM rooms WHERE room_id = ?', (room_id,))
    conn.commit()
    conn.close()

# ===== HANDLERS =====

async def handle_reme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id
    text = update.message.text.strip()

    parts = text.split()
    if len(parts) != 3:
        await update.message.reply_text("❌ Format salah!\nGunakan: `.reme [taruhan] [ronde]`\nContoh: `.reme 5000 1r`", parse_mode='Markdown')
        return

    try:
        taruhan = int(parts[1])
        ronde_str = parts[2].lower().replace('r', '')
        total_ronde = int(ronde_str)
    except:
        await update.message.reply_text("❌ Format salah!\nContoh: `.reme 5000 1r`", parse_mode='Markdown')
        return

    if taruhan < 100:
        await update.message.reply_text("❌ Taruhan minimal 100!", parse_mode='Markdown')
        return

    if total_ronde < 1 or total_ronde > 10:
        await update.message.reply_text("❌ Ronde harus antara 1-10!", parse_mode='Markdown')
        return

    # Cek apakah player sudah di room lain
    existing = get_room_by_player(user.id)
    if existing:
        await update.message.reply_text("❌ Kamu sudah ada di room lain! Selesaikan dulu atau tunggu.", parse_mode='Markdown')
        return

    # Cek saldo
    get_user(user.id, user.username or user.first_name)
    saldo = get_saldo(user.id)
    if saldo < taruhan:
        await update.message.reply_text(f"❌ Saldo tidak cukup!\nSaldo kamu: *{saldo}*\nTaruhan: *{taruhan}*\n\nTop up dulu dengan command `.topup`", parse_mode='Markdown')
        return

    # Cek apakah ada room dengan taruhan & ronde sama yang waiting
    conn = sqlite3.connect('reme_bot.db')
    c = conn.cursor()
    c.execute('''SELECT * FROM rooms WHERE status = "waiting" AND taruhan = ? 
                 AND total_ronde = ? AND player2_id IS NULL AND chat_id = ?''',
              (taruhan, total_ronde, chat_id))
    waiting_room = c.fetchone()
    conn.close()

    if waiting_room:
        room_id = waiting_room[0]
        p1_id = waiting_room[1]

        if p1_id == user.id:
            await update.message.reply_text("❌ Kamu sudah membuat room ini!", parse_mode='Markdown')
            return

        # Join room
        update_saldo(user.id, -taruhan)
        update_saldo(p1_id, -taruhan)

        conn = sqlite3.connect('reme_bot.db')
        c = conn.cursor()
        c.execute('UPDATE rooms SET player2_id = ?, status = "playing" WHERE room_id = ?', (user.id, room_id))
        conn.commit()
        conn.close()

        p1_username = get_username(p1_id)
        msg = (
            f"🎰 *Room Reme Dimulai!*\n"
            f"• Room ID: `{room_id}`\n"
            f"• Player 1: @{p1_username}\n"
            f"• Player 2: @{user.username or user.first_name}\n"
            f"• Taruhan: *{taruhan}*\n"
            f"• Mode: *{total_ronde}r*\n\n"
            f"Kedua pemain ketik *.spinr* untuk mulai ronde 1!"
        )
        await update.message.reply_text(msg, parse_mode='Markdown')

    else:
        # Buat room baru
        room_id = generate_room_id()
        conn = sqlite3.connect('reme_bot.db')
        c = conn.cursor()
        c.execute('''INSERT INTO rooms (room_id, player1_id, taruhan, total_ronde, chat_id, status)
                     VALUES (?, ?, ?, ?, ?, "waiting")''',
                  (room_id, user.id, taruhan, total_ronde, chat_id))
        conn.commit()
        conn.close()

        username = user.username or user.first_name
        get_user(user.id, username)

        msg = (
            f"🎰 *Room Reme Dibuat*\n"
            f"• Room ID: `{room_id}`\n"
            f"• PLAYER: @{username}\n"
            f"• Taruhan: *{taruhan}*\n"
            f"• Mode: *{total_ronde}r*\n\n"
            f"Pemain lain silakan join dengan command yang sama:\n"
            f"*.reme {taruhan} {total_ronde}r*"
        )
        await update.message.reply_text(msg, parse_mode='Markdown')


async def handle_spinr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id

    room = get_room_by_player(user.id)
    if not room:
        await update.message.reply_text("❌ Kamu tidak sedang di room manapun!", parse_mode='Markdown')
        return

    room_id = room[0]
    p1_id = room[1]
    p2_id = room[2]
    taruhan = room[3]
    total_ronde = room[4]
    ronde_sekarang = room[5]
    skor1 = room[6]
    skor2 = room[7]
    spin1 = room[8]
    spin2 = room[9]
    status = room[10]

    if status != 'playing':
        await update.message.reply_text("❌ Room belum siap!", parse_mode='Markdown')
        return

    # Cek sudah spin belum di ronde ini
    if user.id == p1_id:
        if spin1 != -1:
            await update.message.reply_text("⏳ Kamu sudah spin! Tunggu lawan spin.", parse_mode='Markdown')
            return
        angka = spin_roulette()
        reme = hitung_reme(angka)
        update_room(room_id, spin1=angka)
        spin1 = angka

        username = user.username or user.first_name
        await update.message.reply_text(
            f"@{username} _*Spun the wheel and got {angka}🎰*_ REME ({reme})",
            parse_mode='Markdown'
        )

    elif user.id == p2_id:
        if spin2 != -1:
            await update.message.reply_text("⏳ Kamu sudah spin! Tunggu lawan spin.", parse_mode='Markdown')
            return
        angka = spin_roulette()
        reme = hitung_reme(angka)
        update_room(room_id, spin2=angka)
        spin2 = angka

        username = user.username or user.first_name
        await update.message.reply_text(
            f"@{username} _*Spun the wheel and got {angka}🎰*_ REME ({reme})",
            parse_mode='Markdown'
        )

    # Reload room untuk cek kedua sudah spin
    room = get_room(room_id)
    spin1 = room[8]
    spin2 = room[9]

    if spin1 != -1 and spin2 != -1:
        # Hitung hasil ronde
        reme1 = hitung_reme(spin1)
        reme2 = hitung_reme(spin2)

        p1_username = get_username(p1_id)
        p2_username = get_username(p2_id)

        result_msg = (
            f"🎮 *Ronde {ronde_sekarang}* (Room `{room_id}`)\n"
            f"@{p1_username}: {spin1} → {reme1}\n"
            f"@{p2_username}: {spin2} → {reme2}\n\n"
        )

        # Tentukan pemenang ronde
        # Khusus: angka 0 menang 3x (tapi di konteks PvP, kita pakai reme value 0 sebagai kekalahan)
        # Angka 0 dari spin = reme 0 = nilai terkecil

        if reme1 > reme2:
            skor1 += 1
            result_msg += f"🏆 Menang: @{p1_username}\n"
        elif reme2 > reme1:
            skor2 += 1
            result_msg += f"🏆 Menang: @{p2_username}\n"
        else:
            result_msg += f"🤝 Seri! Ronde ini tidak ada poin.\n"

        result_msg += f"📊 Skor: {skor1} - {skor2}"

        # Cek apakah match selesai
        if ronde_sekarang >= total_ronde:
            # Match selesai
            total_pot = taruhan * 2
            tax = int(total_pot * TAX_PERCENT / 100)
            hadiah = total_pot - tax

            if skor1 > skor2:
                pemenang_id = p1_id
                pemenang_username = p1_username
            elif skor2 > skor1:
                pemenang_id = p2_id
                pemenang_username = p2_username
            else:
                pemenang_id = None
                pemenang_username = None

            result_msg += f"\n\n🎉 *Match Selesai!* (Room `{room_id}`)\n"

            if pemenang_id:
                update_saldo(pemenang_id, hadiah)
                saldo_baru = get_saldo(pemenang_id)
                result_msg += (
                    f"Menang: @{pemenang_username}\n"
                    f"💰 Hadiah: Rp{hadiah:,} (Tax {TAX_PERCENT}% = Rp{tax:,})\n"
                    f"Saldo sekarang: {saldo_baru}"
                )
            else:
                # Seri total - kembalikan taruhan masing-masing
                update_saldo(p1_id, taruhan)
                update_saldo(p2_id, taruhan)
                result_msg += f"🤝 Match Seri! Taruhan dikembalikan."

            delete_room(room_id)
            await update.message.reply_text(result_msg, parse_mode='Markdown')

        else:
            # Lanjut ronde berikutnya
            update_room(room_id,
                        ronde_sekarang=ronde_sekarang + 1,
                        skor1=skor1,
                        skor2=skor2,
                        spin1=-1,
                        spin2=-1)

            result_msg += f"\n\nKedua pemain silakan ketik *.spinr* lagi untuk ronde berikutnya."
            await update.message.reply_text(result_msg, parse_mode='Markdown')


async def handle_saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or user.first_name)
    saldo = get_saldo(user.id)
    await update.message.reply_text(
        f"💰 *Saldo kamu:* Rp{saldo:,}",
        parse_mode='Markdown'
    )


async def handle_topup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()
    parts = text.split()

    if len(parts) < 2:
        await update.message.reply_text(
            "💳 *Cara Top Up:*\n\n"
            "1. Transfer ke DANA: `08xxxxxxxxxx` (a/n Owner)\n"
            "2. Ketik: `.topup [jumlah]`\n"
            "3. Kirim bukti transfer ke admin\n\n"
            "Contoh: `.topup 50000`\n\n"
            "⚠️ Saldo akan ditambah setelah admin konfirmasi.",
            parse_mode='Markdown'
        )
        return

    try:
        jumlah = int(parts[1])
    except:
        await update.message.reply_text("❌ Format salah! Contoh: `.topup 50000`", parse_mode='Markdown')
        return

    if jumlah < 5000:
        await update.message.reply_text("❌ Minimum top up Rp5.000!", parse_mode='Markdown')
        return

    get_user(user.id, user.username or user.first_name)

    conn = sqlite3.connect('reme_bot.db')
    c = conn.cursor()
    c.execute('INSERT INTO topup (user_id, jumlah) VALUES (?, ?)', (user.id, jumlah))
    topup_id = c.lastrowid
    conn.commit()
    conn.close()

    username = user.username or user.first_name
    await update.message.reply_text(
        f"✅ *Request Top Up Diterima!*\n\n"
        f"• ID Request: `#{topup_id}`\n"
        f"• Nama: @{username}\n"
        f"• Jumlah: Rp{jumlah:,}\n\n"
        f"📤 Sekarang kirim bukti transfer ke admin!\n"
        f"Saldo akan ditambah setelah dikonfirmasi.",
        parse_mode='Markdown'
    )

    # Notif ke admin
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                admin_id,
                f"📥 *Request Top Up Baru!*\n\n"
                f"• ID: `#{topup_id}`\n"
                f"• User: @{username} (`{user.id}`)\n"
                f"• Jumlah: Rp{jumlah:,}\n\n"
                f"Konfirmasi: `.konfirmasi {topup_id}`\n"
                f"Tolak: `.tolak {topup_id}`",
                parse_mode='Markdown'
            )
        except:
            pass


async def handle_konfirmasi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin konfirmasi top up"""
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        return

    text = update.message.text.strip()
    parts = text.split()

    if len(parts) < 2:
        await update.message.reply_text("Format: `.konfirmasi [id_topup]`", parse_mode='Markdown')
        return

    try:
        topup_id = int(parts[1])
    except:
        await update.message.reply_text("❌ ID tidak valid!", parse_mode='Markdown')
        return

    conn = sqlite3.connect('reme_bot.db')
    c = conn.cursor()
    c.execute('SELECT * FROM topup WHERE id = ? AND status = "pending"', (topup_id,))
    topup = c.fetchone()

    if not topup:
        conn.close()
        await update.message.reply_text("❌ Request tidak ditemukan atau sudah diproses!", parse_mode='Markdown')
        return

    topup_user_id = topup[1]
    jumlah = topup[2]

    c.execute('UPDATE topup SET status = "confirmed" WHERE id = ?', (topup_id,))
    conn.commit()
    conn.close()

    update_saldo(topup_user_id, jumlah)
    saldo_baru = get_saldo(topup_user_id)

    await update.message.reply_text(
        f"✅ Top up #{topup_id} dikonfirmasi!\nSaldo user ditambah Rp{jumlah:,}",
        parse_mode='Markdown'
    )

    try:
        await context.bot.send_message(
            topup_user_id,
            f"✅ *Top Up Berhasil!*\n\n"
            f"• Jumlah: Rp{jumlah:,}\n"
            f"• Saldo sekarang: Rp{saldo_baru:,}\n\n"
            f"Selamat bermain! 🎰",
            parse_mode='Markdown'
        )
    except:
        pass


async def handle_tolak(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin tolak top up"""
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        return

    text = update.message.text.strip()
    parts = text.split()

    if len(parts) < 2:
        await update.message.reply_text("Format: `.tolak [id_topup]`", parse_mode='Markdown')
        return

    try:
        topup_id = int(parts[1])
    except:
        await update.message.reply_text("❌ ID tidak valid!", parse_mode='Markdown')
        return

    conn = sqlite3.connect('reme_bot.db')
    c = conn.cursor()
    c.execute('SELECT * FROM topup WHERE id = ? AND status = "pending"', (topup_id,))
    topup = c.fetchone()

    if not topup:
        conn.close()
        await update.message.reply_text("❌ Request tidak ditemukan!", parse_mode='Markdown')
        return

    topup_user_id = topup[1]
    jumlah = topup[2]

    c.execute('UPDATE topup SET status = "rejected" WHERE id = ?', (topup_id,))
    conn.commit()
    conn.close()

    await update.message.reply_text(f"❌ Top up #{topup_id} ditolak!", parse_mode='Markdown')

    try:
        await context.bot.send_message(
            topup_user_id,
            f"❌ *Top Up Ditolak!*\n\n"
            f"• Jumlah: Rp{jumlah:,}\n\n"
            f"Hubungi admin untuk info lebih lanjut.",
            parse_mode='Markdown'
        )
    except:
        pass


async def handle_addsaldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin tambah saldo manual"""
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        return

    text = update.message.text.strip()
    parts = text.split()

    if len(parts) < 3:
        await update.message.reply_text("Format: `.addsaldo [user_id] [jumlah]`", parse_mode='Markdown')
        return

    try:
        target_id = int(parts[1])
        jumlah = int(parts[2])
    except:
        await update.message.reply_text("❌ Format salah!", parse_mode='Markdown')
        return

    get_user(target_id)
    update_saldo(target_id, jumlah)
    saldo_baru = get_saldo(target_id)

    await update.message.reply_text(
        f"✅ Saldo ditambah!\nUser: `{target_id}`\nJumlah: Rp{jumlah:,}\nSaldo baru: Rp{saldo_baru:,}",
        parse_mode='Markdown'
    )


async def handle_setsaldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin set saldo"""
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        return

    text = update.message.text.strip()
    parts = text.split()

    if len(parts) < 3:
        await update.message.reply_text("Format: `.setsaldo [user_id] [jumlah]`", parse_mode='Markdown')
        return

    try:
        target_id = int(parts[1])
        jumlah = int(parts[2])
    except:
        await update.message.reply_text("❌ Format salah!", parse_mode='Markdown')
        return

    get_user(target_id)
    set_saldo(target_id, jumlah)

    await update.message.reply_text(
        f"✅ Saldo diset!\nUser: `{target_id}`\nSaldo baru: Rp{jumlah:,}",
        parse_mode='Markdown'
    )


async def handle_ceksaldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin cek saldo user"""
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        return

    text = update.message.text.strip()
    parts = text.split()

    if len(parts) < 2:
        await update.message.reply_text("Format: `.ceksaldo [user_id]`", parse_mode='Markdown')
        return

    try:
        target_id = int(parts[1])
    except:
        await update.message.reply_text("❌ ID tidak valid!", parse_mode='Markdown')
        return

    get_user(target_id)
    saldo = get_saldo(target_id)
    username = get_username(target_id)

    await update.message.reply_text(
        f"👤 User: @{username} (`{target_id}`)\n💰 Saldo: Rp{saldo:,}",
        parse_mode='Markdown'
    )


async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🎰 *Bot Reme - Panduan*\n\n"
        "*Game:*\n"
        "• `.reme [taruhan] [ronde]` - Buat/join room Reme\n"
        "• `.spinr` - Spin roulette di room aktif\n\n"
        "*Saldo:*\n"
        "• `.saldo` - Cek saldo kamu\n"
        "• `.topup [jumlah]` - Request top up saldo\n\n"
        "*Contoh:*\n"
        "`.reme 5000 1r` - Buat room taruhan 5000 1 ronde\n"
        "`.reme 10000 3r` - Buat room taruhan 10000 3 ronde\n\n"
        "*Aturan Reme:*\n"
        "• Angka > 9 dijumlah digitnya (34 → 3+4 = 7)\n"
        "• Angka terbesar menang\n"
        "• Tax 3% dari total pot\n"
        "• Seri = ronde tidak ada poin"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip().lower()

    if text.startswith('.reme'):
        await handle_reme(update, context)
    elif text.startswith('.spinr'):
        await handle_spinr(update, context)
    elif text.startswith('.saldo'):
        await handle_saldo(update, context)
    elif text.startswith('.topup'):
        await handle_topup(update, context)
    elif text.startswith('.konfirmasi'):
        await handle_konfirmasi(update, context)
    elif text.startswith('.tolak'):
        await handle_tolak(update, context)
    elif text.startswith('.addsaldo'):
        await handle_addsaldo(update, context)
    elif text.startswith('.setsaldo'):
        await handle_setsaldo(update, context)
    elif text.startswith('.ceksaldo'):
        await handle_ceksaldo(update, context)
    elif text in ['.help', '.start', '.menu']:
        await handle_help(update, context)


def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("✅ Bot Reme berjalan...")
    app.run_polling()


if __name__ == '__main__':
    main()