import logging, sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

TOKEN = "8403040501:AAF4JQrD11TrZPUn5iI6BhM1MryWZ7_tRqE"
ADMIN_ID = 7300546509

bot = Bot(TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())
logging.basicConfig(level=logging.INFO)

db = sqlite3.connect("data.db", check_same_thread=False)
cur = db.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY,
    name TEXT,
    balance INTEGER DEFAULT 0,
    acc_live INTEGER DEFAULT 0,
    acc_die INTEGER DEFAULT 0,
    bank TEXT,
    stk TEXT,
    ctk TEXT,
    is_staff INTEGER DEFAULT 0,
    pending INTEGER DEFAULT 0
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS history(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount INTEGER,
    reason TEXT,
    time TEXT
)
""")

db.commit()

class MoneyState(StatesGroup):
    choose = State()
    amount = State()
    reason = State()

class AccState(StatesGroup):
    choose = State()
    amount = State()

class WithdrawState(StatesGroup):
    amount = State()

def kb_user():
    return types.ReplyKeyboardMarkup(resize_keyboard=True).add(
        "💰 Số dư","🏦 Ngân hàng",
        "📜 Lịch sử","💸 Rút tiền",
        "📝 Xin làm NV"
    )

def kb_admin():
    return types.ReplyKeyboardMarkup(resize_keyboard=True).add(
        "👥 Duyệt NV","💰 Cộng/Trừ tiền",
        "➕ Cập nhật acc","💸 Duyệt rút",
        "📊 Tổng"
    )

@dp.message_handler(commands=['start'])
async def start(msg: types.Message):
    cur.execute("INSERT OR IGNORE INTO users(id,name) VALUES(?,?)",(msg.from_user.id,msg.from_user.full_name))
    db.commit()
    if msg.from_user.id == ADMIN_ID:
        await msg.answer("ADMIN PANEL", reply_markup=kb_admin())
    else:
        await msg.answer("🤖 Cattuong Zalo Kính Chào", reply_markup=kb_user())

# USER

@dp.message_handler(text="📝 Xin làm NV")
async def req_staff(msg: types.Message):
    cur.execute("UPDATE users SET pending=1 WHERE id=?",(msg.from_user.id,))
    db.commit()
    await bot.send_message(ADMIN_ID,f"Yêu cầu làm NV:\n{msg.from_user.full_name}\nID:{msg.from_user.id}")
    await msg.answer("Đã gửi yêu cầu")

@dp.message_handler(text="💰 Số dư")
async def bal(msg: types.Message):
    cur.execute("SELECT balance,acc_live,acc_die FROM users WHERE id=?",(msg.from_user.id,))
    b,a,d = cur.fetchone()
    await msg.answer(f"💰 Số dư: {b}\n🟢 Acc sống: {a}\n☠️ Acc chết: {d}\n📦 Tổng acc: {a+d}")

@dp.message_handler(text="🏦 Ngân hàng")
async def bank(msg: types.Message):
    await msg.answer("Gửi theo format:\nBank | STK | CTK")

@dp.message_handler(lambda m: "|" in m.text and m.text.count("|")==2)
async def save_bank(msg: types.Message):
    b,s,c = [x.strip() for x in msg.text.split("|")]
    cur.execute("UPDATE users SET bank=?,stk=?,ctk=? WHERE id=?",(b,s,c,msg.from_user.id))
    db.commit()
    await msg.answer("Đã lưu ngân hàng")

@dp.message_handler(text="📜 Lịch sử")
async def history(msg: types.Message):
    cur.execute("SELECT amount,reason,time FROM history WHERE user_id=? ORDER BY id DESC LIMIT 15",(msg.from_user.id,))
    rows = cur.fetchall()
    if not rows:
        return await msg.answer("Chưa có lịch sử")
    text=""
    for a,r,t in rows:
        sign="+" if a>0 else ""
        text+=f"{sign}{a} | {r} | {t}\n"
    await msg.answer(text)

@dp.message_handler(text="💸 Rút tiền")
async def wd(msg: types.Message):
    cur.execute("SELECT bank,stk,ctk FROM users WHERE id=?",(msg.from_user.id,))
    if None in cur.fetchone():
        return await msg.answer("Chưa cập nhật ngân hàng")
    await msg.answer("Nhập số tiền muốn rút:")
    await WithdrawState.amount.set()

@dp.message_handler(state=WithdrawState.amount)
async def wd2(msg: types.Message, state:FSMContext):
    if not msg.text.isdigit(): return
    amt=int(msg.text)
    cur.execute("SELECT balance,bank,stk,ctk FROM users WHERE id=?",(msg.from_user.id,))
    b,bank,stk,ctk = cur.fetchone()
    if amt>b: return await msg.answer("Không đủ tiền")
    await bot.send_message(ADMIN_ID,
        f"💸 YÊU CẦU RÚT\n\n"
        f"👤 {msg.from_user.full_name}\nID:{msg.from_user.id}\n\n"
        f"🏦 {bank}\n💳 {stk}\n👤 {ctk}\n\n💰 {amt}",
        reply_markup=types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("✅ Duyệt",callback_data=f"okwd_{msg.from_user.id}_{amt}")
        )
    )
    await msg.answer("Đã gửi yêu cầu")
    await state.finish()

# ADMIN

@dp.message_handler(text="👥 Duyệt NV")
async def approve_list(msg: types.Message):
    cur.execute("SELECT id,name FROM users WHERE pending=1")
    rows=cur.fetchall()
    if not rows: return await msg.answer("Không có yêu cầu")
    kb=types.InlineKeyboardMarkup()
    for i,n in rows:
        kb.add(types.InlineKeyboardButton(n,callback_data=f"ap_{i}"))
    await msg.answer("Chọn NV:",reply_markup=kb)

@dp.callback_query_handler(lambda c:c.data.startswith("ap_"))
async def approve(c:types.CallbackQuery):
    uid=int(c.data.split("_")[1])
    cur.execute("UPDATE users SET is_staff=1,pending=0 WHERE id=?",(uid,))
    db.commit()
    await bot.send_message(uid,"Bạn đã được duyệt làm NV")
    await c.message.edit_text("Đã duyệt")

# CỘNG / TRỪ TIỀN

@dp.message_handler(text="💰 Cộng/Trừ tiền")
async def money_list(msg: types.Message):
    cur.execute("SELECT id,name FROM users WHERE is_staff=1")
    rows=cur.fetchall()
    kb=types.InlineKeyboardMarkup()
    for i,n in rows:
        kb.add(types.InlineKeyboardButton(n,callback_data=f"money_{i}"))
    await msg.answer("Chọn NV:",reply_markup=kb)

@dp.callback_query_handler(lambda c:c.data.startswith("money_"))
async def money_type(c:types.CallbackQuery, state:FSMContext):
    await state.update_data(uid=int(c.data.split("_")[1]))
    kb=types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton("➕ Cộng",callback_data="plus"),
        types.InlineKeyboardButton("➖ Trừ",callback_data="minus")
    )
    await c.message.edit_text("Chọn:",reply_markup=kb)
    await MoneyState.choose.set()

@dp.callback_query_handler(lambda c:c.data in ["plus","minus"],state=MoneyState.choose)
async def money_amt(c:types.CallbackQuery,state:FSMContext):
    await state.update_data(mode=c.data)
    await c.message.answer("Nhập số tiền:")
    await MoneyState.amount.set()

@dp.message_handler(state=MoneyState.amount)
async def money_reason(msg:types.Message,state:FSMContext):
    if not msg.text.isdigit(): return
    await state.update_data(amount=int(msg.text))
    await msg.answer("Nhập lý do:")
    await MoneyState.reason.set()

@dp.message_handler(state=MoneyState.reason)
async def money_done(msg:types.Message,state:FSMContext):
    data=await state.get_data()
    uid=data["uid"]; amt=data["amount"]
    if data["mode"]=="minus": amt=-amt
    cur.execute("UPDATE users SET balance=balance+? WHERE id=?",(amt,uid))
    cur.execute("INSERT INTO history(user_id,amount,reason,time) VALUES(?,?,?,?)",
        (uid,amt,f"Admin {'cộng' if amt>0 else 'trừ'} | {msg.text}",datetime.now().strftime("%d/%m %H:%M")))
    db.commit()
    await bot.send_message(uid,f"💰 Số dư thay đổi: {amt}")
    await msg.answer("Đã cập nhật")
    await state.finish()

# CẬP NHẬT ACC

@dp.message_handler(text="➕ Cập nhật acc")
async def acc_list(msg: types.Message):
    cur.execute("SELECT id,name FROM users WHERE is_staff=1")
    rows=cur.fetchall()
    kb=types.InlineKeyboardMarkup()
    for i,n in rows:
        kb.add(types.InlineKeyboardButton(n,callback_data=f"acc_{i}"))
    await msg.answer("Chọn NV:",reply_markup=kb)

@dp.callback_query_handler(lambda c:c.data.startswith("acc_"))
async def acc_type(c:types.CallbackQuery,state:FSMContext):
    await state.update_data(uid=int(c.data.split("_")[1]))
    kb=types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton("➕ Acc sống",callback_data="live"),
        types.InlineKeyboardButton("☠️ Acc chết",callback_data="die")
    )
    await c.message.edit_text("Chọn:",reply_markup=kb)
    await AccState.choose.set()

@dp.callback_query_handler(lambda c:c.data in ["live","die"],state=AccState.choose)
async def acc_amt(c:types.CallbackQuery,state:FSMContext):
    await state.update_data(mode=c.data)
    await c.message.answer("Nhập số lượng:")
    await AccState.amount.set()

@dp.message_handler(state=AccState.amount)
async def acc_done(msg:types.Message,state:FSMContext):
    if not msg.text.isdigit(): return
    n=int(msg.text)
    data=await state.get_data()
    uid=data["uid"]
    if data["mode"]=="live":
        cur.execute("UPDATE users SET acc_live=acc_live+? WHERE id=?",(n,uid))
        text=f"➕ Acc sống +{n}"
    else:
        cur.execute("UPDATE users SET acc_die=acc_die+?, acc_live=acc_live-? WHERE id=?",(n,n,uid))
        text=f"☠️ Acc chết +{n}"
    db.commit()
    await bot.send_message(uid,f"📊 Cập nhật acc:\n{text}")
    await msg.answer("Đã cập nhật acc")
    await state.finish()

# DUYỆT RÚT

@dp.callback_query_handler(lambda c:c.data.startswith("okwd_"))
async def okwd(c:types.CallbackQuery):
    _,uid,amt=c.data.split("_")
    uid=int(uid); amt=int(amt)
    cur.execute("UPDATE users SET balance=balance-? WHERE id=?",(amt,uid))
    cur.execute("INSERT INTO history(user_id,amount,reason,time) VALUES(?,?,?,?)",
        (uid,-amt,"Rút tiền",datetime.now().strftime("%d/%m %H:%M")))
    db.commit()
    await bot.send_message(uid,f"Rút {amt} thành công")
    await c.message.edit_text("Đã duyệt")

# DASHBOARD TỔNG

@dp.message_handler(text="📊 Tổng")
async def total_admin(msg: types.Message):
    cur.execute("SELECT COUNT(*) FROM users WHERE is_staff=1")
    staff=cur.fetchone()[0]
    cur.execute("SELECT SUM(balance),SUM(acc_live),SUM(acc_die) FROM users")
    bal,live,die=cur.fetchone()
    await msg.answer(
        f"📊 TỔNG HỆ THỐNG\n\n"
        f"👥 Nhân viên: {staff}\n"
        f"💰 Tổng tiền: {bal or 0}\n"
        f"🟢 Acc sống: {live or 0}\n"
        f"☠️ Acc chết: {die or 0}"
    )

executor.start_polling(dp)

