const express = require('express');
const cors = require('cors');
const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const path = require('path');

const app = express();
app.use(cors());
app.use(express.json());

// Persistent session - NEVER LOGOUT!
const client = new Client({
    authStrategy: new LocalAuth({
        dataPath: path.join(__dirname, 'whatsapp-session')
    }),
    puppeteer: {
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    }
});

let isReady = false;
let currentQR = null;

client.on('qr', (qr) => {
    currentQR = qr;
    isReady = false;
    console.log('\n📱 SCAN QR CODE:');
    qrcode.generate(qr, { small: true });
});

client.on('ready', () => {
    isReady = true;
    currentQR = null;
    console.log('\n✅ WHATSAPP CONNECTED! WILL STAY CONNECTED FOREVER!\n');
});

client.on('disconnected', () => {
    isReady = false;
    console.log('⚠️ Disconnected, reconnecting...');
    client.initialize();
});

client.initialize();

// Routes
app.get('/status', (req, res) => {
    res.json({ connected: isReady, qr: currentQR });
});

app.post('/send', async (req, res) => {
    const { to, message } = req.body;
    if (!isReady) {
        return res.status(503).json({ success: false, error: 'WhatsApp not connected' });
    }
    try {
        let phone = to.toString().replace(/\D/g, '');
        if (phone.length === 10) phone = '91' + phone;
        if (!phone.endsWith('@c.us')) phone = phone + '@c.us';
        await client.sendMessage(phone, message);
        res.json({ success: true });
    } catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});

const PORT = 3001;
app.listen(PORT, () => {
    console.log(`\n🚀 WhatsApp Bridge running on port ${PORT}`);
    console.log(`💡 Scan QR once - NEVER AGAIN!\n`);
});