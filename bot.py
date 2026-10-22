# ============================================================
# TELEGRAM BOT
# SAFE API + FORCE SUB + ADMIN PANEL + CREDITS + REFERRALS
# ============================================================

import re
import json
import os
import asyncio
import sqlite3
import secrets
import string
import aiohttp

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    KeyboardButton
)

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ============================================================
# 1. BUTTON STYLE HACK (FROM REFERENCE CODE)
# ============================================================
class _StyledKB(KeyboardButton):
    """KeyboardButton subclass with compatible serialization."""
    def __init__(self, text, style=None, **kwargs):
        super().__init__(text=text, **kwargs)
        self._button_style = style

    def to_dict(self, *args, **kwargs):
        data = super().to_dict(*args, **kwargs)
        if self._button_style:
            data["style"] = self._button_style
        return data


# ============================================================
# 2. CONFIG
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "8888531795:AAG4ZZib6oLpPN34AHgmAewtlvcIZFS8XJU").strip()

ADMIN_IDS = {
    8742883635
}

FORCE_CHANNELS = [
    "@altaf_upgraded",
    "@darkercoder",
]

# ============================================================
# 3. API CONFIG
# ============================================================
DEFAULT_API_URLS = {
    "Number": "https://nmdllpezcocquamhgpmb.supabase.co/functions/v1/lookup?number={value}",
    "Vehicle": "https://sbsakib.eu.cc/apis/vehicle_besic?key=Demo&vehicle={value}",
    "IFSC": "https://sbsakib.eu.cc/apis/ifsc_info?key=Demo&ifsc={value}",
    "IP": "https://sbsakib.eu.cc/apis/ip_info?key=Demo&ip={value}",
    "PIN": "https://sbsakib.eu.cc/apis/pincode_info?key=Demo&pincode={value}",
    "GST": "https://anon-gst-info.vercel.app/gstin?gstin={value}&key=anon404",
    "Aadhaar": "https://dark-info.site/familyinfo/api.php?key=JSON-4325&aadhar={value}",
    "GitHub": "https://sbsakib.eu.cc/apis/github_info?key=Demo&username={value}",
    "Snapchat": "https://petro-snap-info-api.vercel.app/api?username={value}&key=PETRO",
    "Truecaller": "https://sbsakib.eu.cc/apis/pk-info-v2?key=Demo&num={value}",
    "Pakistan_No": "https://sbsakib.eu.cc/apis/pk-info-v2?key=Demo&num={value}",
    "Vehicle_to_Num": "https://sbsakib.eu.cc/apis/vehicle_besic?key=Demo&vehicle={value}",
    "TG_to_Number": "https://tg2num-botadminshere.vercel.app/?id={value}",
    "UPI_Info": "https://sbsakib.eu.cc/apis/upi_info?key=Demo&upi={value}",
    "Aadhaar_to_PAN": "https://anon-pan-info.vercel.app/aadhar?key=temppanx2408&id={value}",
}

API_LABELS = {
    "Number": "📞 Number",
    "Vehicle": "🚗 Vehicle",
    "IFSC": "🏦 IFSC",
    "IP": "🌐 IP",
    "PIN": "📮 PIN",
    "GST": "🏢 GST",
    "Aadhaar": "🆔 Aadhaar",
    "GitHub": "🐙 GitHub",
    "Snapchat": "👻 Snapchat",
    "Truecaller": "📱 Truecaller",
    "Pakistan_No": "🇵🇰 Pakistan No",
    "Vehicle_to_Num": "🔢 Vehicle to Num",
    "TG_to_Number": "🆔 TG to Number",
    "UPI_Info": "💰 UPI Info",
    "Aadhaar_to_PAN": "🪪 Aadhaar to PAN",
}

REFERRAL_REWARD = 2
API_COST = 1
DB_FILE = "bot.db"


# ============================================================
# 4. DATABASE
# ============================================================
def db():
    return sqlite3.connect(DB_FILE)

def init_db():
    con = db()
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            credits INTEGER DEFAULT 0,
            referred_by INTEGER,
            referral_rewarded INTEGER DEFAULT 0,
            banned INTEGER DEFAULT 0,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS gift_codes (
            code TEXT PRIMARY KEY,
            credits INTEGER NOT NULL,
            max_uses INTEGER NOT NULL DEFAULT 1,
            uses INTEGER NOT NULL DEFAULT 0,
            used_by INTEGER,
            used_at TIMESTAMP
        )
    """)
    for column, definition in (
        ("max_uses", "INTEGER NOT NULL DEFAULT 1"),
        ("uses", "INTEGER NOT NULL DEFAULT 0"),
    ):
        try:
            cur.execute(f"ALTER TABLE gift_codes ADD COLUMN {column} {definition}")
        except sqlite3.OperationalError:
            pass

    cur.execute("""
        CREATE TABLE IF NOT EXISTS api_configs (
            name TEXT PRIMARY KEY,
            url TEXT NOT NULL DEFAULT '',
            emoji TEXT NOT NULL DEFAULT '🔹'
        )
    """)
    # Migrate existing databases without losing saved API URLs.
    try:
        cur.execute("ALTER TABLE api_configs ADD COLUMN emoji TEXT NOT NULL DEFAULT '🔹'")
    except sqlite3.OperationalError:
        pass
    for name, url in DEFAULT_API_URLS.items():
        cur.execute("INSERT OR IGNORE INTO api_configs(name, url) VALUES (?, ?)", (name, url))
    
    cur.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    cur.execute("INSERT OR IGNORE INTO settings(key, value) VALUES ('maintenance', '0')")
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS gift_redemptions (
            code TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            redeemed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (code, user_id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS referral_rewards (
            referred_user_id INTEGER PRIMARY KEY,
            referrer_id INTEGER NOT NULL,
            rewarded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.commit()
    con.close()

def register_user(user, referrer=None):
    con = db()
    cur = con.cursor()
    cur.execute("SELECT user_id FROM users WHERE user_id=?", (user.id,))
    if not cur.fetchone():
        cur.execute("INSERT INTO users (user_id, username, first_name, referred_by) VALUES (?, ?, ?, ?)", 
                    (user.id, user.username or "", user.first_name or "", referrer))
    else:
        cur.execute("UPDATE users SET username=?, first_name=? WHERE user_id=?", 
                    (user.username or "", user.first_name or "", user.id))
    con.commit()
    con.close()

def is_banned(user_id):
    con = db()
    cur = con.cursor()
    cur.execute("SELECT banned FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    con.close()
    return bool(row and row[0])

def get_credits(user_id):
    con = db()
    cur = con.cursor()
    cur.execute("SELECT credits FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    con.close()
    return row[0] if row else 0

def get_setting(key, default=""):
    con = db()
    cur = con.cursor()
    cur.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = cur.fetchone()
    con.close()
    return row[0] if row else default

def set_setting(key, value):
    con = db()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO settings(key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value))
    )
    con.commit()
    con.close()

def maintenance_enabled():
    return get_setting("maintenance", "0") == "1"

def get_api_url(name):
    con = db()
    cur = con.cursor()
    cur.execute("SELECT url FROM api_configs WHERE name=?", (name,))
    row = cur.fetchone()
    con.close()
    return row[0] if row else ""

def set_api_url(name, url, emoji="🔹"):
    con = db()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO api_configs(name, url, emoji) VALUES (?, ?, ?) "
        "ON CONFLICT(name) DO UPDATE SET url=excluded.url, emoji=excluded.emoji",
        (name, url, emoji or "🔹")
    )
    con.commit()
    con.close()

def get_api_emoji(name):
    con = db()
    cur = con.cursor()
    cur.execute("SELECT emoji FROM api_configs WHERE name=?", (name,))
    row = cur.fetchone()
    con.close()
    return (row[0] if row and row[0] else "🔹")

def delete_api_config(name):
    """Delete a custom API configuration. Built-in tools are protected."""
    if name in API_LABELS:
        return False
    con = db()
    cur = con.cursor()
    cur.execute("DELETE FROM api_configs WHERE name=?", (name,))
    deleted = cur.rowcount > 0
    con.commit()
    con.close()
    return deleted

def list_api_configs():
    con = db()
    cur = con.cursor()
    cur.execute("SELECT name, url FROM api_configs ORDER BY name")
    rows = cur.fetchall()
    con.close()
    return rows

def add_credits(user_id, amount):
    con = db()
    cur = con.cursor()
    cur.execute("""
        UPDATE users
        SET credits = credits + ?
        WHERE user_id=?
    """, (amount, user_id))
    con.commit()
    con.close()

def remove_credits(user_id, amount):
    con = db()
    cur = con.cursor()
    cur.execute("""
        UPDATE users
        SET credits = MAX(credits - ?, 0)
        WHERE user_id=?
    """, (amount, user_id))
    con.commit()
    con.close()

def use_credit(user_id):
    con = db()
    cur = con.cursor()
    cur.execute("UPDATE users SET credits = credits - ? WHERE user_id=? AND credits >= ?", (API_COST, user_id, API_COST))
    changed = cur.rowcount
    con.commit()
    con.close()
    return changed == 1

# ============================================================
# REFERRAL SYSTEM PROCESS
# ============================================================
def process_referral(user_id, referrer_id):
    if user_id == referrer_id:
        return False
    con = db()
    cur = con.cursor()
    try:
        cur.execute("SELECT referred_by FROM users WHERE user_id=?", (user_id,))
        row = cur.fetchone()
        if not row:
            con.rollback()
            return False
        stored_referrer = row[0]
        cur.execute("SELECT user_id FROM users WHERE user_id=?", (referrer_id,))
        if not cur.fetchone():
            con.rollback()
            return False
        if stored_referrer is not None and stored_referrer != referrer_id:
            con.rollback()
            return False
        if stored_referrer is None:
            cur.execute(
                "UPDATE users SET referred_by=? "
                "WHERE user_id=? AND referred_by IS NULL",
                (referrer_id, user_id)
            )
            if cur.rowcount != 1:
                con.rollback()
                return False
        try:
            cur.execute(
                "INSERT INTO referral_rewards(referred_user_id, referrer_id) "
                "VALUES (?, ?)",
                (user_id, referrer_id)
            )
        except sqlite3.IntegrityError:
            con.rollback()
            return False
        cur.execute(
            "UPDATE users SET credits=COALESCE(credits,0)+? WHERE user_id=?",
            (REFERRAL_REWARD, referrer_id)
        )
        if cur.rowcount != 1:
            con.rollback()
            return False
        con.commit()
        return True
    except sqlite3.Error:
        con.rollback()
        return False
    finally:
        con.close()

# ============================================================
# 5. KEYBOARDS (ADDED GIFT & REFERRAL BUTTONS)
# ============================================================
def get_main_keyboard():
    # Custom tools appear first, with the emoji chosen in API SETTINGS.
    custom = [(name, url) for name, url in list_api_configs() if name not in API_LABELS and url]
    rows = []
    custom_row = []
    for name, _url in custom:
        custom_row.append(_StyledKB(f"{get_api_emoji(name)} {name}", style="primary"))
        if len(custom_row) == 3:
            rows.append(custom_row)
            custom_row = []
    if custom_row:
        rows.append(custom_row)

    rows.extend([
        [_StyledKB("📞 Number", style="success"), _StyledKB("🚗 Vehicle", style="danger"), _StyledKB("🏦 IFSC", style="primary")],
        [_StyledKB("🌐 IP", style="success"), _StyledKB("📮 PIN", style="success"), _StyledKB("🏢 GST", style="danger")],
        [_StyledKB("🆔 Aadhaar", style="danger"), _StyledKB("🐙 GitHub", style="danger"), _StyledKB("👻 Snapchat", style="danger")],
        [_StyledKB("📱 Truecaller", style="primary"), _StyledKB("🇵🇰 Pakistan No", style="primary"), _StyledKB("🔢 Vehicle to Num", style="primary")],
        [_StyledKB("🆔 TG to Number", style="primary"), _StyledKB("💰 UPI Info", style="primary"), _StyledKB("🪪 Aadhaar to PAN", style="danger")],
        [_StyledKB("💳 My Credits", style="primary"), _StyledKB("👤 Profile", style="primary"), _StyledKB("🆘 Support", style="danger")],
        [_StyledKB("🎁 CLAIM GIFT", style="success"), _StyledKB("🔗 REFERRAL", style="primary")]
    ])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

ADMIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["👥 USERS", "📊 STATS"],
        ["🚫 BAN USER", "✅ UNBAN USER"],
        ["➕ ADD CREDIT", "➖ REMOVE CREDIT"],
        ["🎁 CREATE GIFT", "📋 GIFT CODES"],
        ["📢 BROADCAST", "🔧 API SETTINGS"],
        ["🛠 MAINTENANCE", "⬅️ USER MENU"],
    ],
    resize_keyboard=True
)

# ============================================================
# 6. JSON FORMAT
# ============================================================
def format_json(data):
    return (
        "<pre>"
        + json.dumps(data, indent=2, ensure_ascii=False)
        + "</pre>"
    )


# ============================================================
# 7. VALIDATION
# ============================================================
def valid_phone(value):
    return bool(re.fullmatch(r"\+?[0-9]{7,15}", value.strip()))

def valid_telegram_id(value):
    return bool(re.fullmatch(r"-?[0-9]{5,20}", value.strip()))

def valid_aadhaar(value):
    digits = re.sub(r"\D", "", value)
    return len(digits) == 12

def valid_ifsc(value):
    return bool(re.fullmatch(r"[A-Z]{4}0[A-Z0-9]{6}", value.strip().upper()))

def valid_ip(value):
    import ipaddress
    try:
        ipaddress.ip_address(value.strip())
        return True
    except ValueError:
        return False

def valid_github(value):
    return bool(re.fullmatch(r"[A-Za-z0-9-]{1,39}", value.strip().lstrip("@")))

def valid_domain(value):
    return bool(re.fullmatch(r"(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}", value.strip()))

def valid_pincode(value):
    return bool(re.fullmatch(r"[1-9][0-9]{5}", value.strip()))

def valid_pk_number(value):
    v = re.sub(r"[\s-]", "", value.strip())
    return bool(re.fullmatch(r"(?:\+92|0092|0)3[0-9]{9}", v))

def valid_pk_cnic(value):
    normalized = re.sub(r"[- ]", "", value.strip())
    return bool(re.fullmatch(r"[0-9]{13}", normalized))

def valid_pan(value):
    return bool(re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", value.strip().upper()))

def valid_gstin(value):
    return bool(re.fullmatch(r"[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]", value.strip().upper()))

def valid_social_username(value):
    return bool(re.fullmatch(r"@?[A-Za-z0-9._-]{1,100}", value.strip()))

def valid_vehicle(value):
    value = value.upper().replace(" ", "").replace("-", "")
    return bool(re.fullmatch(r"[A-Z]{2}[0-9]{1,2}[A-Z]{0,3}[0-9]{3,4}", value))


# ============================================================
# 8. API CALL
# ============================================================
async def call_api(api_url, value):
    if not api_url:
        return {"ok": False, "error": "API URL is not configured"}
    endpoint = api_url.replace("{value}", value)
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(endpoint) as response:
                status = response.status
                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    data = await response.json()
                else:
                    text = await response.text()
                    try:
                        data = json.loads(text)
                    except Exception:
                        return {"error": "API did not return valid JSON", "status": status}
                if status >= 400:
                    return {"error": "API returned an error status", "status": status}
                return data
    except aiohttp.ClientError:
        return {"ok": False, "error": "API connection failed"}
    except Exception as error:
        return {"ok": False, "error": "Unexpected error", "details": str(error)}

# ============================================================
# 9. FORCE SUB
# ============================================================
async def get_missing_channels(bot, user_id):
    missing = []
    for channel in FORCE_CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status not in ("member", "administrator", "creator"):
                missing.append(channel)
        except Exception:
            missing.append(channel)
    return missing

async def force_sub(update):
    if not FORCE_CHANNELS:
        return True
    user_id = update.effective_user.id
    missing = await get_missing_channels(update.get_bot(), user_id)
    if not missing:
        return True
    buttons = []
    for channel in missing:
        username = channel.lstrip("@")
        buttons.append([
            InlineKeyboardButton(f"📢 JOIN {channel}", url=f"https://t.me/{username}")
        ])
    buttons.append([
        InlineKeyboardButton("✅ VERIFY", callback_data="verify_subscription")
    ])
    await update.effective_message.reply_text(
        "🔐 ACCESS LOCKED\n\nPehle required channels join karo.\nPhir VERIFY dabao.",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    return False


# ============================================================
# 10. START
# ============================================================
async def start(update, context):
    user = update.effective_user
    referrer = None
    if context.args:
        try:
            referrer = int(context.args[0])
        except ValueError:
            referrer = None
    register_user(user, referrer)
    if referrer:
        rewarded = process_referral(user.id, referrer)
        if rewarded:
            try:
                await context.bot.send_message(
                    chat_id=referrer,
                    text=(
                        "🎉 REFERRAL SUCCESS!\n\n"
                        f"👤 New user: {user.first_name or 'User'}\n"
                        f"➕ +{REFERRAL_REWARD} credits added\n"
                        f"💳 Your balance: {get_credits(referrer)}"
                    )
                )
            except Exception:
                pass
    if is_banned(user.id):
        await update.message.reply_text("🚫 Aapka account banned hai.")
        return
    if not await force_sub(update):
        return
    context.user_data.clear()
    await update.message.reply_text(
        "🤖 BOT READY\n\nOption select karo:",
        reply_markup=get_main_keyboard()
    )


# ============================================================
# 11. VERIFY
# ============================================================
async def verify_subscription(update, context):
    query = update.callback_query
    await query.answer()

    try:
        missing = await get_missing_channels(context.bot, query.from_user.id)
        if missing:
            missing_text = ", ".join(missing)
            await query.message.reply_text(
                "❌ Verification failed.\n"
                "Sabhi channels join karo, phir VERIFY dabao.\n\n"
                f"Pending: {missing_text}"
            )
            return

        await query.message.reply_text(
            "✅ VERIFIED SUCCESSFULLY!\n\nAb aap bot use kar sakte ho.",
            reply_markup=get_main_keyboard()
        )
    except Exception as error:
        print("VERIFY ERROR:", repr(error))
        await query.message.reply_text(
            "⚠️ Verification check nahi ho paya.\n"
            "Bot ko dono channels mein admin banao aur dobara try karo."
        )


# ============================================================
# 12. ADMIN CHECK
# ============================================================
def is_admin(user_id):
    return user_id in ADMIN_IDS

async def admin_only(update):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin access required.")
        return False
    return True


# ============================================================
# 13. ADMIN COMMAND
# ============================================================
async def admin(update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Access denied.")
        return
    await update.message.reply_text(
        "👑 ADMIN PANEL\n\nAdmin options neeche hain.",
        reply_markup=ADMIN_KEYBOARD
    )


# ============================================================
# 14. ADMIN USERS
# ============================================================
async def show_users(update):
    con = db()
    cur = con.cursor()
    cur.execute("""
        SELECT user_id, username, first_name,
               credits, banned
        FROM users
        ORDER BY joined_at DESC
        LIMIT 50
    """)
    rows = cur.fetchall()
    con.close()
    if not rows:
        await update.message.reply_text("👥 No users.")
        return
    text = "👥 USERS\n\n"
    for user_id, username, name, credits, banned in rows:
        status = "🚫" if banned else "✅"
        text += (
            f"{status} {name or 'Unknown'}\n"
            f"ID: <code>{user_id}</code>\n"
            f"Username: @{username or 'none'}\n"
            f"Credits: {credits}\n\n"
        )
    await update.message.reply_text(text[:4000], parse_mode="HTML")


# ============================================================
# 15. STATS
# ============================================================
async def show_stats(update):
    con = db()
    cur = con.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM users WHERE banned=1")
    banned = cur.fetchone()[0]
    cur.execute("SELECT COALESCE(SUM(credits),0) FROM users")
    credits = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM gift_codes")
    gifts = cur.fetchone()[0]
    con.close()
    await update.message.reply_text(
        "📊 BOT STATS\n\n"
        f"👥 Users: {total}\n"
        f"🚫 Banned: {banned}\n"
        f"💳 Total Credits: {credits}\n"
        f"🎁 Gift Codes: {gifts}"
    )


# ============================================================
# 16. BAN / UNBAN
# ============================================================
async def set_ban(user_id, status):
    con = db()
    cur = con.cursor()
    cur.execute("""
        UPDATE users
        SET banned=?
        WHERE user_id=?
    """, (status, user_id))
    changed = cur.rowcount
    con.commit()
    con.close()
    return changed > 0


# ============================================================
# 17. GIFT CODE
# ============================================================
def generate_code(length=12):
    chars = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(chars) for _ in range(length))

def create_gift(credits, max_uses=1):
    con = db()
    cur = con.cursor()
    while True:
        code = generate_code()
        cur.execute("SELECT code FROM gift_codes WHERE code=?", (code,))
        if not cur.fetchone():
            break
    cur.execute("""
        INSERT INTO gift_codes(code, credits, max_uses, uses)
        VALUES (?, ?, ?, 0)
    """, (code, credits, max_uses))
    con.commit()
    con.close()
    return code

def redeem_gift(user_id, code):
    con = db()
    cur = con.cursor()
    try:
        cur.execute("""
            SELECT credits, max_uses, uses
            FROM gift_codes
            WHERE code=?
        """, (code.upper(),))
        row = cur.fetchone()
        if not row:
            return None
        credits, max_uses, uses = row
        if uses >= max_uses:
            return 0
        cur.execute("""
            SELECT 1 FROM gift_redemptions
            WHERE code=? AND user_id=?
        """, (code.upper(), user_id))
        if cur.fetchone():
            return 0
        cur.execute("""
            UPDATE gift_codes
            SET uses=uses+1,
                used_by=CASE WHEN uses=0 THEN ? ELSE used_by END,
                used_at=CASE WHEN uses=0 THEN CURRENT_TIMESTAMP ELSE used_at END
            WHERE code=? AND uses < max_uses
        """, (user_id, code.upper()))
        if cur.rowcount != 1:
            con.rollback()
            return 0
        cur.execute("""
            INSERT INTO gift_redemptions(code, user_id)
            VALUES (?, ?)
        """, (code.upper(), user_id))
        cur.execute("""
            UPDATE users SET credits=credits+? WHERE user_id=?
        """, (credits, user_id))
        if cur.rowcount != 1:
            con.rollback()
            return None
        con.commit()
        return credits
    except sqlite3.Error:
        con.rollback()
        return None
    finally:
        con.close()


# ============================================================
# 18. MESSAGE HANDLER
# ============================================================
async def message_handler(update, context):
    if not update.message:
        return

    user = update.effective_user
    register_user(user)

    if is_banned(user.id):
        await update.message.reply_text("🚫 Aapka account banned hai.")
        return

    text = update.message.text.strip()

    if maintenance_enabled() and not is_admin(user.id):
        await update.message.reply_text(
            "🛠 BOT MAINTENANCE MODE\n\nAbhi bot temporarily unavailable hai. Baad me try karo."
        )
        return

    # --------------------------------------------------------
    # ADMIN MENU
    # --------------------------------------------------------
    if text == "/admin":
        await admin(update, context)
        return

    if text == "👥 USERS":
        if await admin_only(update):
            await show_users(update)
        return

    if text == "📊 STATS":
        if await admin_only(update):
            await show_stats(update)
        return

    if text == "🚫 BAN USER":
        if await admin_only(update):
            context.user_data["admin_action"] = "ban"
            await update.message.reply_text("🚫 User Telegram ID send karo:")
        return

    if text == "✅ UNBAN USER":
        if await admin_only(update):
            context.user_data["admin_action"] = "unban"
            await update.message.reply_text("✅ User Telegram ID send karo:")
        return

    if text == "➕ ADD CREDIT":
        if await admin_only(update):
            context.user_data["admin_action"] = "add"
            await update.message.reply_text("Format:\nUSER_ID AMOUNT\n\nExample:\n123456789 10")
        return

    if text == "➖ REMOVE CREDIT":
        if await admin_only(update):
            context.user_data["admin_action"] = "remove"
            await update.message.reply_text("Format:\nUSER_ID AMOUNT")
        return

    if text == "🎁 CREATE GIFT":
        if await admin_only(update):
            context.user_data["admin_action"] = "gift"
            await update.message.reply_text("Format: CREDITS MAX_USERS\n\nExample: 50 10\n50 credits ka code, maximum 10 users.")
        return

    if text == "📋 GIFT CODES":
        if await admin_only(update):
            con = db()
            cur = con.cursor()
            cur.execute("""
                SELECT code, credits, max_uses, uses
                FROM gift_codes
                ORDER BY rowid DESC
                LIMIT 50
            """)
            rows = cur.fetchall()
            con.close()
            if not rows:
                await update.message.reply_text("🎁 No gift codes.")
                return
            output = "🎁 GIFT CODES\n\n"
            for code, credits, max_uses, uses in rows:
                output += f"<code>{code}</code> → {credits} credits ({uses}/{max_uses} used)\n"
            await update.message.reply_text(output[:4000], parse_mode="HTML")
        return

    if text == "📢 BROADCAST":
        if await admin_only(update):
            context.user_data["admin_action"] = "broadcast"
            await update.message.reply_text("📢 Broadcast message bhejo.\n\nYe message registered, non-banned users ko send hoga.")
        return

    if text == "🔧 API SETTINGS":
        if await admin_only(update):
            context.user_data["admin_action"] = "api_settings"
            rows = list_api_configs()
            out = "🔧 API SETTINGS\n\n"
            for name, url in rows:
                out += f"{name}: {'SET' if url else 'NOT SET'}\n"
            out += (
                "\\nADD / UPDATE:\\nAPI_NAME | https://example.com/?q={value}\\n"
                "Example: Weather_API | https://example.com/?q={value} | 🌦️\\n"
                "Emoji is optional; default is 🔹. Example: 🌐, 🔎, 🧩\\n\\n"
                "REMOVE CUSTOM TOOL:\\nREMOVE | Weather_API\\n\\n"
                "Names: 2-32 letters, numbers, _ or -. Spaces automatically become _.\\n"
                "URL must use http/https and include {value}.\\n"
                "New custom tools appear at the TOP of the user menu."
            )
            await update.message.reply_text(out)
        return

    if text == "🛠 MAINTENANCE":
        if await admin_only(update):
            new_state = "0" if maintenance_enabled() else "1"
            set_setting("maintenance", new_state)
            await update.message.reply_text(
                "🟢 Maintenance OFF" if new_state == "0"
                else "🔴 Maintenance ON\nNon-admin users cannot use the bot."
            )
        return

    if text == "⬅️ USER MENU":
        context.user_data.clear()
        await update.message.reply_text("👤 User menu:", reply_markup=get_main_keyboard())
        return

    # --------------------------------------------------------
    # ADMIN ACTIONS
    # --------------------------------------------------------
    action = context.user_data.get("admin_action")
    if action and is_admin(user.id):
        if action in ("ban", "unban"):
            try:
                target_id = int(text)
            except ValueError:
                await update.message.reply_text("❌ Invalid user ID.")
                return
            changed = await set_ban(target_id, 1 if action == "ban" else 0)
            context.user_data.pop("admin_action", None)
            await update.message.reply_text("✅ Done." if changed else "❌ User not found.")
            return

        if action in ("add", "remove"):
            parts = text.split()
            if len(parts) != 2:
                await update.message.reply_text("❌ Format: USER_ID AMOUNT")
                return
            try:
                target_id = int(parts[0])
                amount = int(parts[1])
            except ValueError:
                await update.message.reply_text("❌ Invalid numbers.")
                return
            if amount <= 0:
                await update.message.reply_text("❌ Amount must be greater than 0.")
                return
            if action == "add":
                add_credits(target_id, amount)
            else:
                remove_credits(target_id, amount)
            balance = get_credits(target_id)
            context.user_data.pop("admin_action", None)
            await update.message.reply_text(f"✅ Updated.\n\nUser: {target_id}\nCredits: {balance}")
            return

        if action == "gift":
            parts = text.split()
            try:
                amount = int(parts[0])
                max_uses = int(parts[1]) if len(parts) > 1 else 1
            except (ValueError, IndexError):
                await update.message.reply_text("❌ Format: CREDITS MAX_USERS\nExample: 50 10")
                return
            if amount <= 0 or max_uses <= 0 or max_uses > 10000:
                await update.message.reply_text("❌ Credits > 0 and MAX_USERS must be 1-10000.")
                return
            code = create_gift(amount, max_uses)
            context.user_data.pop("admin_action", None)
            await update.message.reply_text(
                "🎁 GIFT CODE CREATED\n\n"
                f"Code: `{code}`\n"
                f"Credits/user: {amount}\n"
                f"Max users: {max_uses}",
                parse_mode="Markdown"
            )
            return

        if action == "broadcast":
            message = text.strip()
            context.user_data.pop("admin_action", None)
            con = db()
            cur = con.cursor()
            cur.execute("SELECT user_id FROM users WHERE banned=0")
            user_ids = [row[0] for row in cur.fetchall()]
            con.close()
            sent = 0
            failed = 0
            for target_id in user_ids:
                try:
                    await context.bot.send_message(chat_id=target_id, text=message)
                    sent += 1
                except Exception:
                    failed += 1
            await update.message.reply_text(f"📢 Broadcast complete.\n\n✅ Sent: {sent}\n❌ Failed: {failed}")
            return

        if action == "api_settings":
            # Remove custom tools with: REMOVE | Tool_Name
            parts = [part.strip() for part in text.split("|")]
            first = parts[0] if parts else ""
            remainder = parts[1] if len(parts) >= 2 else ""
            emoji = parts[2] if len(parts) >= 3 else "🔹"

            if first.upper() == "REMOVE":
                name = re.sub(r"\s+", "_", remainder.strip())
                if not re.fullmatch(r"[A-Za-z0-9_-]{2,32}", name):
                    await update.message.reply_text(
                        "❌ Tool name invalid. Use 2-32 letters, numbers, _ or -."
                    )
                    return
                if name in API_LABELS:
                    await update.message.reply_text(
                        "⚠️ Built-in tools cannot be removed here. Only custom tools can be removed."
                    )
                    return
                if delete_api_config(name):
                    context.user_data.pop("admin_action", None)
                    await update.message.reply_text(
                        f"✅ Custom tool '{name}' removed.\\nIt will no longer appear in the user menu.",
                        reply_markup=get_main_keyboard()
                    )
                else:
                    await update.message.reply_text(f"❌ Custom tool '{name}' was not found.")
                return

            if not remainder:
                await update.message.reply_text(
                    "❌ Format: API_NAME | https://example.com/?q={value} | EMOJI\\n"
                    "To remove: REMOVE | API_NAME"
                )
                return
            if len(parts) > 3:
                await update.message.reply_text("❌ Sirf 3 fields use karo: API_NAME | URL | EMOJI")
                return

            # Accept readable names such as "Weather API" by normalizing spaces.
            name = re.sub(r"\s+", "_", first.strip())
            url = remainder.strip()

            if not re.fullmatch(r"[A-Za-z0-9_-]{2,32}", name):
                await update.message.reply_text(
                    "❌ API_NAME must be 2-32 letters, numbers, _ or -.\\n"
                    "Example: Weather_API | https://example.com/?q={value}"
                )
                return
            if not re.match(r"^https?://", url, re.IGNORECASE):
                await update.message.reply_text("❌ API URL must start with http:// or https://.")
                return
            if "{value}" not in url:
                await update.message.reply_text("❌ URL me {value} placeholder zaroor hona chahiye.")
                return

            if not emoji:
                emoji = "🔹"
            if len(emoji) > 16:
                await update.message.reply_text("❌ Emoji field bahut lamba hai. Ek emoji ya short emoji combination do.")
                return

            set_api_url(name, url, emoji)
            context.user_data.pop("admin_action", None)
            await update.message.reply_text(
                f"✅ '{name}' API URL and emoji saved.\\n"
                "Tool ab user menu ke TOP par dikhega.",
                reply_markup=get_main_keyboard()
            )
            return

    if not await force_sub(update):
        return

    # --------------------------------------------------------
    # CREDITS & REFERRAL & GIFT BUTTON LOGIC
    # --------------------------------------------------------
    if text == "💳 My Credits":
        await update.message.reply_text(f"💳 Your credits: {get_credits(user.id)}")
        return

    if text == "👤 Profile":
        await update.message.reply_text(f"👤 Name: {user.first_name}\nID: {user.id}")
        return

    if text == "🆘 Support":
        await update.message.reply_text("Admin se contact karein: @BEST_API_SELLER")
        return

    if text == "🔗 REFERRAL":
        me = await context.bot.get_me()
        link = f"https://t.me/{me.username}?start={user.id}"
        await update.message.reply_text(
            "🔗 YOUR REFERRAL\n\n"
            f"1 successful referral = {REFERRAL_REWARD} credits\n\n"
            f"Your link:\n{link}\n\n"
            f"Current credits: {get_credits(user.id)}"
        )
        return

    if text == "🎁 CLAIM GIFT":
        context.user_data["mode"] = "gift"
        await update.message.reply_text("🎁 Gift code enter karo:\n\nExample: ABC123XYZ789")
        return

    if text.upper().startswith("GIFT "):
        code = text[5:].strip()
        result = redeem_gift(user.id, code)
        if result is None:
            await update.message.reply_text("❌ Invalid gift code.")
        elif result == 0:
            await update.message.reply_text("❌ Gift code already used.")
        else:
            await update.message.reply_text(f"🎁 Gift redeemed!\n\n+{result} credits\nBalance: {get_credits(user.id)}")
        return

    # --------------------------------------------------------
    # API BUTTONS
    # --------------------------------------------------------
    button_to_mode = {label: mode for mode, label in API_LABELS.items()}
    for custom_name, custom_url in list_api_configs():
        if custom_name not in API_LABELS:
            button_to_mode[f"{get_api_emoji(custom_name)} {custom_name}"] = custom_name

    if text in button_to_mode:
        mode = button_to_mode[text]
        context.user_data["mode"] = mode
        prompts = {
            "Number": "📱 Number send karo:",
            "Telegram": "🌟 Telegram numeric ID send karo:",
            "Aadhaar": "💎 Aadhaar send karo:",
            "Vehicle": "🚀 Vehicle registration number send karo:",
            "Vehicle_challan": "🚦 Vehicle number send karo:",
            "Instagram": "🔥 Public Instagram username send karo:",
            "Snapchat": "👻 Public Snapchat username send karo:",
            "IFSC": "🏦 IFSC code send karo:",
            "IP": "🌐 IP address send karo:",
            "GitHub": "🐙 GitHub username send karo:",
            "Domain": "🔎 Domain send karo:",
            "PIN": "📍 6-digit Indian pincode send karo:",
            "Pakistan_No": "🇵🇰 Pakistan number send karo:",
            "Truecaller": "📱 Truecaller info input send karo:",
            "TG_to_Number": "👤 Public Telegram username/ID send karo:",
            "GST": "🧾 GSTIN send karo:",
            "PAN": "🪪 PAN send karo:",
            "Aadhaar_to_PAN": "💳 Aadhaar → PAN input send karo:",
        }
        await update.message.reply_text(prompts.get(mode, f"✨ {text} ke liye input send karo:"))
        return

    # --------------------------------------------------------
    # API MODE & GIFT MODE
    # --------------------------------------------------------
    mode = context.user_data.get("mode")
    if not mode:
        await update.message.reply_text("⬇️ Pehle koi option select karo.", reply_markup=get_main_keyboard())
        return

    if mode == "gift":
        code = text.strip().upper()
        if not re.fullmatch(r"[A-Z0-9]{6,32}", code):
            await update.message.reply_text("❌ Invalid gift code format.")
            return
        result = redeem_gift(user.id, code)
        context.user_data.pop("mode", None)
        if result is None:
            await update.message.reply_text("❌ Invalid gift code.")
        elif result == 0:
            await update.message.reply_text("❌ Gift code already used.")
        else:
            await update.message.reply_text(f"🎁 Gift redeemed successfully!\n\n➕ {result} credits added\n💳 Balance: {get_credits(user.id)}")
        return

    # --------------------------------------------------------
    # VALIDATE (DYNAMIC SUPPORT ADDED)
    # --------------------------------------------------------
    validators = {
        "Number": valid_phone,
        "Aadhaar": valid_aadhaar,
        "Aadhaar_to_PAN": valid_aadhaar,
        "PAN": valid_pan,
        "Telegram": valid_telegram_id,
        "Vehicle": valid_vehicle,
        "Vehicle_challan": valid_vehicle,
        "Instagram": valid_social_username,
        "Snapchat": valid_social_username,
        "IFSC": valid_ifsc,
        "IP": valid_ip,
        "GitHub": valid_github,
        "Domain": valid_domain,
        "PIN": valid_pincode,
        "Pakistan_No": valid_pk_number,
        "Truecaller": valid_phone,
        "TG_to_Number": lambda v: bool(re.fullmatch(r"(?:@?[A-Za-z0-9_]{3,32}|-?[0-9]{5,20})", v.strip())),
        "GST": valid_gstin,
    }

    is_valid = validators.get(mode, lambda v: True)(text)
    
    if not is_valid:
        await update.message.reply_text("❌ Invalid input format.")
        return

    if mode == "pk_cnic":
        text = text.replace("-", "").replace(" ", "")

    api_url = get_api_url(mode)
    if not api_url:
        context.user_data.pop("mode", None)
        await update.message.reply_text(format_json({"error": "API URL is not configured"}), parse_mode="HTML")
        return

    # --------------------------------------------------------
    # CREDIT CHECK & API CALL
    # --------------------------------------------------------
    if get_credits(user.id) < API_COST:
        await update.message.reply_text(f"❌ Insufficient credits.\n\nRequired: {API_COST}\nAvailable: {get_credits(user.id)}")
        context.user_data.pop("mode", None)
        return

    processing_msg = await update.message.reply_text("⏳ Processing fast...")

    api_url = get_api_url(mode)
    result = await call_api(api_url, text)

    if not (isinstance(result, dict) and result.get("error")):
        use_credit(user.id)

    # --------------------------------------------------------
    # JSON OUTPUT
    # --------------------------------------------------------
    output = format_json(result)

    await processing_msg.delete()

    if len(output) <= 4000:
        await update.message.reply_text(output, parse_mode="HTML")
    else:
        import io
        document = io.BytesIO(json.dumps(result, indent=2, ensure_ascii=False).encode("utf-8"))
        document.name = f"{mode}_response.json"
        await update.message.reply_document(document=document)

    context.user_data.pop("mode", None)

# ============================================================
# 19. ERROR HANDLER
# ============================================================
async def error_handler(update, context):
    print("ERROR:", repr(context.error))

# ============================================================
# 20. MAIN
# ============================================================
async def run_bot():
    if (not BOT_TOKEN or BOT_TOKEN == "PUT_YOUR_BOT_TOKEN_HERE"):
        raise RuntimeError("BOT_TOKEN missing hai. Render Environment Variables me BOT_TOKEN set karo.")
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CallbackQueryHandler(verify_subscription, pattern="^verify_subscription$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.add_error_handler(error_handler)
    print("🤖 Bot starting...")

    await app.initialize()
    await app.start()
    try:
        await app.updater.start_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=False)
        print("🤖 Bot started successfully...")
        await asyncio.Event().wait()
    finally:
        try:
            if app.updater and app.updater.running:
                await app.updater.stop()
        finally:
            try:
                await app.stop()
            finally:
                await app.shutdown()

def main():
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped.")

if __name__ == "__main__":
    main()
