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

REQUIRED_CHATS = [
    {"id": "@TnnrChat", "name": "TnnrChat Group"},
    {"id": "@markmwehehestore", "name": "MarkMwehehe Store"},
    {"id": -1003994249946, "name": "Tnnr Main Group"},
]

FIREBASE_API_KEY = "ph2yty6YZsJCU4oOFZi901HN4sGo7Ehtie94p7KX"
DB_URL = "https://cpm2bpt-default-rtdb.europe-west1.firebasedatabase.app"

# ============================================================
# ✅ CUSTOM EMOJI MAPPING
# ============================================================
CUSTOM_EMOJI_MAP = {
    '😂': '5406913184810409829', '😄': '5386587088873331829',
    '😍': '5323470315370585285', '😭': '5379656338802482888',
    '🤑': '5427107837568360763', '👑': '5938534225140519372',
    '🔥': '6001061381237903602', '⚡': '6061916283228655823',
    '💎': '6064293500382350516', '❌': '6064642968986323772',
    '🤨': '6134245834595765950', '👹': '6142914800880979809',
    '👀': '5834733550020072624', '💙': '6269557847248342937',
    '⚠️': '6100590432209604692', '😆': '5375135722514685501',
    '😮': '5456662929166309849', '😎': '6062259841957632787',
    '👤': '5258011929993026890', '🎮': '5258508428212445001',
    '🚘': '5366286487862124799', '✅': '5197288647275071607',
    '🎉': '6001197385672298829', '📁': '5357315181649076022',
    '📊': '5192886773948107844',
}

def get_custom_entities(text):
    entities = []
    offset = 0
    i = 0
    while i < len(text):
        ch = text[i]
        utf16_len = len(ch.encode('utf-16-le')) // 2
        if ch in CUSTOM_EMOJI_MAP:
            entities.append(MessageEntity(
                type="custom_emoji",
                offset=offset,
                length=utf16_len,
                custom_emoji_id=CUSTOM_EMOJI_MAP[ch]
            ))
        offset += utf16_len
        i += 1
    return entities

async def send_custom(chat_id, text, context, reply_markup=None):
    entities = get_custom_entities(text)
    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=reply_markup,
        parse_mode=None,
        entities=entities if entities else None
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

ACCOUNT_POOLS = {
    "cpm1_normal": [],
    "cpm2_normal": [],
    "cpm1_unlock": [],
    "cpm2_coin": [],
}

ADD_ACCOUNT_SESSIONS = {}
MEMBERSHIP_CACHE = {}

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

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
            [InlineKeyboardButton("💙 TnnrChat Group", url="https://t.me/TnnrChat")],
            [InlineKeyboardButton("💙 MarkMwehehe Store", url="https://t.me/markmwehehestore")],
            [InlineKeyboardButton("🔄 I've Joined! Check Again", callback_data="check_verification")],
        ]
        await reply_custom(update, msg, context, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    load_accounts()
    msg = (
        "🎮 WELCOME TO THE GIVEAWAY! 🎮\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🔥 You are verified! Choose your prize:\n\n"
        "⚡ One account per game per user ⚡\n"
        "💎 Choose wisely!\n\n"
        "📊 Available Accounts:\n"
    )

    for pool_key, label in [
        ("cpm1_normal", "CPM1 Normal"),
        ("cpm1_unlock", "CPM1 Unlock All Cars"),
        ("cpm2_normal", "CPM2 Normal"),
        ("cpm2_coin", "CPM2 Coin Account"),
    ]:
        count = len(ACCOUNT_POOLS.get(pool_key, []))
        msg += f"  {'❌' if count == 0 else '✅'} {label}: {count} {'(SOLD OUT)' if count == 0 else ''}\n"

    msg += "\n👇 Select your account type:"
    keyboard = []
    for label, callback, pool_key in [
        ("🚘 CPM1 Normal", "claim_cpm1_normal", "cpm1_normal"),
        ("🚘 CPM1 Unlock All Cars", "claim_cpm1_unlock", "cpm1_unlock"),
        ("💰 CPM2 Normal", "claim_cpm2_normal", "cpm2_normal"),
        ("💰 CPM2 Coin Account", "claim_cpm2_coin", "cpm2_coin"),
    ]:
        count = len(ACCOUNT_POOLS.get(pool_key, []))
        display = f"{label} {'❌⚠️' if count == 0 else '✅'}"
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
                    [InlineKeyboardButton("💙 TnnrChat Group", url="https://t.me/TnnrChat")],
                    [InlineKeyboardButton("💙 MarkMwehehe Store", url="https://t.me/markmwehehestore")],
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
            "📌 Account Types:\n"
            "• 🚘 CPM1 Normal\n"
            "• 🚘 CPM1 Unlock All Cars\n"
            "• 💰 CPM2 Normal\n"
            "• 💰 CPM2 Coin Account\n\n"
            "💎 Rules:\n"
            "• 1 account per game per user\n"
            "• Must stay in all required groups\n"
            "• ⚠️ Leaving = warnings\n"
            "• 5 warnings = PERMANENT BAN\n\n"
            "🔥 Want more? Contact @Maarkryan."
        )
        await edit_custom(query, msg)
        return

    if data.startswith("claim_"):
        account_type = data.replace("claim_", "")

        if has_claimed(user_id, account_type):
            await edit_custom(
                query,
                f"❌ ALREADY CLAIMED! ❌\n\nYou already claimed a {account_type.replace('_', ' ').upper()} account.\n🔥 One per user per game only!"
            )
            return

        load_accounts()
        pool = ACCOUNT_POOLS.get(account_type, [])
        if not pool:
            await edit_custom(
                query,
                f"😭 SORRY! 😭\n\nAll {account_type.replace('_', ' ').upper()} accounts have been claimed.\n🔥 Stay tuned for the next giveaway!\n\nContact @Maarkryan for premium accounts."
            )
            return

        account = pool.pop(0)
        save_accounts()
        add_claimed(user_id, account_type, account["email"])
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
            f"👑 Enjoy your account! 🔥\n"
            f"📌 Don't forget to stay in all groups!\n"
            f"👤 Host: @Maarkryan"
        )
        await send_custom(chat_id, msg, context)

        try:
            await edit_custom(
                query,
                f"✅ CLAIMED! You got a {account_type.replace('_', ' ').upper()} account! Check the message above."
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

async def admin_panel(update=None, context=None, query=None):
    if query:
        user_id = query.from_user.id
    else:
        user_id = update.effective_user.id

    if user_id != ADMIN_ID:
        if update:
            await reply_custom(update, "⛔ Admin only.", context)
        return

    msg = "👑 ADMIN PANEL\n━━━━━━━━━━━━━━━━━━━━━\n\nSelect an action:"
    keyboard = [
        [InlineKeyboardButton("📥 Add Accounts", callback_data="add_accounts_menu")],
        [InlineKeyboardButton("📊 Show Inventory", callback_data="show_inventory")],
        [InlineKeyboardButton("👹 Show Makulit Users", callback_data="show_makulit")],
        [InlineKeyboardButton("🗑️ Clear Pool", callback_data="clear_pool")],
        [InlineKeyboardButton("🔓 Unban User", callback_data="unban_user")],
        [InlineKeyboardButton("🔙 Back to Main", callback_data="start_back")],
    ]

    if query:
        await edit_custom(query, msg, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await reply_custom(update, msg, context, reply_markup=InlineKeyboardMarkup(keyboard))

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
            display = f"{label} {'❌⚠️' if count == 0 else '✅'} ({count})"
            keyboard.append([InlineKeyboardButton(display, callback_data=f"addaccount_{pool_key}")])
        keyboard.append([InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_back")])
        await edit_custom(query, msg, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "show_inventory":
        load_accounts()
        msg = "📊 ACCOUNT INVENTORY\n━━━━━━━━━━━━━━━━━━━━━\n\n"
        for pool_key, label in [
            ("cpm1_normal", "CPM1 Normal"),
            ("cpm1_unlock", "CPM1 Unlock All Cars"),
            ("cpm2_normal", "CPM2 Normal"),
            ("cpm2_coin", "CPM2 Coin Account"),
        ]:
            count = len(ACCOUNT_POOLS.get(pool_key, []))
            msg += f"{label}: {'❌ EMPTY' if count == 0 else f'✅ {count} accounts'}\n"
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]]
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
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]]
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

    if data == "admin_back":
        await admin_panel(update, context, query)
        return

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user_id = update.effective_user.id
    text = update.message.text.strip() if update.message.text else None
    document = update.message.document

    if user_id != ADMIN_ID:
        await reply_custom(update, "⛔ Admin only.", context)
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
            f"✅ Added {added} accounts to {pool_key.replace('_', ' ').upper()}!\n📊 Total: {len(ACCOUNT_POOLS.get(pool_key, []))} accounts",
            context
        )
        return

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
            except:
                pass
            break

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
    app.add_handler(CommandHandler("addaccount", admin_panel))
    app.add_handler(CommandHandler("showaccounts", lambda u, c: admin_panel(u, c)))
    app.add_handler(CommandHandler("showthemakulit", lambda u, c: admin_panel(u, c)))
    app.add_handler(CommandHandler("clearpool", lambda u, c: admin_panel(u, c)))
    app.add_handler(CommandHandler("unban", lambda u, c: admin_panel(u, c)))

    app.add_handler(CallbackQueryHandler(claim_handler, pattern="^(claim_|addaccount_|check_verification|more_info|start_back|admin_back|share_confirmed)"))
    app.add_handler(CallbackQueryHandler(button_handler, pattern="^(add_accounts_menu|show_inventory|show_makulit|clear_pool|clearpool_|unban_user|admin_back)"))

    app.add_handler(MessageHandler(filters.TEXT | filters.Document.ALL, message_handler))
    app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, left_chat_member_handler))

    print("=" * 50)
    print("🎁 GIVEAWAY BOT WITH VERIFICATION")
    print("📌 Bot: @Cpm_2test_bot")
    print("📌 Admin: /addaccount - opens admin panel")
    print("📌 Verification: Share to 3-5 groups + join required chats")
    print("📌 Warnings: 5 = ban")
    print("📌 OPTIMIZED: Faster responses with 20 connection pool")
    print("📌 FIXED: LEFT_CHAT_MEMBER filter (no errors)")
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
