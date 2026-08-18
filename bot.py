import json, time, re, os, random as rnd, asyncio, logging, threading, sys, traceback
from datetime import datetime, timedelta, timezone
import aiohttp
from io import BytesIO
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, MessageEntity
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.request import HTTPXRequest
from flask import Flask

# ============================================================
# ✅ FLASK & UPTIME SERVER
# ============================================================
app_flask = Flask(__name__)
PORT = int(os.environ.get("PORT", 10000))

@app_flask.route('/')
def home():
    return "🎁 GIVEAWAY BOT - RUNNING 24/7 (LAG-FREE)!"

@app_flask.route('/health')
def health():
    return "OK"

def run_flask():
    app_flask.run(host="0.0.0.0", port=PORT, use_reloader=False)

# ============================================================
# ✅ CONFIGURATION
# ============================================================
TOKEN = "8960961388:AAESbq3QLKlV0oh_ujBHUbvkvkzXNqLA3n0"
ADMIN_ID = 6531314640
COOLDOWN_HOURS = 24

REQUIRED_CHATS = [
    {"id": "@TnnrCPM", "name": "TnnrCPM Channel", "link": "https://t.me/TnnrCPM"},
    {"id": "@markmwehehestore", "name": "MarkMwehehe Store", "link": "https://t.me/markmwehehestore"},
    {"id": "@markmwhehe", "name": "Mark Mwehehe Main Channel", "link": "https://t.me/markmwhehe"},
]

TNNR_GROUP_CHAT = {"id": "@TnnrChat", "name": "TnnrChat Group", "link": "https://t.me/TnnrChat"}
ANNOUNCEMENT_CHATS = [
    {"id": -1003846885691, "name": "Channel 1"},
    {"id": -1003885017181, "name": "Channel 2"},
]

# ============================================================
# ✅ IN-MEMORY DATABASE (INSTANT SPEED)
# ============================================================
DB_FILE = "database.json"
DB = {"giveaway": {}}

if os.path.exists(DB_FILE):
    try:
        with open(DB_FILE, "r") as f:
            DB = json.load(f)
    except Exception as e:
        print(f"⚠️ Error loading DB: {e}")

async def auto_save_db():
    while True:
        await asyncio.sleep(10)
        try:
            with open(DB_FILE, "w") as f:
                json.dump(DB, f)
        except Exception as e:
            print(f"⚠️ DB Save Error: {e}")

async def db_put(path, data):
    keys = path.split('/')
    curr = DB
    for key in keys[:-1]:
        if key not in curr or not isinstance(curr[key], dict):
            curr[key] = {}
        curr = curr[key]
    curr[keys[-1]] = data
    return True

async def db_get(path):
    keys = path.split('/')
    curr = DB
    for key in keys:
        if isinstance(curr, dict) and key in curr:
            curr = curr[key]
        else:
            return None
    return curr

async def db_delete(path):
    keys = path.split('/')
    curr = DB
    for key in keys[:-1]:
        if key not in curr or not isinstance(curr[key], dict):
            return False
        curr = curr[key]
    if keys[-1] in curr:
        del curr[keys[-1]]
        return True
    return False

# ============================================================
# ✅ BUILT-IN UPTIME ROBOT (Self-Pinger)
# ============================================================
async def keep_alive_pinger():
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"http://127.0.0.1:{PORT}/health") as response:
                    pass
        except Exception:
            pass
        await asyncio.sleep(120)

# ============================================================
# ✅ CUSTOM EMOJI MAPPING
# ============================================================
CUSTOM_EMOJI_MAP = {
    '😂': '5406913184810409829', '😄': '5386587088873331829', '😍': '5323470315370585285', 
    '😭': '5379656338802482888', '🤑': '5427107837568360763', '👑': '5938534225140519372',
    '🔥': '6001061381237903602', '⚡': '6100289024289672793', '💎': '6064293500382350516', 
    '❌': '6064642968986323772', '🤨': '6134245834595765950', '👹': '6142914800880979809',
    '👀': '5834733550020072624', '💙': '6269557847248342937', '⚠️': '6100590432209604692', 
    '😆': '5375135722514685501', '😮': '5456662929166309849', '😎': '5195360348693078341',
    '👤': '5258011929993026890', '🎮': '5258508428212445001', '🚘': '5366286487862124799', 
    '✅': '5197288647275071607', '🎉': '6001197385672298829', '📁': '5357315181649076022',
    '📊': '5192886773948107844', '⏳': '5192988444413938411', '🚀': '5190768392998504411', 
    '💰': '5192683149548605430', '📲': '5192998636371330526', '💃': '5373112999076699207', 
    '😠': '5348119373200506812', '😡': '5251301176737013980', '🦁': '5980821811711972473',
    '☑️': '5936230155574842929', '👌': '6001451188174723066', '🗿': '6001226634399585063', 
    '🚗': '5375593780776805206', '🏎': '5391327195169831190', '😌': '5958585443170651565',
    '⚡1': '6100277122935295595', '⚡2': '6100472578307002133', '⚡3': '6102404476071579522', 
    '⚡4': '6100671388048166850', '⚡5': '6100278127957643014', '🥵': '6307832826263768178'
}

def get_custom_entities(text):
    entities = []
    offset = 0
    i = 0
    while i < len(text):
        ch = text[i]
        if i + 1 < len(text) and text[i:i+2] in ['☑️', '✔️', '⚡1', '⚡2', '⚡3', '⚡4', '⚡5']:
            ch = text[i:i+2]
            utf16_len = 2
            i += 2
        else:
            utf16_len = len(ch.encode('utf-16-le')) // 2
            i += 1
        
        if ch in CUSTOM_EMOJI_MAP:
            entities.append(MessageEntity(type="custom_emoji", offset=offset, length=utf16_len, custom_emoji_id=CUSTOM_EMOJI_MAP[ch]))
        offset += utf16_len
    return entities

async def send_custom(chat_id, text, context, reply_markup=None):
    entities = get_custom_entities(text)
    try:
        await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, entities=entities if entities else None)
    except Exception:
        await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)

async def reply_custom(update, text, context, reply_markup=None):
    await send_custom(update.effective_chat.id, text, context, reply_markup)

async def edit_custom(query, text, reply_markup=None):
    entities = get_custom_entities(text)
    try:
        await query.edit_message_text(text=text, reply_markup=reply_markup, entities=entities if entities else None)
    except Exception as e:
        if "Message is not modified" not in str(e):
            try: await query.edit_message_text(text=text, reply_markup=reply_markup)
            except: pass

async def send_file(chat_id, filename, content, context, caption=None):
    try:
        file_bytes = BytesIO(content.encode('utf-8'))
        file_bytes.name = filename
        await context.bot.send_document(chat_id=chat_id, document=file_bytes, caption=caption)
        return True
    except Exception as e:
        print(f"⚠️ Error sending file: {e}")
        return False

# ============================================================
# ✅ CORE DATA FUNCTIONS
# ============================================================
ACCOUNT_POOLS = {"cpm1_normal": [], "cpm2_normal": [], "cpm1_unlock": [], "cpm2_coin": []}
ADD_ACCOUNT_SESSIONS = {}
MEMBERSHIP_CACHE = {}

async def get_claim_enabled(): return await db_get("giveaway/claim_enabled") is not False
async def set_claim_enabled(value): await db_put("giveaway/claim_enabled", value)

EVENT_TYPES = {
    "default": {"name": "Default", "normal_limit": 1, "unlock_coin_limit": 1, "cooldown_hours": 24, "timer_hours": 0},
    "claimagain": {"name": "Claim Again", "normal_limit": 3, "unlock_coin_limit": 3, "cooldown_hours": 0, "timer_hours": 1},
    "partytime": {"name": "Party Time", "normal_limit": 10, "unlock_coin_limit": 5, "cooldown_hours": 0, "timer_hours": 5}
}

def get_event_limits(event_type): return EVENT_TYPES.get(event_type, EVENT_TYPES["default"])

async def get_event_claim_count(user_id, event_type):
    data = await db_get(f"giveaway/event_claims/{user_id}/{event_type}") or {}
    return {"normal": data.get("normal", 0), "unlock": data.get("unlock", 0), "coin": data.get("coin", 0), "total": data.get("total", 0)}

async def increment_event_claim(user_id, event_type, account_type):
    current = await get_event_claim_count(user_id, event_type)
    if "unlock" in account_type: current["unlock"] += 1
    elif "coin" in account_type: current["coin"] += 1
    else: current["normal"] += 1
    current["total"] += 1
    await db_put(f"giveaway/event_claims/{user_id}/{event_type}", current)
    return current

async def can_claim_event(user_id, event_type, account_type):
    limits = get_event_limits(event_type)
    current = await get_event_claim_count(user_id, event_type)
    is_unlock = "unlock" in account_type
    is_coin = "coin" in account_type
    
    if is_unlock or is_coin:
        if (current["unlock"] if is_unlock else current["coin"]) >= limits["unlock_coin_limit"]:
            return False, f"You've reached the max {limits['unlock_coin_limit']} {account_type.upper()} accounts! ⚠️"
    else:
        if current["normal"] >= limits["normal_limit"]:
            return False, f"You've reached the max {limits['normal_limit']} normal accounts! ⚠️"
    
    if current["total"] >= limits["normal_limit"] + limits["unlock_coin_limit"] * 2:
        return False, "You've reached the total max accounts for this event! ⚠️"
    return True, None

async def set_event_timer(event_type, duration_hours):
    expiry = datetime.now(timezone.utc) + timedelta(hours=duration_hours)
    return await db_put(f"giveaway/event_timer/{event_type}", {"start": datetime.now(timezone.utc).isoformat(), "expiry": expiry.isoformat(), "active": True})

async def get_event_timer(event_type):
    data = await db_get(f"giveaway/event_timer/{event_type}")
    if not data: return None
    expiry = datetime.fromisoformat(data["expiry"])
    if datetime.now(timezone.utc) >= expiry:
        await db_delete(f"giveaway/event_timer/{event_type}")
        return None
    rem = expiry - datetime.now(timezone.utc)
    return {"expiry": expiry, "remaining": rem, "hours": rem.seconds // 3600, "minutes": (rem.seconds % 3600) // 60}

async def is_event_active(event_type): return await get_event_timer(event_type) is not None

async def get_current_event():
    if await is_event_active("partytime"): return "partytime"
    if await is_event_active("claimagain"): return "claimagain"
    return "default"

async def load_accounts():
    data = await db_get("giveaway/accounts") or {}
    for key in ACCOUNT_POOLS: ACCOUNT_POOLS[key] = data.get(key, [])

async def save_accounts(): await db_put("giveaway/accounts", ACCOUNT_POOLS)
async def get_claimed(user_id): return await db_get(f"giveaway/claimed/{user_id}") or []
async def add_claimed(user_id, account_type, email):
    claimed = await get_claimed(user_id)
    claimed.append({"type": account_type, "email": email, "timestamp": datetime.now().isoformat()})
    await db_put(f"giveaway/claimed/{user_id}", claimed)

async def get_all_claimed():
    data = await db_get("giveaway/claimed") or {}
    return [{"user_id": int(uid), **claim} for uid, claims in data.items() for claim in claims]

async def get_warnings(user_id): return await db_get(f"giveaway/warnings/{user_id}") or 0
async def add_warning(user_id):
    count = await get_warnings(user_id) + 1
    await db_put(f"giveaway/warnings/{user_id}", count)
    return count
async def reset_warnings(user_id): await db_delete(f"giveaway/warnings/{user_id}")
async def is_banned(user_id): return await db_get(f"giveaway/banned/{user_id}") is not None
async def ban_user(user_id): await db_put(f"giveaway/banned/{user_id}", True)

async def get_makulit_users():
    warnings = await db_get("giveaway/warnings") or {}
    return sorted([{"user_id": int(uid), "warnings": count} for uid, count in warnings.items() if count > 0], key=lambda x: x["warnings"], reverse=True)

async def set_share_verified(user_id): await db_put(f"giveaway/share_verified/{user_id}", True)
async def is_share_verified(user_id): return await db_get(f"giveaway/share_verified/{user_id}") is not None

async def set_last_claim_time(user_id): await db_put(f"giveaway/last_claim/{user_id}", {"timestamp": datetime.now().isoformat()})
async def get_last_claim_time(user_id):
    data = await db_get(f"giveaway/last_claim/{user_id}")
    if data and data.get("timestamp"): return datetime.fromisoformat(data["timestamp"])
    return None

async def can_claim(user_id):
    last = await get_last_claim_time(user_id)
    if not last: return True, None
    cooldown_end = last + timedelta(hours=COOLDOWN_HOURS)
    if datetime.now() >= cooldown_end: return True, None
    rem = cooldown_end - datetime.now()
    return False, f"{rem.seconds // 3600}h {(rem.seconds % 3600) // 60}m"

async def get_all_users():
    data = await db_get("giveaway/users") or {}
    return [int(uid) for uid in data.keys()]

async def add_user(user_id): await db_put(f"giveaway/users/{user_id}", {"timestamp": datetime.now().isoformat()})

# ============================================================
# ✅ MEMBERSHIP CHECK (Parallelized for speed)
# ============================================================
async def check_membership(context, user_id, force_refresh=False):
    cache_key = f"{user_id}"
    if force_refresh and cache_key in MEMBERSHIP_CACHE: del MEMBERSHIP_CACHE[cache_key]
    
    if cache_key in MEMBERSHIP_CACHE:
        res, ctime = MEMBERSHIP_CACHE[cache_key]
        if (datetime.now() - ctime).seconds < 10: return res

    async def check_one(chat):
        chat_id, chat_name = chat["id"], chat["name"]
        try:
            member = await context.bot.get_chat_member(chat_id, user_id)
            return True, None if member.status in ["member", "administrator", "creator"] else (False, chat_name)
        except Exception:
            return False, chat_name

    results = await asyncio.gather(*(check_one(chat) for chat in REQUIRED_CHATS))
    for success, missing in results:
        if not success:
            MEMBERSHIP_CACHE[cache_key] = ((False, missing), datetime.now())
            return False, missing

    MEMBERSHIP_CACHE[cache_key] = ((True, None), datetime.now())
    return True, None

# ============================================================
# ✅ BROADCAST & ANNOUNCEMENT
# ============================================================
async def broadcast_to_users(context, msg, title, admin_id):
    users = await get_all_users()
    if not users:
        await send_custom(admin_id, "⚠️ No users found to broadcast.", context)
        return
    full_msg = f"{title}\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n{msg}"
    success, failed = 0, 0
    for uid in users:
        try: 
            await send_custom(uid, full_msg, context)
            success += 1
        except: 
            failed += 1
    await send_custom(admin_id, f"✅ Broadcast completed!\n📤 Sent to: {success} users\n❌ Failed: {failed}", context)

async def broadcast_message_background(context, msg, title, admin_id):
    context.application.create_task(broadcast_to_users(context, msg, title, admin_id))

async def send_announcement_to_channels(context, msg, title, admin_id):
    full_msg = f"{title}\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n{msg}"
    success, failed = 0, 0
    for chat in ANNOUNCEMENT_CHATS:
        try:
            await send_custom(chat["id"], full_msg, context)
            success += 1
        except Exception as e:
            failed += 1
    await send_custom(admin_id, f"✅ Announcement sent to {success} channels.\n❌ Failed: {failed}", context)

async def send_announcement_background(context, msg, title, admin_id):
    context.application.create_task(send_announcement_to_channels(context, msg, title, admin_id))

# ============================================================
# ✅ ACCOUNT DETAILS
# ============================================================
ACCOUNT_DETAILS = {
    "cpm1_normal": "🚘 CPM1 NORMAL GIVEAWAY ACCOUNT\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n📌 Account Features:\n  ✅ 50M Cash (Max)\n  💰 500K / 30K Coins! (Random)\n  🆔 Random ID!\n  🏠 Houses & Clothes\n  🔓 Everything Unlocked!\n\n⚡ One account per game – choose wisely!\n\n👇 Click the button below to claim:",
    "cpm1_unlock": "🚘 CPM1 UNLOCK ALL CARS GIVEAWAY ACCOUNT\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n📌 Account Features:\n  ✅ 50M Cash (Max)\n  💰 500K / 30K Coins! (Random)\n  🆔 Random ID!\n  🏎️ UNLOCK ALL CARS 🏎️\n  🏠 Houses & Clothes\n  🔓 Everything Unlocked!\n\n⚡ One account per game – choose wisely!\n\n👇 Click the button below to claim:",
    "cpm2_coin": "💰 CPM2 COIN GIVEAWAY ACCOUNT\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n📌 Account Features:\n  ✅ 50M Cash (Max)\n  💰 11K-13K Coins\n  🎯 20 Slots Unlocked!\n  👑 King Rank!\n  🚗 4-20 Random Cars\n  🎨 Full Customization!\n  🏠 Houses + Clothes\n\n⚡ One account per game – choose wisely!\n\n👇 Click the button below to claim:",
    "cpm2_normal": "💰 CPM2 NORMAL GIVEAWAY ACCOUNT\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n📌 Account Features:\n  ✅ 50M Cash (Max)\n  🎯 20 Slots Unlocked!\n  👑 King Rank!\n  🚗 4-20 Random Cars\n  🎨 Full Customization!\n  🏠 Houses + Clothes\n\n⚡ One account per game – choose wisely!\n\n👇 Click the button below to claim:"
}

# ============================================================
# ✅ BOT HANDLERS
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        try: await update.message.delete()
        except: pass

    if update.effective_chat.type in ["group", "supergroup"]:
        await reply_custom(update, f"⚠️ Please use this bot in **private chat** only!\n👉 t.me/{context.bot.username}?start=private", context)
        return

    user_id = update.effective_user.id
    await add_user(user_id)

    if await is_banned(user_id):
        await reply_custom(update, "⛔ BANNED ⛔\n\nYou have been permanently banned.\nContact @Maarkryan.", context)
        return

    if not await get_claim_enabled():
        await reply_custom(update, "⚠️ CLAIMING IS CURRENTLY DISABLED ⚠️\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n🔒 The admin has temporarily disabled claiming.", context, InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Check Again", callback_data="start_back")]]))
        return

    if not await is_share_verified(user_id):
        kb = [[InlineKeyboardButton("📤 Share to Groups", switch_inline_query="🔥 FREE CPM1/CPM2 ACCOUNTS! Join the giveaway! @Cpm_2test_bot")], [InlineKeyboardButton("✅ I've Shared!", callback_data="share_confirmed")]]
        await reply_custom(update, "📢 SHARE TO WIN! 📢\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n🔥 To claim your free account, you must share this bot to 3-5 groups!", context, InlineKeyboardMarkup(kb))
        return

    warnings = await get_warnings(user_id)
    if warnings > 0:
        if warnings >= 5:
            await ban_user(user_id)
            await reply_custom(update, "🚫 YOU HAVE BEEN BANNED 🚫\n\nYou reached 5 warnings.", context)
            return
        await reply_custom(update, f"⚠️ WARNING #{warnings}/5 ⚠️\n\nYou left a required group.\n🔄 Warnings: {warnings}/5\n❌ 5 warnings = PERMANENT BAN\n\n💙 Stay in all groups.", context)

    is_member, missing = await check_membership(context, user_id)
    if not is_member:
        msg = "🔒 VERIFICATION REQUIRED 🔒\n\nYou must join ALL of the following:\n\n"
        kb = [[InlineKeyboardButton(f"💙 {c['name']}", url=c["link"])] for c in REQUIRED_CHATS]
        kb.append([InlineKeyboardButton("🔄 I've Joined! Check Again", callback_data="check_verification")])
        await reply_custom(update, msg + f"❌ Missing: {missing}", context, InlineKeyboardMarkup(kb))
        return

    await load_accounts()
    event_type = await get_current_event()
    limits = get_event_limits(event_type)
    
    timer_msg = ""
    if event_type != "default":
        timer = await get_event_timer(event_type)
        if timer: timer_msg = f"\n⏳ {EVENT_TYPES[event_type]['name']} ACTIVE! ({timer['hours']}h {timer['minutes']}m)\n"
        else: event_type, limits = "default", get_event_limits("default")
    
    msg = f"🎮 WELCOME TO THE GIVEAWAY! 🎮\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n📌 Event: {EVENT_TYPES[event_type]['name']}\n📊 Available Accounts:\n"
    for p_key, label in [("cpm1_normal", "CPM1 Normal"), ("cpm1_unlock", "CPM1 Unlock"), ("cpm2_normal", "CPM2 Normal"), ("cpm2_coin", "CPM2 Coin")]:
        count = len(ACCOUNT_POOLS.get(p_key, []))
        msg += f"  {'☑️' if count > 0 else '❌'} {label}: {count if count > 0 else 'SOLD OUT'}\n"
    msg += timer_msg + "\n👇 Select your account type:"
    
    kb = []
    for label, cb, pk in [("🚘 CPM1 Normal", "details_cpm1_normal", "cpm1_normal"), ("🚘 CPM1 Unlock", "details_cpm1_unlock", "cpm1_unlock"), ("💰 CPM2 Normal", "details_cpm2_normal", "cpm2_normal"), ("💰 CPM2 Coin", "details_cpm2_coin", "cpm2_coin")]:
        kb.append([InlineKeyboardButton(f"{label} {'☑️' if len(ACCOUNT_POOLS.get(pk, [])) > 0 else '❌'}", callback_data=cb)])
    kb.append([InlineKeyboardButton("ℹ️ More Info", callback_data="more_info")])
    await reply_custom(update, msg, context, InlineKeyboardMarkup(kb))

async def details_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try: await query.answer()
    except: pass
    data = query.data
    
    if data.startswith("details_"):
        account_type = data.replace("details_", "")
        if account_type not in ACCOUNT_DETAILS: return
        details_msg = ACCOUNT_DETAILS[account_type]
        keyboard = [
            [InlineKeyboardButton("🎯 CLAIM ACCOUNT", callback_data=f"claim_{account_type}")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="start_back")],
        ]
        await edit_custom(query, details_msg, reply_markup=InlineKeyboardMarkup(keyboard))

async def claim_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try: await query.answer()
    except: pass
    user_id = query.from_user.id
    chat_id = update.effective_chat.id
    data = query.data

    if data == "share_confirmed":
        await set_share_verified(user_id)
        await edit_custom(query, "✅ SHARE VERIFIED!\nClick /start to continue.", InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Start", callback_data="start_back")]]))
        return
    if data == "check_verification":
        is_member, _ = await check_membership(context, user_id, force_refresh=True)
        if is_member:
            await reset_warnings(user_id)
            await edit_custom(query, "✅ VERIFICATION SUCCESSFUL!", InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Start", callback_data="start_back")]]))
        else:
            await edit_custom(query, "❌ Still missing groups. Join and check again.", InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Check Again", callback_data="check_verification")]]))
        return
    if data == "start_back": await start(update, context)
    elif data == "admin_back": await admin_panel(update, context, query)
    elif data == "more_info":
        msg = "ℹ️ ABOUT THIS GIVEAWAY ℹ️\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n⚡ Owner: @Maarkryan 💙\n⚡ Powered by Mark Mwehehe\n\n📌 Required Chats:\n• 💙 TnnrCPM Channel (@TnnrCPM)\n• 💙 MarkMwehehe Store (@markmwehehestore)\n• 💙 Mark Mwehehe Main Channel (@markmwhehe)\n\n📌 Events:\n• Default: 1 per pool, 24h cooldown\n• Claim Again: 3 total, 1 hour\n• Party Time: 10 normal, 5 unlock/coin, 5 hours\n\n💎 Rules:\n• Must stay in all required groups\n• ⚠️ Leaving = warnings\n• 5 warnings = PERMANENT BAN\n\n🔥 Want more? Contact @Maarkryan."
        await edit_custom(query, msg)
    elif data.startswith("claim_"):
        if not await get_claim_enabled():
            await edit_custom(query, "🔒 CLAIMING IS CURRENTLY DISABLED 🔒")
            return

        acc_type = data.replace("claim_", "")
        evt = await get_current_event()
        can, msg = await can_claim_event(user_id, evt, acc_type)
        if not can:
            await edit_custom(query, f"❌ {msg}\nClick /start to return.")
            return
        
        await load_accounts()
        pool = ACCOUNT_POOLS.get(acc_type, [])
        if not pool:
            await edit_custom(query, f"😭 SORRY! All {acc_type.replace('_', ' ').upper()} accounts are SOLD OUT!")
            return
        
        acc = pool.pop(0)
        await save_accounts()
        await add_claimed(user_id, acc_type, acc["email"])
        await increment_event_claim(user_id, evt, acc_type)
        if evt == "default": await set_last_claim_time(user_id)
        await reset_warnings(user_id)
        
        msg = f"💎 CONGRATULATIONS! 💎\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n🎮 You claimed a {acc_type.replace('_', ' ').upper()} account!\n\n⚡ Details:\n📧 Email: {acc['email']}\n🔑 Password: {acc['password']}\n\n⚠️🔥 CHANGE PASSWORD OR EMAIL BRO! 🔥⚠️\n💎✅ USE BOT: @Mark_changer_bot 🚀\n\n💙 JOIN GC: {TNNR_GROUP_CHAT['link']}"
        await send_custom(chat_id, msg, context)
        try: await edit_custom(query, f"✅ CLAIMED!\nYou got a {acc_type.replace('_', ' ').upper()} account! Check the message above.")
        except: pass

    elif data.startswith("addaccount_"):
        pool_key = data.replace("addaccount_", "")
        context.user_data['add_account_pool'] = pool_key
        ADD_ACCOUNT_SESSIONS[user_id] = pool_key
        pool_name = pool_key.replace('_', ' ').upper()
        msg = f"📥 ADD ACCOUNTS TO: {pool_name}\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\nSend accounts in format:\n📧 email:password\n\nOr upload a .txt file.\n\n⚠️ Each line: email:password"
        await edit_custom(query, msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="admin_back")]]))

# ============================================================
# ✅ ADMIN PANEL & BUTTONS
# ============================================================
async def admin_panel(update=None, context=None, query=None):
    if update and update.effective_chat.type != "private": return
    if query and query.message.chat.type != "private": return
    user_id = query.from_user.id if query else update.effective_user.id
    if user_id != ADMIN_ID: return

    status = "ENABLED ✅" if await get_claim_enabled() else "DISABLED ❌"
    msg = f"👑 ADMIN PANEL 🥵\n━━━━━━━━━━━━━━━━━━━━━\n📊 Claim Status: {status}\n\nSelect an action:"
    kb = [
        [InlineKeyboardButton("📥 Add Accounts", callback_data="add_accounts_menu")],
        [InlineKeyboardButton("📊 Show Inventory", callback_data="show_inventory")],
        [InlineKeyboardButton("📋 Show Claimed Accounts (📄)", callback_data="show_claimed")],
        [InlineKeyboardButton("👹 Show Makulit Users", callback_data="show_makulit")],
        [InlineKeyboardButton("🗑️ Clear Pool", callback_data="clear_pool")],
        [InlineKeyboardButton("🔓 Unban User", callback_data="unban_user")],
        [InlineKeyboardButton("🎉 Start Claim Again", callback_data="start_claimagain")],
        [InlineKeyboardButton("🎊 Start Party Time", callback_data="start_partytime")],
        [InlineKeyboardButton("⏹️ End Event", callback_data="end_event")],
        [InlineKeyboardButton("📢 Send Announcement", callback_data="send_announcement")],
        [InlineKeyboardButton("🔒 Disable Claim" if await get_claim_enabled() else "🔓 Enable Claim", callback_data="toggle_claim")],
        [InlineKeyboardButton("🔙 Back to Main", callback_data="start_back")],
    ]
    if query: await edit_custom(query, msg, reply_markup=InlineKeyboardMarkup(kb))
    elif update: await reply_custom(update, msg, context, reply_markup=InlineKeyboardMarkup(kb))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try: await query.answer()
    except: pass
    data = query.data
    user_id = query.from_user.id
    if user_id != ADMIN_ID: return

    if data == "send_announcement":
        context.user_data['awaiting_announcement'] = True
        await edit_custom(query, "📢 SEND ANNOUNCEMENT\n━━━━━━━━━━━━━━━━━━━━━\n\nPlease type your announcement message below.\n📌 Sent to channels only.")
    
    elif data == "add_accounts_menu":
        await load_accounts()
        msg = "📥 SELECT ACCOUNT TYPE TO ADD:\n━━━━━━━━━━━━━━━━━━━━━\nChoose which pool:"
        kb = []
        for label, pk in [("🚘 CPM1 Normal", "cpm1_normal"), ("🚘 CPM1 Unlock", "cpm1_unlock"), ("💰 CPM2 Normal", "cpm2_normal"), ("💰 CPM2 Coin", "cpm2_coin")]:
            count = len(ACCOUNT_POOLS.get(pk, []))
            kb.append([InlineKeyboardButton(f"{label} {'❌⚠️' if count == 0 else '☑️'} ({count})", callback_data=f"addaccount_{pk}")])
        kb.append([InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_back")])
        await edit_custom(query, msg, reply_markup=InlineKeyboardMarkup(kb))
    
    elif data == "show_inventory":
        await load_accounts()
        msg = "📊 ACCOUNT INVENTORY\n━━━━━━━━━━━━━━━━━━━━━\n\n"
        for pk, label in [("cpm1_normal", "CPM1 Normal"), ("cpm1_unlock", "CPM1 Unlock"), ("cpm2_normal", "CPM2 Normal"), ("cpm2_coin", "CPM2 Coin")]:
            accs = ACCOUNT_POOLS.get(pk, [])
            if accs:
                msg += f"📌 {label} ({len(accs)} accounts):\n"
                for i, acc in enumerate(accs, 1): msg += f"  {i}. {acc['email']}:{acc['password']}\n"
                msg += "\n"
            else: msg += f"❌ {label}: EMPTY\n\n"
        await edit_custom(query, msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_back")]]))
    
    elif data == "show_claimed":
        claimed_data = await get_all_claimed()
        if not claimed_data:
            await edit_custom(query, "📋 CLAIMED ACCOUNTS\n━━━━━━━━━━━━━━━━━━━━━\n\n📭 No accounts have been claimed yet.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_back")]]))
            return
        
        file_content = "📋 CLAIMED ACCOUNTS\n━━━━━━━━━━━━━━━━━━━━━\n\n"
        claimed_by_user = {}
        for claim in claimed_data:
            uid = claim["user_id"]
            if uid not in claimed_by_user: claimed_by_user[uid] = []
            claimed_by_user[uid].append(claim)
        
        for uid, claims in claimed_by_user.items():
            file_content += f"👤 User ID: {uid}\n"
            for claim in claims:
                account_type = claim.get("type", "unknown").replace('_', ' ').upper()
                email = claim.get("email", "unknown")
                timestamp = claim.get("timestamp", "")[:16].replace('T', ' ')
                file_content += f"  ✅ {account_type}: {email} ({timestamp})\n"
            file_content += "\n"
        
        filename = f"claimed_accounts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        await send_file(user_id, filename, file_content, context, caption="📋 Here is the list of claimed accounts:")
        await asyncio.sleep(0.5); await admin_panel(update, context, query)
    
    elif data == "show_makulit":
        makulit = await get_makulit_users()
        if not makulit: msg = "👀 No annoying users detected. All clean! 🎉"
        else:
            msg = "👹 MAKULIT USERS 👀\n━━━━━━━━━━━━━━━━━━━━━\n\n"
            for user in makulit: msg += f"• User ID: {user['user_id']} – Warnings: {user['warnings']}/5\n"
        await edit_custom(query, msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_back")]]))
    
    elif data == "clear_pool":
        kb = [[InlineKeyboardButton("🚘 CPM1 Normal", callback_data="clearpool_cpm1_normal")], [InlineKeyboardButton("🚘 CPM1 Unlock", callback_data="clearpool_cpm1_unlock")], [InlineKeyboardButton("💰 CPM2 Normal", callback_data="clearpool_cpm2_normal")], [InlineKeyboardButton("💰 CPM2 Coin", callback_data="clearpool_cpm2_coin")], [InlineKeyboardButton("🔙 Back", callback_data="admin_back")]]
        await edit_custom(query, "🗑️ SELECT POOL TO CLEAR:", reply_markup=InlineKeyboardMarkup(kb))
    
    elif data.startswith("clearpool_"):
        pool_key = data.replace("clearpool_", "")
        await load_accounts()
        ACCOUNT_POOLS[pool_key] = []
        await save_accounts()
        await edit_custom(query, f"✅ Cleared all accounts in {pool_key.replace('_', ' ').upper()}")
        await asyncio.sleep(0.5); await admin_panel(update, context, query)
    
    elif data == "unban_user":
        context.user_data['awaiting_unban'] = True
        await edit_custom(query, "🔓 Send the USER ID to unban:\n\nExample: 6531314640")
    
    elif data == "start_claimagain" or data == "start_partytime":
        evt = data.replace("start_", "")
        await set_event_timer(evt, EVENT_TYPES[evt]["timer_hours"])
        await admin_panel(update, context, query)
        await send_custom(user_id, f"✅ {EVENT_TYPES[evt]['name']} Started!", context)
    
    elif data == "end_event":
        await db_delete("giveaway/event_timer/claimagain")
        await db_delete("giveaway/event_timer/partytime")
        await admin_panel(update, context, query)
        await send_custom(user_id, "✅ Event ended! 🔥", context)
    
    elif data == "toggle_claim":
        await set_claim_enabled(not await get_claim_enabled())
        await admin_panel(update, context, query)

# ============================================================
# ✅ MESSAGE & FILE UPLOAD HANDLER
# ============================================================
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or update.effective_chat.type != "private": return
    user_id = update.effective_user.id
    if user_id != ADMIN_ID: return

    text = update.message.text.strip() if update.message.text else None
    document = update.message.document

    if context.user_data.get('awaiting_announcement'):
        if not text:
            await reply_custom(update, "❌ Please send a text message.", context)
            return
        await send_announcement_background(context, text, "📢 ANNOUNCEMENT", user_id)
        context.user_data.pop('awaiting_announcement', None)
        await reply_custom(update, "✅ Announcement is being sent.", context)
        await admin_panel(update, context)
        return

    if context.user_data.get('awaiting_unban'):
        try:
            target_id = int(text)
            await db_delete(f"giveaway/banned/{target_id}")
            await reset_warnings(target_id)
            await reply_custom(update, f"✅ Unbanned user {target_id}", context)
            context.user_data.pop('awaiting_unban', None)
        except:
            await reply_custom(update, "❌ Invalid USER ID.", context)
        return

    pool_key = ADD_ACCOUNT_SESSIONS.get(user_id)
    if pool_key:
        accounts = []
        if document:
            try:
                file = await document.get_file()
                content = (await file.download_as_bytearray()).decode("utf-8")
                accounts = [line.strip() for line in content.splitlines() if ':' in line]
            except Exception as e:
                await reply_custom(update, f"❌ Failed to read file: {e}", context)
                return
        else:
            if not text: return
            accounts = [line.strip() for line in text.splitlines() if ':' in line]

        if not accounts:
            await reply_custom(update, "❌ No valid accounts found. Format: email:password", context)
            return

        await load_accounts()
        added = 0
        for acc in accounts:
            if ':' in acc:
                email, password = acc.split(':', 1)
                ACCOUNT_POOLS[pool_key].append({"email": email.strip(), "password": password.strip()})
                added += 1
        await save_accounts()
        ADD_ACCOUNT_SESSIONS.pop(user_id, None)
        await reply_custom(update, f"✅ Added {added} accounts to {pool_key.replace('_', ' ').upper()}!\n📊 Total: {len(ACCOUNT_POOLS.get(pool_key, []))} accounts", context)

# ============================================================
# ✅ LEFT CHAT MEMBER HANDLER (Warnings)
# ============================================================
async def left_chat_member_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.left_chat_member: return
    chat_member = update.left_chat_member
    user = chat_member.from_user
    if user.id == context.bot.id: return
    if chat_member.new_chat_member.status not in ["left", "kicked"]: return
    
    chat = chat_member.chat
    chat_id = chat.id
    chat_username = chat.username or str(chat_id)
    
    for req in REQUIRED_CHATS:
        req_id = req["id"] if isinstance(req["id"], str) else int(req["id"])
        if req_id == chat_id or req_id == chat_username:
            warnings = await add_warning(user.id)
            try:
                await context.bot.send_message(
                    chat_id=user.id,
                    text=f"⚠️ WARNING #{warnings}/5 ⚠️\n\nYou left {req['name']}!\n🔄 Warnings: {warnings}/5\n❌ 5 warnings = PERMANENT BAN\n\n💙 Please rejoin."
                )
            except: pass
            break

# ============================================================
# ✅ ADMIN COMMANDS
# ============================================================
async def claimagain_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    await set_event_timer("claimagain", EVENT_TYPES["claimagain"]["timer_hours"])
    await reply_custom(update, "✅ Claim Again event started!\n💙 @Cpm_2test_bot", context)

async def undermaintinance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    broadcast_msg = "🛠️ UNDER MAINTENANCE ⚡5\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n⚠️ The bot is currently under maintenance. ⚡5\n\n🔥 We are adding new accounts and improving the system!\n⏳ Please wait a few minutes and try again.\n\n💎 We apologize for the inconvenience.\n👑 Stay tuned for more updates!\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n💙 @Cpm_2test_bot"
    await broadcast_message_background(context, broadcast_msg, "🛠️ MAINTENANCE ⚡5", update.effective_user.id)
    await reply_custom(update, "✅ Maintenance broadcast is being sent.", context)

async def admin_redirect_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        await admin_panel(update, context)

# ============================================================
# ✅ MAIN EXECUTION
# ============================================================
def main():
    print("🚀 Starting Full Bot Framework (LAG-FREE)...")
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("addaccount", admin_redirect_command))
    application.add_handler(CommandHandler("showaccounts", admin_redirect_command))
    application.add_handler(CommandHandler("showthemakulit", admin_redirect_command))
    application.add_handler(CommandHandler("clearpool", admin_redirect_command))
    application.add_handler(CommandHandler("unban", admin_redirect_command))
    application.add_handler(CommandHandler("claimagain", claimagain_command))
    application.add_handler(CommandHandler("undermaintinance", undermaintinance_command))

    application.add_handler(CallbackQueryHandler(details_handler, pattern="^details_"))
    application.add_handler(CallbackQueryHandler(claim_handler, pattern="^(claim_|addaccount_|check_verification|more_info|start_back|admin_back|share_confirmed)"))
    application.add_handler(CallbackQueryHandler(button_handler, pattern="^(add_accounts_menu|show_inventory|show_claimed|show_makulit|clear_pool|clearpool_|unban_user|start_claimagain|start_partytime|end_event|send_announcement|toggle_claim|admin_back)"))

    application.add_handler(MessageHandler(filters.TEXT | filters.Document.ALL, message_handler))
    application.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, left_chat_member_handler))
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    loop.create_task(auto_save_db())
    loop.create_task(keep_alive_pinger())
    
    print("✅ Complete Features Loaded")
    print("🤖 Polling Bot Updates...")
    
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    main()
