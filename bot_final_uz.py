import logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.deep_linking import get_start_link
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import asyncio
from aiogram.bot.api import PROXY_URL # Import the proxy URL


# Sozlamalar
BOT_TOKEN = "7614808546:AAHI9Jt5GB7iVlWefwDZSMeg3iL6MTTgOSg"
CHANNEL_ID = "@memar_development"  # Kanal ID'sini o'zingiznikiga almashtiring (masalan: @mychannel yoki -1001234567890)

# Loglarni sozlash
logging.basicConfig(level=logging.INFO)

# Botni ishga tushirish
# bot = Bot(token=BOT_TOKEN)
bot = Bot(token=API_TOKEN, proxy=PROXY_URL)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Ma'lumotlar bazasini sozlash
engine = create_engine('sqlite:///bot_database.db')
Base = declarative_base()
Session = sessionmaker(bind=engine)

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True, nullable=False)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    referrer_id = Column(Integer, nullable=True)  # Taklif qilgan foydalanuvchining ID'si
    referral_count = Column(Integer, default=0)  # Taklif qilingan foydalanuvchilar soni
    is_subscribed = Column(Boolean, default=False)
    registration_date = Column(DateTime, default=datetime.now)

# Jadvallarni yaratish
Base.metadata.create_all(engine)

# Holatlar
class UserStates(StatesGroup):
    waiting_subscription = State()

def get_user(user_id):
    """Foydalanuvchini ma'lumotlar bazasidan olish"""
    session = Session()
    try:
        user = session.query(User).filter(User.user_id == user_id).first()
        return user
    finally:
        session.close()

def create_user(user_id, username, first_name, referrer_id=None):
    """Yangi foydalanuvchi yaratish"""
    session = Session()
    try:
        user = User(
            user_id=user_id,
            username=username,
            first_name=first_name,
            referrer_id=referrer_id
        )
        session.add(user)
        session.commit()
        return user
    finally:
        session.close()

def update_user_subscription(user_id, is_subscribed=True):
    """Foydalanuvchining obuna holatini yangilash"""
    session = Session()
    try:
        user = session.query(User).filter(User.user_id == user_id).first()
        if user:
            user.is_subscribed = is_subscribed
            session.commit()
    finally:
        session.close()

def increment_referral_count(user_id):
    """Referallar sonini oshirish"""
    session = Session()
    try:
        user = session.query(User).filter(User.user_id == user_id).first()
        if user:
            user.referral_count += 1
            session.commit()
            return user.referral_count
    finally:
        session.close()

async def check_subscription(user_id):
    """Foydalanuvchining kanalga obunasini tekshirish"""
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logging.error(f"Obunani tekshirishda xatolik: {e}")
        return False

def get_subscription_keyboard():
    """Obunani tekshirish uchun klaviatura"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("📺 Kanalga obuna bo'lish", url=f"https://t.me/{CHANNEL_ID.replace('@', '')}"),
        InlineKeyboardButton("✅ Men obuna bo'ldim!", callback_data="check_subscription")
    )
    return keyboard

def get_main_menu_keyboard():
    """Obunadan keyingi asosiy menyu"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("👥 Mening referal havolam", callback_data="get_referral_link"),
        InlineKeyboardButton("📊 Mening referallarim", callback_data="my_referrals")
    )
    return keyboard

@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    """/start buyrug'i uchun ishlovchi"""
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    # Deep link'dan referal kodni ajratib olish
    referrer_id = None
    if len(message.text.split()) > 1:
        try:
            referrer_id = int(message.text.split()[1])
        except ValueError:
            pass
    
    # Foydalanuvchi bazada mavjudligini tekshirish
    user = get_user(user_id)
    
    if not user:
        # Yangi foydalanuvchi yaratish
        user = create_user(user_id, username, first_name, referrer_id)
        logging.info(f"Yangi foydalanuvchi yaratildi: {user_id}, taklif qiluvchi: {referrer_id}")
    
    # Kanalga obunani tekshirish
    if await check_subscription(user_id):
        # Foydalanuvchi allaqachon obuna bo'lgan
        update_user_subscription(user_id, True)
        
        # Agar foydalanuvchi referal havola orqali kelib, obuna bo'lgan bo'lsa
        if referrer_id and not user.is_subscribed:
            await notify_referrer(referrer_id, message.from_user)
        
        await message.answer(
            f"👋 Xush kelibsiz, {first_name}!\n\n"
            "🎉 Siz bizning kanalimizga allaqachon obuna bo'lgansiz!\n"
            "Amalni tanlang:",
            reply_markup=get_main_menu_keyboard()
        )
    else:
        # Kanalga obuna bo'lishni so'rash
        await message.answer(
            f"👋 Salom, {first_name}!\n\n"
            """Bepul honadon yutib olish shartlari juda oddiy:
1. Taqdimot kanalimizga obuna boʻling

2. Sizga shaxsiy havola beriladi va shu havoliyiz orqali 50ta dostingizni kanalimizga taklif qilishingiz kerak!

3. Qanday qilib golibni aniqlashimizni, 18 iyun 20:00 boʻladigan, online taqdimotimizda bilib olasiz 💸""",
            reply_markup=get_subscription_keyboard()
        )
        
        # Obunani kutish holatini o'rnatish
        await UserStates.waiting_subscription.set()

@dp.callback_query_handler(text="check_subscription", state="*")
async def check_subscription_callback(callback_query: types.CallbackQuery, state: FSMContext):
    """Tugma orqali obunani tekshirish"""
    user_id = callback_query.from_user.id
    
    if await check_subscription(user_id):
        # Foydalanuvchi obuna bo'ldi
        update_user_subscription(user_id, True)
        
        # Foydalanuvchi haqidagi ma'lumotni bazadan olish
        user = get_user(user_id)
        
        # Agar foydalanuvchi referal havola orqali kelgan bo'lsa
        if user and user.referrer_id:
            await notify_referrer(user.referrer_id, callback_query.from_user)
        
        await callback_query.message.edit_text(
            f"🎉 Ajoyib! Xush kelibsiz!\n\n"
            "Endi siz botdan foydalanishingiz mumkin.\n"
            "Amalni tanlang:",
            reply_markup=get_main_menu_keyboard()
        )
        
        # Holatni tiklash
        await state.finish()
    else:
        await callback_query.answer(
            "❌ Siz hali kanalga obuna bo'lmadingiz! Iltimos, obuna bo'ling va qayta urinib ko'ring.",
            show_alert=True
        )

@dp.callback_query_handler(text="get_referral_link")
async def get_referral_link_callback(callback_query: types.CallbackQuery):
    """Referal havolani olish"""
    user_id = callback_query.from_user.id
    
    # Referal havola yaratish
    referral_link = await get_start_link(payload=str(user_id), encode=False)
    
    user = get_user(user_id)
    referral_count = user.referral_count if user else 0
    if referral_count >= 50:
        await callback_query.message.edit_text(
            "Tabriklaymiz! Siz konkursda qatnashiyapsiz !"
            f"🔗 Sizning referal havolangiz:\n\n"
            f"{referral_link}\n\n"
            f"👥 Sizning referallaringiz soni: {referral_count}\n\n"
            f"📤 Bu havolani do'stlaringiz bilan ulashing! Va ularga uy yutib olish imkoniyatini taqdim eting! \n"
            f"Har bir taklif qilingan do'stingiz uchun sizga bildirishnoma keladi.",
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_menu")
        ), parse_mode="Markdown"
        )
    else:
        await callback_query.message.edit_text(
            f"🔗 Sizning referal havolangiz:\n\n"
            f"{referral_link}\n\n"
            f"👥 Sizning referallaringiz soni: {referral_count}\n\n"
            f"📤 Bu havolani do'stlaringiz bilan ulashing! Va ularga uy yutib olish imkoniyatini taqdim eting! \n"
            f"Har bir taklif qilingan do'stingiz uchun sizga bildirishnoma keladi.",
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_menu")
            ), parse_mode="Markdown"
        )

@dp.callback_query_handler(text="my_referrals")
async def my_referrals_callback(callback_query: types.CallbackQuery):
    """Referallar haqida ma'lumotni ko'rsatish"""
    user_id = callback_query.from_user.id
    user = get_user(user_id)
    
    if user:
        referral_count = user.referral_count
        await callback_query.message.edit_text(
            f"📊 Sizning referal statistikangiz:\n\n"
            f"👥 Jami referallar: {referral_count}\n"
            f"📅 Ro'yxatdan o'tgan sana: {user.registration_date.strftime('%d.%m.%Y %H:%M')}\n\n"
            f"🎯 Do'stlarni taklif qilishda davom eting!",
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_menu")
            )
        )
    else:
        await callback_query.answer("Ma'lumotlarni olishda xatolik", show_alert=True)

@dp.callback_query_handler(text="back_to_menu")
async def back_to_menu_callback(callback_query: types.CallbackQuery):
    """Asosiy menyuga qaytish"""
    await callback_query.message.edit_text(
        f"👋 Xush kelibsiz, {callback_query.from_user.first_name}!\n\n"
        "Amalni tanlang:",
        reply_markup=get_main_menu_keyboard()
    )

async def notify_referrer(referrer_id, new_user):
    """Taklif qiluvchini yangi foydalanuvchi haqida xabardor qilish"""
    try:
        # Referallar hisoblagichini oshirish
        new_referral_count = increment_referral_count(referrer_id)
        
        # Bildirishnoma yuborish
        username_info = f"@{new_user.username}" if new_user.username else "username'siz"
        
        await bot.send_message(
            referrer_id,
            f"🎉 Tabriklaymiz!\n\n"
            f"👤 Sizning havolangiz orqali yangi foydalanuvchi ro'yxatdan o'tdi:\n"
            f"• Ism: {new_user.first_name}\n"
            f"• Username: {username_info}\n\n"
            f"👥 Endi sizda {new_referral_count} ta referal bor!\n\n"
            f"🚀 Havolani do'stlar bilan ulashishda davom eting!"
        )
        
        logging.info(f"Foydalanuvchi {referrer_id}ga yangi referal {new_user.id} haqida bildirishnoma yuborildi")
        
    except Exception as e:
        logging.error(f"Taklif qiluvchi {referrer_id}ga bildirishnoma yuborishda xatolik: {e}")

@dp.message_handler(content_types=types.ContentTypes.ANY, state="*")
async def handle_other_messages(message: types.Message, state: FSMContext):
    """Boshqa barcha xabarlar uchun ishlovchi"""
    user_id = message.from_user.id
    
    # Obunani tekshirish
    if not await check_subscription(user_id):
        await message.answer(
            "🔔 Avval bizning kanalimizga obuna bo'ling!",
            reply_markup=get_subscription_keyboard()
        )
        await UserStates.waiting_subscription.set()
    else:
        await message.answer(
            "👋 Navigatsiya uchun menyu tugmalaridan foydalaning:",
            reply_markup=get_main_menu_keyboard()
        )

if __name__ == '__main__':
    print("🚀 Bot ishga tushirilmoqda...")
    print("📝 Unutmang:")
    print("1. BOT_TOKEN'ni o'z botingiz tokeniga almashtiring")
    print("2. CHANNEL_ID'ni o'z kanalingiz ID'siga almashtiring")
    print("3. Botni kanal administratorlariga qo'shing")
    
    executor.start_polling(dp, skip_updates=True)

