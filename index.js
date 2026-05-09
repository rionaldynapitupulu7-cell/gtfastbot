const { default: makeWASocket, useMultiFileAuthState, DisconnectReason, fetchLatestBaileysVersion } = require('@whiskeysockets/baileys');
const { Boom } = require('@hapi/boom');
const fs = require('fs');
const pino = require('pino');

// ========================
// DATABASE (file JSON)
// ========================
const DB_FILE = './database.json';

function loadDB() {
  if (!fs.existsSync(DB_FILE)) {
    fs.writeFileSync(DB_FILE, JSON.stringify({ users: {}, rooms: {}, transactions: [] }));
  }
  return JSON.parse(fs.readFileSync(DB_FILE));
}

function saveDB(db) {
  fs.writeFileSync(DB_FILE, JSON.stringify(db, null, 2));
}

// ========================
// CONFIG
// ========================
const CONFIG = {
  prefix: '.',
  tax: 0.03,          // 3%
  minSaldo: 2000,
  minTopup: 5000,
  minWD: 10000,
  // Isi nomor owner & staff (format: 628xxxxxxxxxx)
  owners: ['628xxxxxxxxxx'],   // <-- GANTI dengan nomor HP owner
  staffs: [],                  // <-- Tambah nomor staff di sini
  resellers: [],               // <-- Tambah nomor reseller di sini
  botName: 'GT Casino Bot',
  groupOnly: true,
};

// ========================
// HELPER
// ========================
function getNum(jid) {
  return jid.split('@')[0];
}

function formatRp(angka) {
  const num = parseFloat(angka) || 0;
  // Format dengan titik ribuan dan koma desimal (Indonesian style)
  return 'Rp' + num.toLocaleString('id-ID', { minimumFractionDigits: 0, maximumFractionDigits: 2 });
}

function parseNominal(str) {
  str = str.toLowerCase().trim();
  if (str.endsWith('k')) return parseFloat(str) * 1000;
  if (str.endsWith('rb')) return parseFloat(str) * 1000;
  if (str.endsWith('jt') || str.endsWith('m')) return parseFloat(str) * 1000000;
  return parseFloat(str.replace(/[^0-9.]/g, '')) || 0;
}

function randomWheel() {
  return Math.floor(Math.random() * 36) + 1; // 1-36
}

function wheelToReme(wheel) {
  return Math.floor(wheel / 4);
}

function generateRoomID() {
  const chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
  let id = 'moy';
  for (let i = 0; i < 9; i++) id += chars[Math.floor(Math.random() * chars.length)];
  return id;
}

function isOwner(jid) {
  return CONFIG.owners.includes(getNum(jid));
}

function isStaff(jid) {
  return CONFIG.staffs.includes(getNum(jid)) || isOwner(jid);
}

function isReseller(jid) {
  return CONFIG.resellers.includes(getNum(jid)) || isStaff(jid);
}

function getUser(db, jid) {
  const num = getNum(jid);
  if (!db.users[num]) {
    db.users[num] = { saldo: 0, nama: num, menang: 0, kalah: 0 };
  }
  return db.users[num];
}

function mention(jid) {
  return '@' + getNum(jid);
}

// ========================
// MAIN BOT
// ========================
async function startBot() {
  const { state, saveCreds } = await useMultiFileAuthState('./auth_info');
  const { version } = await fetchLatestBaileysVersion();

  const sock = makeWASocket({
    version,
    auth: state,
    logger: pino({ level: 'silent' }),
    printQRInTerminal: true,
    browser: ['GT Casino Bot', 'Chrome', '1.0.0'],
  });

  sock.ev.on('creds.update', saveCreds);

  sock.ev.on('connection.update', (update) => {
    const { connection, lastDisconnect } = update;
    if (connection === 'close') {
      const shouldReconnect = (lastDisconnect?.error instanceof Boom)
        ? lastDisconnect.error.output?.statusCode !== DisconnectReason.loggedOut
        : true;
      console.log('Koneksi terputus, reconnect:', shouldReconnect);
      if (shouldReconnect) startBot();
    } else if (connection === 'open') {
      console.log('✅ Bot terhubung ke WhatsApp!');
    }
  });

  sock.ev.on('messages.upsert', async ({ messages }) => {
    const msg = messages[0];
    if (!msg.message || msg.key.fromMe) return;

    const from = msg.key.remoteJid;
    const isGroup = from.endsWith('@g.us');

    // Hanya proses pesan dari grup
    if (CONFIG.groupOnly && !isGroup) return;

    const senderJid = isGroup ? msg.key.participant : msg.key.remoteJid;
    const body = msg.message?.conversation || msg.message?.extendedTextMessage?.text || '';
    if (!body.startsWith(CONFIG.prefix)) return;

    const args = body.slice(CONFIG.prefix.length).trim().split(/\s+/);
    const cmd = args[0].toLowerCase();
    const rest = args.slice(1);

    // Fungsi reply
    const reply = async (text, mentions = []) => {
      await sock.sendMessage(from, {
        text,
        mentions,
      }, { quoted: msg });
    };

    const db = loadDB();
    const user = getUser(db, senderJid);

    // ============================
    // CMD: .cu [@user]
    // ============================
    if (cmd === 'cu') {
      let targetJid = senderJid;
      if (msg.message?.extendedTextMessage?.contextInfo?.mentionedJid?.length > 0) {
        targetJid = msg.message.extendedTextMessage.contextInfo.mentionedJid[0];
      }
      const target = getUser(db, targetJid);
      const nama = target.nama || mention(targetJid);
      saveDB(db);
      await reply(
        `💰 *Cek Uang*\n• 👤 Nama  : ${mention(targetJid)}\n• 💵 Saldo : *${formatRp(target.saldo)}*`,
        [targetJid]
      );
    }

    // ============================
    // CMD: .lb (leaderboard)
    // ============================
    else if (cmd === 'lb') {
      const sorted = Object.entries(db.users)
        .sort(([, a], [, b]) => b.saldo - a.saldo)
        .slice(0, 10);

      const totalSaldo = Object.values(db.users).reduce((a, b) => a + (b.saldo || 0), 0);

      let text = `🏆 *LEADERBOARD GT CASINO*\n\n`;
      sorted.forEach(([num, u], i) => {
        const icon = i === 0 ? '👑' : '🔹';
        text += `${i + 1}. ${icon} @~${u.nama || num}\n   💰 ${formatRp(u.saldo)}\n\n`;
      });
      text += `💼 *JUMLAH ALL SALDO* : ${formatRp(totalSaldo)}`;

      await reply(text);
    }

    // ============================
    // CMD: .room (lihat room open)
    // ============================
    else if (cmd === 'room') {
      const openRooms = Object.entries(db.rooms).filter(([, r]) => r.status === 'waiting' && r.game === 'reme');
      if (openRooms.length === 0) {
        return await reply('📋 Tidak ada room REME yang terbuka saat ini.');
      }
      let text = `📋 *DAFTAR ROOM OPEN*\n\n`;
      openRooms.forEach(([id, r]) => {
        text += `🎰 *REME PVP*\n`;
        text += `Room : ${id}\n`;
        text += `Player : @${r.player1}\n`;
        text += `Bet  : ${formatRp(r.bet)}\n`;
        text += `Mode : ${r.ronde}R\n`;
        text += `Join : .reme ${r.bet/1000}k ${r.ronde}r\n`;
        text += `Cancel (Host): .creme\n\n`;
      });
      await reply(text.trim());
    }

    // ============================
    // CMD: .reme <nominal> <xr>
    // ============================
    else if (cmd === 'reme') {
      if (rest.length < 2) {
        return await reply('❌ Format salah!\nContoh: .reme 20k 1r');
      }

      const bet = parseNominal(rest[0]);
      const rondeStr = rest[1].toLowerCase();
      const ronde = parseInt(rondeStr.replace('r', ''));

      if (isNaN(bet) || bet <= 0) return await reply('❌ Nominal taruhan tidak valid!');
      if (isNaN(ronde) || ronde <= 0) return await reply('❌ Format ronde tidak valid! Contoh: 1r, 3r, 5r');
      if (bet < CONFIG.minSaldo) return await reply(`❌ Minimum taruhan ${formatRp(CONFIG.minSaldo)}`);
      if (user.saldo < bet) return await reply(`❌ Saldo kamu tidak cukup!\nSaldo: ${formatRp(user.saldo)}\nTaruhan: ${formatRp(bet)}`);

      const senderNum = getNum(senderJid);

      // Cek apakah sudah ada room yang cocok (join)
      const matchRoom = Object.entries(db.rooms).find(([, r]) =>
        r.status === 'waiting' &&
        r.game === 'reme' &&
        r.bet === bet &&
        r.ronde === ronde &&
        r.player1 !== senderNum
      );

      if (matchRoom) {
        // JOIN room
        const [roomId, room] = matchRoom;
        room.player2 = senderNum;
        room.status = 'spinning';
        room.spins = {};
        room.rondeSelesai = 0;
        room.skorP1 = 0;
        room.skorP2 = 0;
        room.rondeSkors = [];

        // Kurangi saldo kedua pemain
        db.users[room.player1].saldo -= bet;
        db.users[senderNum].saldo -= bet;

        saveDB(db);

        await reply(
          `✅ *Lawan Telah Join!*\n• Room ID : ${roomId}\n• PLAYER1 : @${room.player1}\n• PLAYER2 : @${senderNum}\n• Taruhan : ${formatRp(bet)}\n• Mode : ${ronde}R\n\nKedua pemain silakan ketik *.spinr* untuk memulai ronde 1.`,
          [room.player1 + '@s.whatsapp.net', senderJid]
        );
      } else {
        // BUAT room baru
        // Cek apakah sudah ada room dari player ini
        const existing = Object.entries(db.rooms).find(([, r]) =>
          r.status === 'waiting' && r.player1 === senderNum && r.game === 'reme'
        );
        if (existing) return await reply('❌ Kamu sudah punya room yang terbuka! Ketik .creme untuk membatalkan.');

        const roomId = generateRoomID();
        db.rooms[roomId] = {
          game: 'reme',
          player1: senderNum,
          player2: null,
          bet,
          ronde,
          status: 'waiting',
          group: from,
          spins: {},
          rondeSelesai: 0,
          skorP1: 0,
          skorP2: 0,
          rondeSkors: [],
          createdAt: Date.now(),
        };

        saveDB(db);

        await reply(
          `🎰 *Room REME Dibuat*\n• Room ID : ${roomId}\n• PLAYER : ${mention(senderJid)}\n• Taruhan : ${formatRp(bet)}\n• Mode : ${ronde}R\n\nPemain lain silakan join dengan command yang sama:\n*.reme ${rest[0]} ${rest[1]}*`,
          [senderJid]
        );
      }
    }

    // ============================
    // CMD: .spinr
    // ============================
    else if (cmd === 'spinr') {
      const senderNum = getNum(senderJid);

      // Cari room dimana player ini ada dan status spinning
      const myRoom = Object.entries(db.rooms).find(([, r]) =>
        r.status === 'spinning' &&
        r.game === 'reme' &&
        (r.player1 === senderNum || r.player2 === senderNum) &&
        r.group === from
      );

      if (!myRoom) return await reply('❌ Kamu tidak sedang dalam room REME aktif!');

      const [roomId, room] = myRoom;
      const currentRonde = room.rondeSelesai + 1;
      const rondeKey = `ronde_${currentRonde}`;

      if (!room.spins[rondeKey]) room.spins[rondeKey] = {};

      if (room.spins[rondeKey][senderNum]) {
        return await reply('❌ Kamu sudah spin di ronde ini! Tunggu lawan spin.');
      }

      // Spin!
      const wheel = randomWheel();
      const reme = wheelToReme(wheel);
      room.spins[rondeKey][senderNum] = { wheel, reme };

      saveDB(db);

      await reply(
        `${mention(senderJid)} _*Spun the wheel and got ${wheel}🎰*_ REME (${reme})`,
        [senderJid]
      );

      // Cek apakah kedua pemain sudah spin
      const spinsRonde = room.spins[rondeKey];
      if (spinsRonde[room.player1] && spinsRonde[room.player2]) {
        const sp1 = spinsRonde[room.player1];
        const sp2 = spinsRonde[room.player2];

        let rondeWinner = null;
        let rondeText = '';

        if (sp1.reme > sp2.reme) {
          room.skorP1++;
          rondeWinner = room.player1;
        } else if (sp2.reme > sp1.reme) {
          room.skorP2++;
          rondeWinner = room.player2;
        } else {
          rondeText = '\n🤝 Ronde ini DRAW! Tidak ada poin.';
        }

        room.rondeSelesai++;

        const p1jid = room.player1 + '@s.whatsapp.net';
        const p2jid = room.player2 + '@s.whatsapp.net';

        let resultText = `🎮 *Ronde ${currentRonde}* (Room ${roomId})\n`;
        resultText += `@${room.player1}: ${sp1.wheel} → ${sp1.reme}\n`;
        resultText += `@${room.player2}: ${sp2.wheel} → ${sp2.reme}\n\n`;

        if (rondeWinner) {
          resultText += `🏆 Menang: @${rondeWinner}\n`;
        }
        resultText += `📊 Skor: ${room.skorP1} - ${room.skorP2}${rondeText}`;

        // Cek apakah match selesai
        const halfRonde = Math.ceil(room.ronde / 2);
        const matchSelesai = room.rondeSelesai >= room.ronde ||
          room.skorP1 >= halfRonde || room.skorP2 >= halfRonde;

        if (matchSelesai) {
          let winner = null;
          if (room.skorP1 > room.skorP2) winner = room.player1;
          else if (room.skorP2 > room.skorP1) winner = room.player2;

          if (winner) {
            const loser = winner === room.player1 ? room.player2 : room.player1;
            const totalPot = room.bet * 2;
            const tax = Math.floor(totalPot * CONFIG.tax);
            const hadiah = totalPot - tax;

            db.users[winner].saldo += hadiah;
            db.users[winner].menang = (db.users[winner].menang || 0) + 1;
            db.users[loser].kalah = (db.users[loser].kalah || 0) + 1;

            const saldoWinner = db.users[winner].saldo;

            resultText += `\n\n🎉 *Match selesai!* (Room ${roomId})\n`;
            resultText += `Menang: @${winner}\n`;
            resultText += `💰 Hadiah: ${formatRp(hadiah)} (Tax 3% = ${formatRp(tax)})\n`;
            resultText += `Saldo sekarang: ${formatRp(saldoWinner)}`;
          } else {
            // Draw - kembalikan saldo
            db.users[room.player1].saldo += room.bet;
            db.users[room.player2].saldo += room.bet;

            resultText += `\n\n🤝 *Match DRAW!* (Room ${roomId})\n`;
            resultText += `Saldo dikembalikan ke masing-masing pemain.`;
          }

          delete db.rooms[roomId];
        } else {
          resultText += `\n\nKedua pemain ketik *.spinr* untuk ronde ${room.rondeSelesai + 1}.`;
        }

        saveDB(db);
        await sock.sendMessage(from, {
          text: resultText,
          mentions: [p1jid, p2jid],
        });
      }
    }

    // ============================
    // CMD: .creme (cancel room)
    // ============================
    else if (cmd === 'creme') {
      const senderNum = getNum(senderJid);
      const myRoom = Object.entries(db.rooms).find(([, r]) =>
        r.player1 === senderNum && r.status === 'waiting' && r.game === 'reme' && r.group === from
      );

      if (!myRoom) return await reply('❌ Kamu tidak punya room yang bisa dibatalkan!');

      const [roomId] = myRoom;
      delete db.rooms[roomId];
      saveDB(db);

      await reply('✅ Room REME dibatalkan. Saldo dikembalikan.');
    }

    // ============================
    // CMD: .topup @user <nominal> (owner/staff/reseller)
    // ============================
    else if (cmd === 'topup') {
      if (!isReseller(senderJid)) return await reply('❌ Kamu tidak punya akses perintah ini!');

      const mentionedJid = msg.message?.extendedTextMessage?.contextInfo?.mentionedJid?.[0];
      if (!mentionedJid) return await reply('❌ Tag user yang mau ditopup!\nContoh: .topup @user 20k');

      const nominal = parseNominal(rest[rest.length - 1]);
      if (!nominal || nominal < CONFIG.minTopup) return await reply(`❌ Minimum topup ${formatRp(CONFIG.minTopup)}`);

      const target = getUser(db, mentionedJid);
      const saldobefore = target.saldo;
      target.saldo += nominal;

      db.transactions.push({
        type: 'topup',
        from: getNum(senderJid),
        to: getNum(mentionedJid),
        nominal,
        time: Date.now(),
      });

      saveDB(db);

      await reply(
        `✅ *Topup Berhasil!*\n• 👤 User : ${mention(mentionedJid)}\n• 💵 Nominal : ${formatRp(nominal)}\n• 📊 Saldo : ${formatRp(saldobefore)} → ${formatRp(target.saldo)}`,
        [mentionedJid]
      );
    }

    // ============================
    // CMD: .kurang @user <nominal> (owner/staff)
    // ============================
    else if (cmd === 'kurang') {
      if (!isStaff(senderJid)) return await reply('❌ Kamu tidak punya akses perintah ini!');

      const mentionedJid = msg.message?.extendedTextMessage?.contextInfo?.mentionedJid?.[0];
      if (!mentionedJid) return await reply('❌ Tag user dulu!\nContoh: .kurang @user 10k');

      const nominal = parseNominal(rest[rest.length - 1]);
      if (!nominal) return await reply('❌ Masukkan nominal yang valid!');

      const target = getUser(db, mentionedJid);
      if (target.saldo < nominal) return await reply(`❌ Saldo user tidak cukup! Saldo: ${formatRp(target.saldo)}`);

      const saldobefore = target.saldo;
      target.saldo -= nominal;
      saveDB(db);

      await reply(
        `✅ *Kurangi Saldo Berhasil!*\n• 👤 User : ${mention(mentionedJid)}\n• 💵 Nominal : -${formatRp(nominal)}\n• 📊 Saldo : ${formatRp(saldobefore)} → ${formatRp(target.saldo)}`,
        [mentionedJid]
      );
    }

    // ============================
    // CMD: .wd <nominal> (request withdraw)
    // ============================
    else if (cmd === 'wd') {
      const nominal = parseNominal(rest[0]);
      if (!nominal || nominal < CONFIG.minWD) return await reply(`❌ Minimum withdraw ${formatRp(CONFIG.minWD)}`);
      if (user.saldo < nominal) return await reply(`❌ Saldo tidak cukup! Saldo kamu: ${formatRp(user.saldo)}`);

      user.saldo -= nominal;

      db.transactions.push({
        type: 'wd_request',
        from: getNum(senderJid),
        nominal,
        status: 'pending',
        time: Date.now(),
      });

      saveDB(db);

      await reply(
        `✅ *Request Withdraw Dikirim!*\n• 👤 User : ${mention(senderJid)}\n• 💵 Nominal : ${formatRp(nominal)}\n• 📊 Saldo sekarang : ${formatRp(user.saldo)}\n\nTunggu konfirmasi owner/staff ya! 🙏`,
        [senderJid]
      );
    }

    // ============================
    // CMD: .setnama <nama> (ganti nama)
    // ============================
    else if (cmd === 'setnama') {
      const nama = rest.join(' ').trim();
      if (!nama) return await reply('❌ Masukkan nama!\nContoh: .setnama Alif');
      user.nama = nama;
      saveDB(db);
      await reply(`✅ Nama berhasil diubah menjadi *${nama}*`);
    }

    // ============================
    // CMD: .addstaff @user (owner only)
    // ============================
    else if (cmd === 'addstaff') {
      if (!isOwner(senderJid)) return await reply('❌ Hanya owner yang bisa!');
      const mentionedJid = msg.message?.extendedTextMessage?.contextInfo?.mentionedJid?.[0];
      if (!mentionedJid) return await reply('❌ Tag user dulu!');
      const num = getNum(mentionedJid);
      if (!CONFIG.staffs.includes(num)) CONFIG.staffs.push(num);
      // Simpan ke config file
      fs.writeFileSync('./config_runtime.json', JSON.stringify({ staffs: CONFIG.staffs, resellers: CONFIG.resellers }, null, 2));
      await reply(`✅ ${mention(mentionedJid)} ditambahkan sebagai Staff!`, [mentionedJid]);
    }

    // ============================
    // CMD: .addreseller @user (owner/staff only)
    // ============================
    else if (cmd === 'addreseller') {
      if (!isStaff(senderJid)) return await reply('❌ Hanya owner/staff yang bisa!');
      const mentionedJid = msg.message?.extendedTextMessage?.contextInfo?.mentionedJid?.[0];
      if (!mentionedJid) return await reply('❌ Tag user dulu!');
      const num = getNum(mentionedJid);
      if (!CONFIG.resellers.includes(num)) CONFIG.resellers.push(num);
      fs.writeFileSync('./config_runtime.json', JSON.stringify({ staffs: CONFIG.staffs, resellers: CONFIG.resellers }, null, 2));
      await reply(`✅ ${mention(mentionedJid)} ditambahkan sebagai Reseller!`, [mentionedJid]);
    }

    // ============================
    // CMD: .menu / .help
    // ============================
    else if (cmd === 'menu' || cmd === 'help') {
      const isOwnerUser = isOwner(senderJid);
      const isStaffUser = isStaff(senderJid);
      const isResellerUser = isReseller(senderJid);

      let text = `🎰 *GT CASINO BOT*\n`;
      text += `━━━━━━━━━━━━━━━━\n\n`;
      text += `👤 *PLAYER*\n`;
      text += `• .reme <nominal> <xr> — Buat/join room REME\n`;
      text += `• .spinr — Spin roulette di room\n`;
      text += `• .creme — Batalkan room REME\n`;
      text += `• .room — Lihat room tersedia\n`;
      text += `• .cu [@user] — Cek saldo\n`;
      text += `• .lb — Leaderboard\n`;
      text += `• .wd <nominal> — Request withdraw\n`;
      text += `• .setnama <nama> — Ganti nama\n`;

      if (isResellerUser) {
        text += `\n💼 *RESELLER*\n`;
        text += `• .topup @user <nominal> — Topup saldo user\n`;
      }

      if (isStaffUser) {
        text += `\n🛡️ *STAFF*\n`;
        text += `• .kurang @user <nominal> — Kurangi saldo\n`;
        text += `• .addreseller @user — Tambah reseller\n`;
      }

      if (isOwnerUser) {
        text += `\n👑 *OWNER*\n`;
        text += `• .addstaff @user — Tambah staff\n`;
      }

      text += `\n━━━━━━━━━━━━━━━━\n`;
      text += `_Prefix: ${CONFIG.prefix}_`;

      await reply(text);
    }
  });
}

// Load runtime config kalau ada
if (fs.existsSync('./config_runtime.json')) {
  const rt = JSON.parse(fs.readFileSync('./config_runtime.json'));
  if (rt.staffs) CONFIG.staffs = rt.staffs;
  if (rt.resellers) CONFIG.resellers = rt.resellers;
}

startBot();
