import json, time, re, os, random as rnd, asyncio, aiohttp, logging, threading
from datetime import datetime, timedelta, timezone
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, MessageEntity
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.request import HTTPXRequest
from flask import Flask

app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return "🎁 GIVEAWAY BOT - RUNNING 24/7!"

@app_flask.route('/health')
def health():
    return "OK"

# ============================================================
# ✅ CONFIGURATION
# ============================================================
TOKEN = "8960961388:AAFeBpbgZNMDVLogNfl3GSeFnAxqdtRpy54"
ADMIN_ID = 6531314640
COOLDOWN_HOURS = 24

REQUIRED_CHATS = [
    {"id": "@TnnrCPM", "name": "TnnrCPM Channel"},
    {"id": "@TnnrChat", "name": "TnnrChat Group"},
    {"id": "@markmwehehestore", "name": "MarkMwehehe Store"},
    {"id": "@markmwhehe", "name": "Mark Mwehehe Main Channel"},
    {"id": -1003994249946, "name": "Tnnr Main Group"},
]

FIREBASE_API_KEY = "ph2yty6YZsJCU4oOFZi901HN4sGo7Ehtie94p7KX"
DB_URL = "https://cpm2bpt-default-rtdb.europe-west1.firebasedatabase.app"

# ============================================================
# ✅ CUSTOM EMOJI MAPPING (LAHAT NG BINIGAY MO)
# ============================================================
CUSTOM_EMOJI_MAP = {
    '😂': '5406913184810409829', '😄': '5386587088873331829',
    '😍': '5323470315370585285', '😭': '5379656338802482888',
    '🤑': '5427107837568360763', '👑': '5938534225140519372',
    '🔥': '6001061381237903602', '⚡': '6100289024289672793',
    '💎': '6064293500382350516', '❌': '6064642968986323772',
    '🤨': '6134245834595765950', '👹': '6142914800880979809',
    '👀': '5834733550020072624', '💙': '6269557847248342937',
    '⚠️': '6100590432209604692', '😆': '5375135722514685501',
    '😮': '5456662929166309849', '😎': '5195360348693078341',
    '👤': '5258011929993026890', '🎮': '5258508428212445001',
    '🚘': '5366286487862124799', '✅': '5197288647275071607',
    '🎉': '6001197385672298829', '📁': '5357315181649076022',
    '📊': '5192886773948107844', '⏳': '5192988444413938411',
    '🚀': '5190768392998504411', '💰': '5192683149548605430',
    '📲': '5192998636371330526',
    '💃': '5373112999076699207', '😠': '5348119373200506812',
    '😡': '5251301176737013980', '🦁': '5980821811711972473',
    '☑️': '5936230155574842929', '👌': '6001451188174723066',
    '🗿': '6001226634399585063', '🚗': '5375593780776805206',
    '🏎': '5391327195169831190', '😌': '5958585443170651565',
    '⚡1': '6100277122935295595', '⚡2': '6100472578307002133',
    '⚡3': '6102404476071579522', '⚡4': '6100671388048166850',
    '⚡5': '6100278127957643014',
    '🥵': '6307832826263768178',  # ADMIN-ONLY
}

def get_custom_entities(text):
    entities = []
    offset = 0
    i = 0
    while i < len(text):
        ch = text[i]
        if i + 1 < len(text) and text[i:i+2] == '☑️':
            ch = '☑️'
            utf16_len = 2
            i += 2
        elif i + 1 < len(text) and text[i:i+2] == '✔️':
            ch = '✔️'
            utf16_len = 2
            i += 2
        elif i + 1 < len(text) and text[i:i+2] in ['⚡1', '⚡2', '⚡3', '⚡4', '⚡5']:
            ch = text[i:i+2]
            utf16_len = 2
            i += 2
        else:
            utf16_len = len(ch.encode('utf-16-le')) // 2
            i += 1
        
        if ch in CUSTOM_EMOJI_MAP:
            entities.append(MessageEntity(
                type="custom_emoji",
                offset=offset,
                length=utf16_len,
                custom_emoji_id=CUSTOM_EMOJI_MAP[ch]
            ))
        offset += utf16_len
    return entities

async def send_custom(chat_id, text, context, reply_markup=None):
    entities = get_custom_entities(text)
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=None,
            entities=entities if entities else None
        )
    except Exception as e:
        print(f"⚠️ Custom emoji error: {e}. Sending without entities.")
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=None
        )

async def reply_custom(update, text, context, reply_markup=None):
    await send_custom(update.effective_chat.id, text, context, reply_markup)

async def edit_custom(query, text, reply_markup=None):
    entities = get_custom_entities(text)
    try:
        await query.edit_message_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=None,
            entities=entities if entities else None
        )
    except Exception as e:
        if "Message is not modified" in str(e):
            pass
        else:
            try:
                await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode=None)
            except:
                pass

# ============================================================
# ✅ FIREBASE HELPERS
# ============================================================
def db_put(path, data):
    url = f"{DB_URL}/{path}.json?auth={FIREBASE_API_KEY}"
    return requests.put(url, json=data).status_code in (200, 204)

def db_get(path):
    url = f"{DB_URL}/{path}.json?auth={FIREBASE_API_KEY}"
    r = requests.get(url)
    return r.json() if r.status_code == 200 else None

def db_delete(path):
    url = f"{DB_URL}/{path}.json?auth={FIREBASE_API_KEY}"
    return requests.delete(url).status_code in (200, 204)

def db_push(path, data):
    url = f"{DB_URL}/{path}.json?auth={FIREBASE_API_KEY}"
    r = requests.post(url, json=data)
    return r.status_code in (200, 204)

# ============================================================
# ✅ GIVEAWAY DATA
# ============================================================
ACCOUNT_POOLS = {
    "cpm1_normal": [],
    "cpm2_normal": [],
    "cpm1_unlock": [],
    "cpm2_coin": [],
}

ADD_ACCOUNT_SESSIONS = {}
MEMBERSHIP_CACHE = {}

# ============================================================
# ✅ EVENT SYSTEM
# ============================================================
EVENT_TYPES = {
    "default": {
        "name": "Default",
        "normal_limit": 1,
        "unlock_coin_limit": 1,
        "cooldown_hours": 24,
        "timer_hours": 0,
    },
    "claimagain": {
        "name": "Claim Again",
        "normal_limit": 3,
        "unlock_coin_limit": 3,
        "cooldown_hours": 0,
        "timer_hours": 1,
    },
    "partytime": {
        "name": "Party Time",
        "normal_limit": 10,
        "unlock_coin_limit": 5,
        "cooldown_hours": 0,
        "timer_hours": 5,
    }
}

def get_event_limits(event_type):
    return EVENT_TYPES.get(event_type, EVENT_TYPES["default"])

def get_event_claim_count(user_id, event_type):
    data = db_get(f"giveaway/event_claims/{user_id}/{event_type}") or {}
    return {
        "normal": data.get("normal", 0),
        "unlock": data.get("unlock", 0),
        "coin": data.get("coin", 0),
        "total": data.get("total", 0)
    }

def increment_event_claim(user_id, event_type, account_type):
    limits = get_event_limits(event_type)
    current = get_event_claim_count(user_id, event_type)
    is_unlock = "unlock" in account_type
    is_coin = "coin" in account_type
    
    if is_unlock:
        current["unlock"] += 1
    elif is_coin:
        current["coin"] += 1
    else:
        current["normal"] += 1
    current["total"] += 1
    
    db_put(f"giveaway/event_claims/{user_id}/{event_type}", current)
    return current

def can_claim_event(user_id, event_type, account_type):
    limits = get_event_limits(event_type)
    current = get_event_claim_count(user_id, event_type)
    
    is_unlock = "unlock" in account_type
    is_coin = "coin" in account_type
    
    if is_unlock or is_coin:
        if current["unlock"] if is_unlock else current["coin"] >= limits["unlock_coin_limit"]:
            return False, f"You've reached the max {limits['unlock_coin_limit']} {account_type.upper()} accounts for this event! ⚠️"
    else:
        if current["normal"] >= limits["normal_limit"]:
            return False, f"You've reached the max {limits['normal_limit']} normal accounts for this event! ⚠️"
    
    if current["total"] >= limits["normal_limit"] + limits["unlock_coin_limit"] * 2:
        return False, "You've reached the total max accounts for this event! ⚠️"
    
    return True, None

def set_event_timer(event_type, duration_hours):
    try:
        expiry = datetime.now(timezone.utc) + timedelta(hours=duration_hours)
        db_put(f"giveaway/event_timer/{event_type}", {
            "start": datetime.now(timezone.utc).isoformat(),
            "expiry": expiry.isoformat(),
            "active": True
        })
        return True
    except Exception as e:
        print(f"⚠️ Error setting event timer: {e}")
        return False

def get_event_timer(event_type):
    data = db_get(f"giveaway/event_timer/{event_type}")
    if not data:
        return None
    expiry = datetime.fromisoformat(data["expiry"])
    if datetime.now(timezone.utc) >= expiry:
        db_delete(f"giveaway/event_timer/{event_type}")
        return None
    remaining = expiry - datetime.now(timezone.utc)
    return {
        "expiry": expiry,
        "remaining": remaining,
        "hours": remaining.seconds // 3600,
        "minutes": (remaining.seconds % 3600) // 60
    }

def is_event_active(event_type):
    timer = get_event_timer(event_type)
    return timer is not None

def get_current_event():
    if is_event_active("partytime"):
        return "partytime"
    elif is_event_active("claimagain"):
        return "claimagain"
    return "default"

def load_accounts():
    data = db_get("giveaway/accounts") or {}
    for key in ACCOUNT_POOLS:
        ACCOUNT_POOLS[key] = data.get(key, [])

def save_accounts():
    db_put("giveaway/accounts", ACCOUNT_POOLS)

def get_claimed(user_id):
    return db_get(f"giveaway/claimed/{user_id}") or []

def add_claimed(user_id, account_type, email):
    claimed = get_claimed(user_id)
    claimed.append({"type": account_type, "email": email, "timestamp": datetime.now().isoformat()})
    db_put(f"giveaway/claimed/{user_id}", claimed)

def has_claimed(user_id, account_type):
    claimed = get_claimed(user_id)
    return any(c["type"] == account_type for c in claimed)

def get_all_claimed():
    claimed_data = db_get("giveaway/claimed") or {}
    result = []
    for user_id, claims in claimed_data.items():
        for claim in claims:
            result.append({
                "user_id": int(user_id),
                "type": claim.get("type", "unknown"),
                "email": claim.get("email", "unknown"),
                "timestamp": claim.get("timestamp", "unknown")
            })
    return result

def get_warnings(user_id):
    return db_get(f"giveaway/warnings/{user_id}") or 0

def add_warning(user_id):
    count = get_warnings(user_id) + 1
    db_put(f"giveaway/warnings/{user_id}", count)
    return count

def reset_warnings(user_id):
    db_delete(f"giveaway/warnings/{user_id}")

def is_banned(user_id):
    return db_get(f"giveaway/banned/{user_id}") is not None

def ban_user(user_id):
    db_put(f"giveaway/banned/{user_id}", True)

def get_makulit_users():
    warnings = db_get("giveaway/warnings") or {}
    result = []
    for uid, count in warnings.items():
        if count > 0:
            result.append({"user_id": int(uid), "warnings": count})
    return sorted(result, key=lambda x: x["warnings"], reverse=True)

def set_share_verified(user_id):
    db_put(f"giveaway/share_verified/{user_id}", True)

def is_share_verified(user_id):
    return db_get(f"giveaway/share_verified/{user_id}") is not None

def get_last_claim_time(user_id):
    data = db_get(f"giveaway/last_claim/{user_id}")
    if data and data.get("timestamp"):
        return datetime.fromisoformat(data["timestamp"])
    return None

def set_last_claim_time(user_id):
    db_put(f"giveaway/last_claim/{user_id}", {"timestamp": datetime.now().isoformat()})

def can_claim(user_id):
    last = get_last_claim_time(user_id)
    if not last:
        return True, None
    cooldown_end = last + timedelta(hours=COOLDOWN_HOURS)
    if datetime.now() >= cooldown_end:
        return True, None
    remaining = cooldown_end - datetime.now()
    hours = remaining.seconds // 3600
    minutes = (remaining.seconds % 3600) // 60
    return False, f"{hours}h {minutes}m"

def get_all_users():
    try:
        data = db_get("giveaway/users") or {}
        return [int(uid) for uid in data.keys()]
    except Exception as e:
        print(f"⚠️ Error getting users: {e}")
        return []

def add_user(user_id):
    db_put(f"giveaway/users/{user_id}", {"timestamp": datetime.now().isoformat()})

async def check_membership(context, user_id):
    cache_key = f"{user_id}"
    if cache_key in MEMBERSHIP_CACHE:
        cached_result, cached_time = MEMBERSHIP_CACHE[cache_key]
        if (datetime.now() - cached_time).seconds < 15:
            return cached_result

    for chat in REQUIRED_CHATS:
        try:
            chat_id = chat["id"] if isinstance(chat["id"], str) else int(chat["id"])
            member = await context.bot.get_chat_member(chat_id, user_id)
            if member.status not in ["member", "administrator", "creator"]:
                MEMBERSHIP_CACHE[cache_key] = ((False, chat["name"]), datetime.now())
                return False, chat["name"]
        except Exception:
            MEMBERSHIP_CACHE[cache_key] = ((False, chat["name"]), datetime.now())
            return False, chat["name"]

    MEMBERSHIP_CACHE[cache_key] = ((True, None), datetime.now())
    return True, None

async def broadcast_message(context, msg, title="📢 ANNOUNCEMENT"):
    try:
        users = get_all_users()
        if not users:
            return 0, 0
        
        header = f"{title}\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        full_msg = header + msg
        
        success = 0
        failed = 0
        for uid in users:
            try:
                await send_custom(uid, full_msg, context)
                success += 1
                await asyncio.sleep(0.05)
            except Exception as e:
                print(f"⚠️ Failed to send to {uid}: {e}")
                failed += 1
        return success, failed
    except Exception as e:
        print(f"⚠️ Broadcast error: {e}")
        return 0, 0

# ============================================================
# ✅ ACCOUNT DETAILS (WITH EMOJIS)
# ============================================================
ACCOUNT_DETAILS = {
    "cpm1_normal": (
        "🚘 CPM1 NORMAL GIVEAWAY ACCOUNT\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📌 Account Features:\n"
        "  ✅ 50M Cash (Max)\n"
        "  💰 500K / 30K Coins! (Random)\n"
        "  🆔 Random ID!\n"
        "  🏠 Houses & Clothes\n"
        "  🔓 Everything Unlocked!\n\n"
        "⚡ One account per game – choose wisely!\n\n"
        "👇 Click the button below to claim:"
    ),
    "cpm1_unlock": (
        "🚘 CPM1 UNLOCK ALL CARS GIVEAWAY ACCOUNT\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📌 Account Features:\n"
        "  ✅ 50M Cash (Max)\n"
        "  💰 500K / 30K Coins! (Random)\n"
        "  🆔 Random ID!\n"
        "  🏎️ UNLOCK ALL CARS 🏎️\n"
        "  🏠 Houses & Clothes\n"
        "  🔓 Everything Unlocked!\n\n"
        "⚡ One account per game – choose wisely!\n\n"
        "👇 Click the button below to claim:"
    ),
    "cpm2_coin": (
        "💰 CPM2 COIN GIVEAWAY ACCOUNT\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📌 Account Features:\n"
        "  ✅ 50M Cash (Max)\n"
        "  💰 11K-13K Coins\n"
        "  🎯 20 Slots Unlocked!\n"
        "  👑 King Rank!\n"
        "  🚗 4-20 Random Cars\n"
        "  🎨 Full Customization!\n"
        "  🏠 Houses + Clothes\n\n"
        "⚡ One account per game – choose wisely!\n\n"
        "👇 Click the button below to claim:"
    ),
    "cpm2_normal": (
        "💰 CPM2 NORMAL GIVEAWAY ACCOUNT\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📌 Account Features:\n"
        "  ✅ 50M Cash (Max)\n"
        "  🎯 20 Slots Unlocked!\n"
        "  👑 King Rank!\n"
        "  🚗 4-20 Random Cars\n"
        "  🎨 Full Customization!\n"
        "  🏠 Houses + Clothes\n\n"
        "⚡ One account per game – choose wisely!\n\n"
        "👇 Click the button below to claim:"
    )
}

# ============================================================
# ✅ START COMMAND
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    add_user(user_id)

    if is_banned(user_id):
        await reply_custom(update, "⛔ BANNED ⛔\n\nYou have been permanently banned.\nContact @Maarkryan.", context)
        return

    if not is_share_verified(user_id):
        msg = (
            "📢 SHARE TO WIN! 📢\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🔥 To claim your free account, you must share this bot to 3-5 groups!\n\n"
            "⚡ Why?\n"
            "• Help others discover this giveaway\n"
            "• Show your support\n"
            "• It's fast and easy!\n\n"
            "👇 Click the button below to share:"
        )
        keyboard = [
            [InlineKeyboardButton("📤 Share to Groups", switch_inline_query="🔥 FREE CPM1/CPM2 ACCOUNTS! Join the giveaway! @Cpm_2test_bot")],
            [InlineKeyboardButton("✅ I've Shared!", callback_data="share_confirmed")],
        ]
        await reply_custom(update, msg, context, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    warnings = get_warnings(user_id)
    if warnings > 0:
        if warnings >= 5:
            ban_user(user_id)
            await reply_custom(update, "🚫 YOU HAVE BEEN BANNED 🚫\n\nYou reached 5 warnings.\nContact @Maarkryan.", context)
            return
        await reply_custom(update, f"⚠️ WARNING #{warnings}/5 ⚠️\n\nYou left a required group.\n🔄 Warnings: {warnings}/5\n❌ 5 warnings = PERMANENT BAN\n\n💙 Stay in all groups.", context)

    is_member, missing = await check_membership(context, user_id)
    if not is_member:
        msg = "🔒 VERIFICATION REQUIRED 🔒\n\nYou must join ALL of the following:\n\n"
        for chat in REQUIRED_CHATS:
            msg += f"• {chat['name']}\n"
        msg += f"\n❌ Missing: {missing}\n\n👇 Click to join:"
        keyboard = [
            [InlineKeyboardButton("💙 TnnrCPM Channel", url="https://t.me/TnnrCPM")],
            [InlineKeyboardButton("💙 TnnrChat Group", url="https://t.me/TnnrChat")],
            [InlineKeyboardButton("💙 MarkMwehehe Store", url="https://t.me/markmwehehestore")],
            [InlineKeyboardButton("💙 Mark Mwehehe Main Channel", url="https://t.me/markmwhehe")],
            [InlineKeyboardButton("🔄 I've Joined! Check Again", callback_data="check_verification")],
        ]
        await reply_custom(update, msg, context, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    load_accounts()
    event_type = get_current_event()
    limits = get_event_limits(event_type)
    
    timer_msg = ""
    if event_type != "default":
        timer = get_event_timer(event_type)
        if timer:
            event_name = EVENT_TYPES[event_type]["name"]
            timer_msg = f"\n⏳ {event_name} EVENT ACTIVE!\n"
            timer_msg += f"🕐 Time remaining: {timer['hours']}h {timer['minutes']}m\n"
            timer_msg += f"⚡ Max claims: {limits['normal_limit']} normal, {limits['unlock_coin_limit']} unlock/coin\n"
        else:
            timer_msg = "\n⚠️ Event has ended! Returning to default mode.\n"
            event_type = "default"
            limits = get_event_limits("default")
    
    msg = (
        "🎮 WELCOME TO THE GIVEAWAY! 🎮\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 Event: {EVENT_TYPES[event_type]['name']}\n"
        f"📊 Available Accounts:\n"
    )
    
    all_sold_out = True
    for pool_key, label in [
        ("cpm1_normal", "CPM1 Normal"),
        ("cpm1_unlock", "CPM1 Unlock All Cars"),
        ("cpm2_normal", "CPM2 Normal"),
        ("cpm2_coin", "CPM2 Coin Account"),
    ]:
        count = len(ACCOUNT_POOLS.get(pool_key, []))
        if event_type != "default" and not is_event_active(event_type):
            msg += f"  ❌ {label}: EVENT ENDED\n"
        elif count == 0:
            msg += f"  ❌ {label}: SOLD OUT ⚠️\n"
        else:
            all_sold_out = False
            msg += f"  ☑️ {label}: {count} available\n"
    
    if all_sold_out and (event_type == "default" or is_event_active(event_type)):
        msg += "\n⚠️ ALL ACCOUNTS ARE SOLD OUT! ⚠️\n"
        msg += "🔥 Stay tuned for the next giveaway!\n"
        msg += "👤 Contact @Maarkryan for premium accounts."
    
    msg += timer_msg
    
    if event_type != "default":
        claims = get_event_claim_count(user_id, event_type)
        msg += f"\n📋 Your claims this event:\n"
        msg += f"  Normal: {claims['normal']}/{limits['normal_limit']}\n"
        msg += f"  Unlock/Coin: {claims['unlock'] + claims['coin']}/{limits['unlock_coin_limit'] * 2}\n"
        msg += f"  Total: {claims['total']}/{limits['normal_limit'] + limits['unlock_coin_limit'] * 2}\n"
    
    msg += "\n👇 Select your account type:"
    
    keyboard = []
    for label, callback, pool_key in [
        ("🚘 CPM1 Normal", "details_cpm1_normal", "cpm1_normal"),
        ("🚘 CPM1 Unlock All Cars", "details_cpm1_unlock", "cpm1_unlock"),
        ("💰 CPM2 Normal", "details_cpm2_normal", "cpm2_normal"),
        ("💰 CPM2 Coin Account", "details_cpm2_coin", "cpm2_coin"),
    ]:
        count = len(ACCOUNT_POOLS.get(pool_key, []))
        if count == 0:
            display = f"{label} ❌⚠️ SOLD OUT"
        elif event_type != "default" and not is_event_active(event_type):
            display = f"{label} ⏳ EVENT ENDED"
        else:
            is_unlock = "unlock" in pool_key
            is_coin = "coin" in pool_key
            limits = get_event_limits(event_type)
            claims = get_event_claim_count(user_id, event_type)
            reached = False
            if is_unlock or is_coin:
                if (is_unlock and claims["unlock"] >= limits["unlock_coin_limit"]) or (is_coin and claims["coin"] >= limits["unlock_coin_limit"]):
                    reached = True
            else:
                if claims["normal"] >= limits["normal_limit"]:
                    reached = True
            
            if reached:
                display = f"{label} ✅ LIMIT REACHED"
            else:
                display = f"{label} ☑️"
        keyboard.append([InlineKeyboardButton(display, callback_data=callback)])
    
    keyboard.append([InlineKeyboardButton("ℹ️ More Info", callback_data="more_info")])
    await reply_custom(update, msg, context, reply_markup=InlineKeyboardMarkup(keyboard))

async def share_confirmed_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except:
        pass
    user_id = query.from_user.id
    set_share_verified(user_id)
    await edit_custom(
        query,
        "✅ SHARE VERIFIED! ✅\n\nThank you for sharing! 🎉\nNow let's verify your group memberships...\n\nClick /start to continue.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Start", callback_data="start_back")]])
    )

# ============================================================
# ✅ DETAILS HANDLER
# ============================================================
async def details_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except:
        pass
    data = query.data
    
    if data.startswith("details_"):
        account_type = data.replace("details_", "")
        
        if account_type not in ACCOUNT_DETAILS:
            await edit_custom(query, "❌ Invalid account type. Please try again.")
            return
        
        details_msg = ACCOUNT_DETAILS[account_type]
        
        keyboard = [
            [InlineKeyboardButton("🎯 CLAIM ACCOUNT", callback_data=f"claim_{account_type}")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="start_back")],
        ]
        
        await edit_custom(query, details_msg, reply_markup=InlineKeyboardMarkup(keyboard))

# ============================================================
# ✅ CLAIM HANDLER
# ============================================================
async def claim_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except:
        pass
    user_id = query.from_user.id
    chat_id = update.effective_chat.id
    data = query.data

    if data == "share_confirmed":
        await share_confirmed_handler(update, context)
        return

    if data == "check_verification":
        is_member, missing = await check_membership(context, user_id)
        if is_member:
            reset_warnings(user_id)
            await edit_custom(
                query,
                "✅ VERIFICATION SUCCESSFUL! ✅\n\nYou are now verified! Click /start to claim.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Start", callback_data="start_back")]])
            )
        else:
            await edit_custom(
                query,
                f"❌ Still missing: {missing}\n\nPlease join ALL groups.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💙 TnnrCPM Channel", url="https://t.me/TnnrCPM")],
                    [InlineKeyboardButton("💙 TnnrChat Group", url="https://t.me/TnnrChat")],
                    [InlineKeyboardButton("💙 MarkMwehehe Store", url="https://t.me/markmwehehestore")],
                    [InlineKeyboardButton("💙 Mark Mwehehe Main Channel", url="https://t.me/markmwhehe")],
                    [InlineKeyboardButton("🔄 I've Joined! Check Again", callback_data="check_verification")],
                ])
            )
        return

    if data == "start_back":
        await start(update, context)
        return

    if data == "admin_back":
        await admin_panel(update, context, query)
        return

    if data == "more_info":
        msg = (
            "ℹ️ ABOUT THIS GIVEAWAY ℹ️\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "⚡ Owner: @Maarkryan 💙\n"
            "⚡ Powered by Mark Mwehehe\n\n"
            "📌 Required Chats:\n"
            "• 💙 TnnrCPM Channel (@TnnrCPM)\n"
            "• 💙 TnnrChat Group (@TnnrChat)\n"
            "• 💙 MarkMwehehe Store (@markmwehehestore)\n"
            "• 💙 Mark Mwehehe Main Channel (@markmwhehe)\n\n"
            "📌 Account Types:\n"
            "• 🚘 CPM1 Normal\n"
            "• 🚘 CPM1 Unlock All Cars\n"
            "• 💰 CPM2 Normal\n"
            "• 💰 CPM2 Coin Account\n\n"
            "📌 Events:\n"
            "• Default: 1 per pool, 24h cooldown\n"
            "• Claim Again: 3 total, 1 hour\n"
            "• Party Time: 10 normal, 5 unlock/coin, 5 hours\n\n"
            "💎 Rules:\n"
            "• Must stay in all required groups\n"
            "• ⚠️ Leaving = warnings\n"
            "• 5 warnings = PERMANENT BAN\n"
            "• ⏳ Each event has its own timer\n\n"
            "🔥 Want more? Contact @Maarkryan."
        )
        await edit_custom(query, msg)
        return

    if data.startswith("claim_"):
        account_type = data.replace("claim_", "")
        event_type = get_current_event()
        limits = get_event_limits(event_type)
        
        if event_type != "default" and not is_event_active(event_type):
            await edit_custom(
                query,
                f"⏳ EVENT ENDED! ⏳\n\n"
                f"The {EVENT_TYPES[event_type]['name']} event has ended.\n"
                f"🔥 Please wait for the next event!\n\n"
                f"💙 Click /start to check current status."
            )
            return
        
        can_claim_event_result, msg = can_claim_event(user_id, event_type, account_type)
        if not can_claim_event_result:
            await edit_custom(query, f"❌ LIMIT REACHED! ❌\n\n{msg}\n\n💙 Click /start to check current status.")
            return

        load_accounts()
        pool = ACCOUNT_POOLS.get(account_type, [])
        if not pool:
            await edit_custom(
                query,
                f"😭 SORRY! 😭\n\nAll {account_type.replace('_', ' ').upper()} accounts have been claimed.\n🔥 Stay tuned for the next giveaway!\n\n👤 Contact @Maarkryan for premium accounts."
            )
            return

        account = pool.pop(0)
        save_accounts()
        add_claimed(user_id, account_type, account["email"])
        increment_event_claim(user_id, event_type, account_type)
        
        if event_type == "default":
            set_last_claim_time(user_id)
        reset_warnings(user_id)

        msg = (
            f"💎 CONGRATULATIONS! 💎\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎮 You claimed a {account_type.replace('_', ' ').upper()} account!\n\n"
            f"⚡ Your Account Details:\n"
            f"📧 Email: {account['email']}\n"
            f"🔑 Password: {account['password']}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚠️🔥 CHANGE THE PASSWORD OR EMAIL AFTER YOU CLAIM IT BRO! 🔥⚠️\n\n"
            f"💎✅ WE OFFERING MY OWN CHANGE EMAIL&PASSWORD BOT BRO! ✅💎\n"
            f"💙🔄 @Mark_changer_bot 🚀\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        )
        
        if event_type != "default":
            claims = get_event_claim_count(user_id, event_type)
            msg += f"📋 Event: {EVENT_TYPES[event_type]['name']}\n"
            msg += f"📊 Your claims: {claims['total']}/{limits['normal_limit'] + limits['unlock_coin_limit'] * 2}\n"
            timer = get_event_timer(event_type)
            if timer:
                msg += f"⏳ Event time left: {timer['hours']}h {timer['minutes']}m\n"
        else:
            msg += f"⏳ COOLDOWN: 24 HOURS\n"
            msg += f"📅 Next claim available: {(datetime.now() + timedelta(hours=COOLDOWN_HOURS)).strftime('%Y-%m-%d %H:%M')}\n"
        
        msg += (
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👑 Enjoy your account! 🔥\n"
            f"📌 Don't forget to stay in all groups!\n"
            f"👤 Host: @Maarkryan"
        )
        await send_custom(chat_id, msg, context)

        try:
            claimed_label = account_type.replace('_', ' ').upper()
            event_label = f" ({EVENT_TYPES[event_type]['name']})" if event_type != "default" else ""
            await edit_custom(
                query,
                f"✅ CLAIMED!{event_label}\nYou got a {claimed_label} account! Check the message above.\n\n"
                f"📊 Event claims: {get_event_claim_count(user_id, event_type)['total']}/{limits['normal_limit'] + limits['unlock_coin_limit'] * 2}"
            )
        except:
            pass
        return

    if data.startswith("addaccount_"):
        pool_key = data.replace("addaccount_", "")
        context.user_data['add_account_pool'] = pool_key
        ADD_ACCOUNT_SESSIONS[user_id] = pool_key
        pool_name = pool_key.replace('_', ' ').upper()
        msg = (
            f"📥 ADD ACCOUNTS TO: {pool_name}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Send accounts in format:\n"
            f"📧 email:password\n"
            f"📧 email:password\n\n"
            f"Or upload a .txt file.\n\n"
            f"⚠️ Each line: email:password"
        )
        keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data="admin_back")]]
        await edit_custom(query, msg, reply_markup=InlineKeyboardMarkup(keyboard))
        return

# ============================================================
# ✅ ADMIN PANEL
# ============================================================
async def admin_panel(update=None, context=None, query=None):
    if query:
        user_id = query.from_user.id
    else:
        user_id = update.effective_user.id

    if user_id != ADMIN_ID:
        if update:
            await reply_custom(update, "⛔ Admin only. ❌⚠️", context)
        return

    msg = "👑 ADMIN PANEL 🥵\n━━━━━━━━━━━━━━━━━━━━━\n\nSelect an action:"
    keyboard = [
        [InlineKeyboardButton("📥 Add Accounts", callback_data="add_accounts_menu")],
        [InlineKeyboardButton("📊 Show Inventory", callback_data="show_inventory")],
        [InlineKeyboardButton("📋 Show Claimed Accounts", callback_data="show_claimed")],
        [InlineKeyboardButton("👹 Show Makulit Users", callback_data="show_makulit")],
        [InlineKeyboardButton("🗑️ Clear Pool", callback_data="clear_pool")],
        [InlineKeyboardButton("🔓 Unban User", callback_data="unban_user")],
        [InlineKeyboardButton("🎉 Start Claim Again", callback_data="start_claimagain")],
        [InlineKeyboardButton("🎊 Start Party Time", callback_data="start_partytime")],
        [InlineKeyboardButton("⏹️ End Event", callback_data="end_event")],
        [InlineKeyboardButton("🔙 Back to Main", callback_data="start_back")],
    ]

    if query:
        await edit_custom(query, msg, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await reply_custom(update, msg, context, reply_markup=InlineKeyboardMarkup(keyboard))

# ============================================================
# ✅ BUTTON HANDLER
# ============================================================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except:
        pass
    data = query.data
    user_id = query.from_user.id

    if user_id != ADMIN_ID:
        try:
            await query.answer("⛔ Admin only!", show_alert=True)
        except:
            pass
        return

    if data == "add_accounts_menu":
        load_accounts()
        msg = "📥 SELECT ACCOUNT TYPE TO ADD:\n━━━━━━━━━━━━━━━━━━━━━\n\nChoose which pool:"
        keyboard = []
        for label, pool_key in [
            ("🚘 CPM1 Normal", "cpm1_normal"),
            ("🚘 CPM1 Unlock All Cars", "cpm1_unlock"),
            ("💰 CPM2 Normal", "cpm2_normal"),
            ("💰 CPM2 Coin Account", "cpm2_coin"),
        ]:
            count = len(ACCOUNT_POOLS.get(pool_key, []))
            display = f"{label} {'❌⚠️' if count == 0 else '☑️'} ({count})"
            keyboard.append([InlineKeyboardButton(display, callback_data=f"addaccount_{pool_key}")])
        keyboard.append([InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_back")])
        await edit_custom(query, msg, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "show_inventory":
        load_accounts()
        msg = "📊 ACCOUNT INVENTORY 🥵\n━━━━━━━━━━━━━━━━━━━━━\n\n"
        has_accounts = False

        for pool_key, label in [
            ("cpm1_normal", "CPM1 Normal"),
            ("cpm1_unlock", "CPM1 Unlock All Cars"),
            ("cpm2_normal", "CPM2 Normal"),
            ("cpm2_coin", "CPM2 Coin Account"),
        ]:
            accounts = ACCOUNT_POOLS.get(pool_key, [])
            if accounts:
                has_accounts = True
                msg += f"📌 {label} ({len(accounts)} accounts):\n"
                for i, acc in enumerate(accounts, 1):
                    msg += f"  {i}. {acc['email']}:{acc['password']}\n"
                msg += "\n"
            else:
                msg += f"❌ {label}: EMPTY\n\n"

        if not has_accounts:
            msg += "📭 No accounts available in any pool.\n"

        msg += "\n━━━━━━━━━━━━━━━━━━━━━\nUse /addaccount to add more."
        keyboard = [[InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_back")]]
        await edit_custom(query, msg, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "show_claimed":
        claimed_data = get_all_claimed()
        if not claimed_data:
            msg = "📋 CLAIMED ACCOUNTS\n━━━━━━━━━━━━━━━━━━━━━\n\n📭 No accounts have been claimed yet."
            keyboard = [[InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_back")]]
            await edit_custom(query, msg, reply_markup=InlineKeyboardMarkup(keyboard))
            return

        msg = "📋 CLAIMED ACCOUNTS\n━━━━━━━━━━━━━━━━━━━━━\n\n"
        claimed_by_user = {}
        for claim in claimed_data:
            uid = claim["user_id"]
            if uid not in claimed_by_user:
                claimed_by_user[uid] = []
            claimed_by_user[uid].append(claim)

        for uid, claims in claimed_by_user.items():
            try:
                chat = await context.bot.get_chat(uid)
                username = chat.username or "NoUsername"
            except:
                username = "Unknown"
            msg += f"👤 @{username} (ID: {uid})\n"
            for claim in claims:
                account_type = claim.get("type", "unknown").replace('_', ' ').upper()
                email = claim.get("email", "unknown")
                timestamp = claim.get("timestamp", "")
                if timestamp:
                    try:
                        dt = datetime.fromisoformat(timestamp)
                        timestamp = dt.strftime("%Y-%m-%d %H:%M")
                    except:
                        timestamp = timestamp[:16]
                msg += f"  ✅ {account_type}: {email} ({timestamp})\n"
            msg += "\n"

        if len(msg) > 3500:
            msg = msg[:3500] + "\n\n... (truncated)"

        keyboard = [[InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_back")]]
        await edit_custom(query, msg, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "show_makulit":
        makulit = get_makulit_users()
        if not makulit:
            msg = "👀 No annoying users detected. All clean! 🎉"
        else:
            msg = "👹 MAKULIT USERS 👀\n━━━━━━━━━━━━━━━━━━━━━\n\n"
            for user in makulit:
                msg += f"• User ID: {user['user_id']} – Warnings: {user['warnings']}/5\n"
            msg += "\n⚠️ These users keep leaving and rejoining groups."
        keyboard = [[InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_back")]]
        await edit_custom(query, msg, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "clear_pool":
        keyboard = [
            [InlineKeyboardButton("🚘 CPM1 Normal", callback_data="clearpool_cpm1_normal")],
            [InlineKeyboardButton("🚘 CPM1 Unlock", callback_data="clearpool_cpm1_unlock")],
            [InlineKeyboardButton("💰 CPM2 Normal", callback_data="clearpool_cpm2_normal")],
            [InlineKeyboardButton("💰 CPM2 Coin", callback_data="clearpool_cpm2_coin")],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_back")],
        ]
        await edit_custom(query, "🗑️ SELECT POOL TO CLEAR:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("clearpool_"):
        pool_key = data.replace("clearpool_", "")
        load_accounts()
        ACCOUNT_POOLS[pool_key] = []
        save_accounts()
        await edit_custom(query, f"✅ Cleared all accounts in {pool_key.replace('_', ' ').upper()}")
        await asyncio.sleep(1)
        await button_handler(update, context)
        return

    if data == "unban_user":
        context.user_data['awaiting_unban'] = True
        await edit_custom(query, "🔓 Send the USER ID to unban:\n\nExample: 6531314640")
        return

    if data == "start_claimagain":
        try:
            event_type = "claimagain"
            limits = EVENT_TYPES[event_type]
            
            # Set timer
            if not set_event_timer(event_type, limits["timer_hours"]):
                await edit_custom(query, "❌ Failed to start event. Please try again. 🥵")
                return
            
            # Broadcast
            success, failed = await broadcast_message(
                context,
                f"🎉 CLAIM AGAIN EVENT STARTED! 🎉\n\n"
                f"🔥 You can claim up to {limits['normal_limit']} accounts!\n"
                f"⚡ Max: {limits['normal_limit']} normal accounts\n"
                f"⚡ Max: {limits['unlock_coin_limit']} unlock/coin accounts\n"
                f"⏳ Event lasts for {limits['timer_hours']} hour!\n\n"
                f"💎 Click /start to claim now! 🚀\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💙 @Cpm_2test_bot",
                "🎉 CLAIM AGAIN EVENT 🎉"
            )
            
            await edit_custom(
                query,
                f"✅ Claim Again event started! 🥵\n"
                f"📤 Broadcast sent to {success} users.\n"
                f"⏳ Timer: {limits['timer_hours']} hour\n"
                f"💙 @Cpm_2test_bot"
            )
        except Exception as e:
            print(f"⚠️ Error in start_claimagain: {e}")
            await edit_custom(query, f"❌ Error starting event: {str(e)} 🥵")
        return

    if data == "start_partytime":
        try:
            event_type = "partytime"
            limits = EVENT_TYPES[event_type]
            
            if not set_event_timer(event_type, limits["timer_hours"]):
                await edit_custom(query, "❌ Failed to start event. Please try again. 🥵")
                return
            
            success, failed = await broadcast_message(
                context,
                f"🎊 PARTY TIME EVENT STARTED! 🎊\n\n"
                f"🔥 Massive giveaway time!\n"
                f"⚡ Max: {limits['normal_limit']} normal accounts\n"
                f"⚡ Max: {limits['unlock_coin_limit']} unlock/coin accounts\n"
                f"⏳ Event lasts for {limits['timer_hours']} hours!\n\n"
                f"💎 Click /start to claim now! 🚀\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💙 @Cpm_2test_bot",
                "🎊 PARTY TIME EVENT 🎊"
            )
            
            await edit_custom(
                query,
                f"✅ Party Time event started! 🥵\n"
                f"📤 Broadcast sent to {success} users.\n"
                f"⏳ Timer: {limits['timer_hours']} hours\n"
                f"💙 @Cpm_2test_bot"
            )
        except Exception as e:
            print(f"⚠️ Error in start_partytime: {e}")
            await edit_custom(query, f"❌ Error starting event: {str(e)} 🥵")
        return

    if data == "end_event":
        try:
            db_delete("giveaway/event_timer/claimagain")
            db_delete("giveaway/event_timer/partytime")
            success, failed = await broadcast_message(
                context,
                f"⏹️ EVENT ENDED ⏹️\n\n"
                f"The current event has ended.\n"
                f"🔥 Returning to default mode.\n\n"
                f"💙 Click /start to check current status.",
                "⏹️ EVENT ENDED"
            )
            await edit_custom(query, f"✅ Event ended! 🥵\n📤 Broadcast sent to {success} users.")
        except Exception as e:
            print(f"⚠️ Error in end_event: {e}")
            await edit_custom(query, f"❌ Error ending event: {str(e)} 🥵")
        return

    if data == "admin_back":
        await admin_panel(update, context, query)
        return

# ============================================================
# ✅ MESSAGE HANDLER
# ============================================================
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user_id = update.effective_user.id
    text = update.message.text.strip() if update.message.text else None
    document = update.message.document

    if user_id != ADMIN_ID:
        await reply_custom(update, "⛔ Admin only. ❌⚠️", context)
        return

    if context.user_data.get('awaiting_unban'):
        try:
            target_id = int(text)
            db_delete(f"giveaway/banned/{target_id}")
            reset_warnings(target_id)
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
            if not text:
                await reply_custom(update, "❌ Please send text or file.", context)
                return
            accounts = [line.strip() for line in text.splitlines() if ':' in line]

        if not accounts:
            await reply_custom(update, "❌ No valid accounts found. Format: email:password", context)
            return

        load_accounts()
        added = 0
        for acc in accounts:
            if ':' in acc:
                email, password = acc.split(':', 1)
                ACCOUNT_POOLS[pool_key].append({"email": email.strip(), "password": password.strip()})
                added += 1
        save_accounts()
        ADD_ACCOUNT_SESSIONS.pop(user_id, None)
        await reply_custom(
            update,
            f"✅ Added {added} accounts to {pool_key.replace('_', ' ').upper()}! 🥵\n📊 Total: {len(ACCOUNT_POOLS.get(pool_key, []))} accounts",
            context
        )
        return

# ============================================================
# ✅ LEFT_CHAT_MEMBER HANDLER
# ============================================================
async def left_chat_member_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.left_chat_member:
        return
    chat_member = update.left_chat_member
    user = chat_member.from_user
    if user.id == context.bot.id:
        return
    new_status = chat_member.new_chat_member.status
    if new_status not in ["left", "kicked"]:
        return
    chat = chat_member.chat
    chat_id = chat.id
    chat_username = chat.username or str(chat_id)
    for req in REQUIRED_CHATS:
        req_id = req["id"] if isinstance(req["id"], str) else int(req["id"])
        if req_id == chat_id or req_id == chat_username:
            warnings = add_warning(user.id)
            try:
                await context.bot.send_message(
                    chat_id=user.id,
                    text=(
                        f"⚠️ WARNING #{warnings}/5 ⚠️\n\n"
                        f"You left {req['name']}!\n"
                        f"🔄 Warnings: {warnings}/5\n"
                        f"❌ 5 warnings = PERMANENT BAN\n\n"
                        "💙 Please rejoin."
                    )
                )
            except Exception as e:
                if "blocked" in str(e).lower():
                    print(f"⚠️ User {user.id} blocked the bot - skipping warning")
                else:
                    print(f"⚠️ Error sending warning to {user.id}: {e}")
                pass
            break

# ============================================================
# ✅ ADMIN COMMANDS (FIXED – with error handling)
# ============================================================
async def claimagain_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.effective_user.id != ADMIN_ID:
            await reply_custom(update, "⛔ Admin only. ❌⚠️", context)
            return

        event_type = "claimagain"
        limits = EVENT_TYPES[event_type]
        
        if not set_event_timer(event_type, limits["timer_hours"]):
            await reply_custom(update, "❌ Failed to start event. Please try again. 🥵", context)
            return
        
        success, failed = await broadcast_message(
            context,
            f"🎉 CLAIM AGAIN EVENT STARTED! 🎉\n\n"
            f"🔥 You can claim up to {limits['normal_limit']} accounts!\n"
            f"⚡ Max: {limits['normal_limit']} normal accounts\n"
            f"⚡ Max: {limits['unlock_coin_limit']} unlock/coin accounts\n"
            f"⏳ Event lasts for {limits['timer_hours']} hour!\n\n"
            f"💎 Click /start to claim now! 🚀\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💙 @Cpm_2test_bot",
            "🎉 CLAIM AGAIN EVENT 🎉"
        )
        
        await reply_custom(
            update,
            f"✅ Claim Again event started! 🥵\n📤 Broadcast sent to {success} users.\n⏳ Timer: {limits['timer_hours']} hour\n💙 @Cpm_2test_bot",
            context
        )
    except Exception as e:
        print(f"⚠️ Error in claimagain_command: {e}")
        await reply_custom(update, f"❌ Error starting event: {str(e)} 🥵", context)

async def undermaintinance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.effective_user.id != ADMIN_ID:
            await reply_custom(update, "⛔ Admin only. ❌⚠️", context)
            return

        success, failed = await broadcast_message(
            context,
            f"🛠️ UNDER MAINTENANCE ⚡5\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"⚠️ The bot is currently under maintenance. ⚡5\n\n"
            f"🔥 We are adding new accounts and improving the system!\n"
            f"⏳ Please wait a few minutes and try again.\n\n"
            f"💎 We apologize for the inconvenience.\n"
            f"👑 Stay tuned for more updates!\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💙 @Cpm_2test_bot",
            "🛠️ MAINTENANCE ⚡5"
        )
        await reply_custom(
            update,
            f"✅ Maintenance broadcast sent! 🥵\n📤 Success: {success}\n❌ Failed: {failed}",
            context
        )
    except Exception as e:
        print(f"⚠️ Error in undermaintinance_command: {e}")
        await reply_custom(update, f"❌ Error sending maintenance: {str(e)} 🥵", context)

async def addaccount_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await admin_panel(update, context)

async def showaccounts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await admin_panel(update, context)

async def showthemakulit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await admin_panel(update, context)

async def clearpool_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await admin_panel(update, context)

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await admin_panel(update, context)

# ============================================================
# ✅ RUN BOT
# ============================================================
def run_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    request = HTTPXRequest(
        connection_pool_size=20,
        connect_timeout=60.0,
        read_timeout=60.0,
        write_timeout=60.0,
        pool_timeout=60.0
    )

    app = Application.builder().token(TOKEN).request(request).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addaccount", addaccount_command))
    app.add_handler(CommandHandler("showaccounts", showaccounts_command))
    app.add_handler(CommandHandler("showthemakulit", showthemakulit_command))
    app.add_handler(CommandHandler("clearpool", clearpool_command))
    app.add_handler(CommandHandler("unban", unban_command))
    app.add_handler(CommandHandler("claimagain", claimagain_command))
    app.add_handler(CommandHandler("undermaintinance", undermaintinance_command))

    app.add_handler(CallbackQueryHandler(details_handler, pattern="^details_"))
    app.add_handler(CallbackQueryHandler(claim_handler, pattern="^(claim_|addaccount_|check_verification|more_info|start_back|admin_back|share_confirmed)"))
    app.add_handler(CallbackQueryHandler(button_handler, pattern="^(add_accounts_menu|show_inventory|show_claimed|show_makulit|clear_pool|clearpool_|unban_user|start_claimagain|start_partytime|end_event|admin_back)"))

    app.add_handler(MessageHandler(filters.TEXT | filters.Document.ALL, message_handler))
    app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, left_chat_member_handler))

    print("=" * 50)
    print("🎁 GIVEAWAY BOT WITH VERIFICATION")
    print("📌 Bot: @Cpm_2test_bot")
    print("📌 Admin: /addaccount - opens admin panel")
    print("📌 Admin: /claimagain - start Claim Again event (FIXED)")
    print("📌 Admin: /undermaintinance - broadcast maintenance")
    print("📌 Verification: Share to 3-5 groups + join required chats")
    print("📌 Account details preview before claiming")
    print("📌 24-hour cooldown, Event system, Full inventory")
    print("📌 ALL ADMIN COMMANDS ARE ADMIN-ONLY")
    print("📌 🥵 emoji = admin-only visibility")
    print("📌 ALL CUSTOM EMOJIS ARE WORKING ✅")
    print("📌 /claimagain now has error handling - bot won't crash")
    print("=" * 50)

    loop.run_until_complete(app.initialize())
    loop.run_until_complete(app.start())
    loop.run_until_complete(app.updater.start_polling())
    loop.run_forever()

if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 10000))
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    print("✅ Bot thread started!")
    app_flask.run(host="0.0.0.0", port=PORT)
