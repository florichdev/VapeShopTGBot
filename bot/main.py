import os
import logging
import urllib.parse
import asyncio
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters, ConversationHandler
from database import init_db, get_session, User, Product, CartItem, Order, OrderItem, Category
from keyboards import main_menu_keyboard, categories_keyboard, products_keyboard, product_keyboard, profile_keyboard, orders_keyboard, cart_keyboard, search_keyboard, cart_items_keyboard, after_order_keyboard, balance_keyboard
from datetime import datetime
from payments import get_payment_qr_code, check_payment_status, get_payment_amount, cleanup_old_sessions

try:
    from config import BOT_TOKEN, ADMIN_IDS
except ImportError:
    print("⚠️ Файл config.py не найден! Скопируйте config.example.py в config.py и заполните данные")
    BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
    ADMIN_IDS = []
SEARCH_QUERY = 1
PAYMENT_AMOUNT = 2 

PAYMENT_CONFIG = {
    'min_amount': 1,
    'max_amount': 189000,
    'timeout_minutes': 15,
    'check_interval': 30,
    'max_checks': 30
}

PHOTO_PATH = os.path.join('bot', 'img', 'ava.jpg')

engine = init_db()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
user_states = {}
payment_sessions = {}

async def check_user_banned(user_id: int) -> bool:
    db = get_session(engine)
    try:
        user = db.query(User).filter(User.user_id == user_id).first()
        return user.is_banned if user else False
    finally:
        db.close()

async def handle_banned_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        user_id = update.effective_user.id
    elif update.callback_query:
        user_id = update.callback_query.from_user.id
    else:
        return False
        
    if await check_user_banned(user_id):
        if update.message:
            await update.message.reply_text("❌ Ваш аккаунт заблокирован. Обратитесь к администратору.")
        elif update.callback_query:
            await update.callback_query.message.reply_text("❌ Ваш аккаунт заблокирован. Обратитесь к администратору.")
        return True
    return False

def translate_status(status):
    status_translations = {
        'pending': '⏳ Ожидает обработки',
        'processing': '🔧 Обрабатывается',
        'shipped': '🚚 Отправлен',
        'delivered': '✅ Доставлен',
        'cancelled': '❌ Отменен'
    }
    return status_translations.get(status, status)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if await handle_banned_user(update, context):
        return
    
    db = get_session(engine)
    try:
        existing_user = db.query(User).filter(User.user_id == user.id).first()
        if not existing_user:
            new_user = User(user_id=user.id, username=user.username, first_name=user.first_name, last_name=user.last_name)
            db.add(new_user)
            db.commit()
            await update.message.reply_text("👋 Добро пожаловать! Вы были зарегистрированы в системе.")
        
        with open(PHOTO_PATH, 'rb') as photo:
            await update.message.reply_photo(
                photo=photo,
                caption="🚬 Добро пожаловать в магазин электронных сигарет - Vape Shop\n\nВыберите нужный раздел:",
                reply_markup=main_menu_keyboard()
            )
    except Exception as e:
        logger.error(f"Error in start: {e}")
        await update.message.reply_text("🚬 Добро пожаловать в магазин электронных сигарет - Vape Shop\n\nВыберите нужный раздел:", reply_markup=main_menu_keyboard())
    finally:
        db.close()

async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await handle_banned_user(update, context):
        return
    with open(PHOTO_PATH, 'rb') as photo:
        await update.message.reply_photo(
            photo=photo,
            caption="🚬 Главное меню:\n\nВыберите нужный раздел:",
            reply_markup=main_menu_keyboard()
        )

async def show_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await handle_banned_user(update, context):
        return
    user_id = update.effective_user.id
    user_states[user_id] = {'category': None, 'page': 0, 'search_query': None}
    
    db = get_session(engine)
    try:
        category_counts = {}
        for category in Category:
            count = db.query(Product).filter(Product.category == category, Product.is_active == True).count()
            category_counts[category] = count
        
        message_text = "🏪 Магазин - выберите категорию:\n\n"
        for category in Category:
            count = category_counts[category]
            message_text += f"• {category.value} ({count} товаров)\n"
        
        await update.message.reply_text(message_text, reply_markup=categories_keyboard())
    except Exception as e:
        logger.error(f"Error in show_shop: {e}")
        await update.message.reply_text("🏪 Магазин - выберите категорию:", reply_markup=categories_keyboard())
    finally:
        db.close()

async def show_shop_from_callback(query):
    db = get_session(engine)
    try:
        category_counts = {}
        for category in Category:
            count = db.query(Product).filter(Product.category == category, Product.is_active == True).count()
            category_counts[category] = count
        
        message_text = "🏪 Магазин - выберите категорию:\n\n"
        for category in Category:
            count = category_counts[category]
            message_text += f"• {category.value} ({count} товаров)\n"
        
        await query.message.reply_text(message_text, reply_markup=categories_keyboard())
    except Exception as e:
        logger.error(f"Error in show_shop_from_callback: {e}")
        await query.message.reply_text("🏪 Магазин - выберите категорию:", reply_markup=categories_keyboard())
    finally:
        db.close()

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await handle_banned_user(update, context):
        return
    db = get_session(engine)
    try:
        user = db.query(User).filter(User.user_id == update.effective_user.id).first()
        text = (
            f"👤 *Ваш профиль*\n\n"
            f"💳 *Баланс:* {user.balance} руб.\n"
            f"📦 *Заказов:* {user.orders_count}\n"
            f"📅 *Регистрация:* {user.created_at.strftime('%d.%m.%Y')}\n\n"
            f"⚠️ *Временно автоматическое пополнение баланса не работает*\n"
            f"Для пополнения используйте кнопку ниже"
        )
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=profile_keyboard())
    except Exception as e:
        logger.error(f"Error in show_profile: {e}")
    finally:
        db.close()

async def show_profile_from_callback(query):
    db = get_session(engine)
    try:
        user = db.query(User).filter(User.user_id == query.from_user.id).first()
        
        active_payments = 0
        for payment_id, session in payment_sessions.items():
            if session['user_id'] == query.from_user.id and session['status'] == 'pending':
                active_payments += 1
        
        text = (
            f"👤 *Ваш профиль*\n\n"
            f"💳 *Баланс:* {user.balance} руб.\n"
            f"📦 *Заказов:* {user.orders_count}\n"
            f"📅 *Регистрация:* {user.created_at.strftime('%d.%m.%Y')}\n"
        )
        
        if active_payments > 0:
            text += f"🔄 *Активные платежи:* {active_payments}\n\n"
        else:
            text += "\n"
            
        text += "💵 *Пополнение баланса:*\n• Минимальная сумма: 100 руб.\n• Автоматическое зачисление\n• Время оплаты: 15 минут"
        
        await query.message.reply_text(text, parse_mode='Markdown', reply_markup=profile_keyboard())
    except Exception as e:
        logger.error(f"Error in show_profile: {e}")
    finally:
        db.close()

async def show_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await handle_banned_user(update, context):
        return
    db = get_session(engine)
    try:
        user = db.query(User).filter(User.user_id == update.effective_user.id).first()
        orders = db.query(Order).filter(Order.user_id == user.id).order_by(Order.created_at.desc()).all()
        if not orders:
            await update.message.reply_text("📦 У вас пока нет заказов.", reply_markup=orders_keyboard())
            return
        text = "📦 Ваши заказы:\n\n"
        for order in orders:
            text += f"🔖 #{order.order_number} - {order.total_amount} руб. - {translate_status(order.status)}\n"
            text += f"📅 {order.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            if order.tracking_number:
                text += f"📦 Трек-номер: {order.tracking_number}\n"
            else:
                text += "📦 Трек-номер: ожидается\n"
            text += "\n"
        await update.message.reply_text(text, reply_markup=orders_keyboard())
    except Exception as e:
        logger.error(f"Error in show_orders: {e}")
    finally:
        db.close()

async def show_orders_from_callback(query):
    db = get_session(engine)
    try:
        user = db.query(User).filter(User.user_id == query.from_user.id).first()
        orders = db.query(Order).filter(Order.user_id == user.id).order_by(Order.created_at.desc()).all()
        if not orders:
            await query.message.reply_text("📦 У вас пока нет заказов.", reply_markup=orders_keyboard())
            return
        text = "📦 Ваши заказы:\n\n"
        for order in orders:
            text += f"🔖 #{order.order_number} - {order.total_amount} руб. - {translate_status(order.status)}\n"
            text += f"📅 {order.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            if order.tracking_number:
                text += f"📦 Трек-номер: {order.tracking_number}\n"
            else:
                text += "📦 Трек-номер: ожидается\n"
            text += "\n"
        await query.message.reply_text(text, reply_markup=orders_keyboard())
    except Exception as e:
        logger.error(f"Error in show_orders: {e}")
    finally:
        db.close()

async def show_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await handle_banned_user(update, context):
        return
    db = get_session(engine)
    try:
        user = db.query(User).filter(User.user_id == update.effective_user.id).first()
        cart_items = db.query(CartItem).filter(CartItem.user_id == user.id).all()
        if not cart_items:
            await update.message.reply_text("🛒 Ваша корзина пуста!", reply_markup=cart_keyboard())
            return
        total = 0
        text = "🛒 Ваша корзина:\n\n"
        for item in cart_items:
            text += f"🚬 {item.product.name} - {item.quantity} шт. x {item.product.price} руб.\n"
            total += item.quantity * item.product.price
        text += f"\n💵 Итого: {total} руб."
        await update.message.reply_text(text, reply_markup=cart_keyboard())
    except Exception as e:
        logger.error(f"Error in show_cart: {e}")
    finally:
        db.close()

async def show_cart_from_callback(query):
    db = get_session(engine)
    try:
        user = db.query(User).filter(User.user_id == query.from_user.id).first()
        cart_items = db.query(CartItem).filter(CartItem.user_id == user.id).all()
        
        if not cart_items:
            await query.message.reply_text("🛒 Ваша корзина пуста!", reply_markup=cart_keyboard())
            return
        
        total = 0
        text = "🛒 Ваша корзина:\n\n"
        for item in cart_items:
            item_total = item.quantity * item.product.price
            text += f"🚬 {item.product.name} - {item.quantity} шт. x {item.product.price} руб. = {item_total} руб.\n"
            total += item_total
        
        text += f"\n💵 Итого: {total} руб."
        
        reply_markup = cart_items_keyboard(cart_items)
        await query.message.reply_text(text, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error in show_cart: {e}")
    finally:
        db.close()

async def remove_from_cart(query, cart_item_id):
    db = get_session(engine)
    try:
        cart_item = db.query(CartItem).filter(CartItem.id == cart_item_id).first()
        
        if cart_item:
            product_name = cart_item.product.name
            db.delete(cart_item)
            db.commit()
            
            await query.answer(f"❌ {product_name} удален из корзины!")
            
            user = db.query(User).filter(User.user_id == query.from_user.id).first()
            cart_items = db.query(CartItem).filter(CartItem.user_id == user.id).all()
            
            if not cart_items:
                await query.message.reply_text("🛒 Ваша корзина пуста!", reply_markup=cart_keyboard())
                return
            
            total = 0
            text = "🛒 Ваша корзина:\n\n"
            for item in cart_items:
                item_total = item.quantity * item.product.price
                text += f"🚬 {item.product.name} - {item.quantity} шт. x {item.product.price} руб. = {item_total} руб.\n"
                total += item_total
            
            text += f"\n💵 Итого: {total} руб."
            
            reply_markup = cart_items_keyboard(cart_items)
            await query.message.reply_text(text, reply_markup=reply_markup)
        else:
            await query.answer("Товар не найден в корзине!")
    except Exception as e:
        logger.error(f"Error removing from cart: {e}")
        await query.answer("Ошибка при удалении товара!")
    finally:
        db.close()

async def start_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("🔍 Введите название товара для поиска:", reply_markup=search_keyboard())
    return SEARCH_QUERY

async def handle_search_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    search_text = update.message.text.strip()
    user_id = update.effective_user.id
    db = get_session(engine)
    try:
        products = db.query(Product).filter(Product.name.ilike(f"%{search_text}%"), Product.is_active == True).all()
        if not products:
            await update.message.reply_text(
                f"🔍 По запросу '{search_text}' ничего не найдено.\n\n"
                f"Попробуйте другой поисковый запрос или выберите категорию:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Новый поиск", callback_data="search")],
                    [InlineKeyboardButton("🏪 К категориям", callback_data="shop")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
                ])
            )
            return ConversationHandler.END
        user_states[user_id] = {'search_results': products, 'search_query': search_text, 'page': 0}
        await show_search_results(update, context, user_id, 0)
    except Exception as e:
        logger.error(f"Error in search: {e}")
        await update.message.reply_text("Произошла ошибка при поиске.")
    finally:
        db.close()
    return ConversationHandler.END

async def show_search_results(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, page: int = 0):
    state = user_states.get(user_id, {})
    products = state.get('search_results', [])
    search_query = state.get('search_query', '')
    if not products:
        if update.callback_query:
            await update.callback_query.message.reply_text(
                f"🔍 По запросу '{search_query}' ничего не найдено.\n\n"
                f"Попробуйте другой поисковый запрос:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Новый поиск", callback_data="search")],
                    [InlineKeyboardButton("🏪 К категориям", callback_data="shop")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
                ])
            )
        else:
            await update.message.reply_text(
                f"🔍 По запросу '{search_query}' ничего не найдено.\n\n"
                f"Попробуйте другой поисковый запрос:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Новый поиск", callback_data="search")],
                    [InlineKeyboardButton("🏪 К категориям", callback_data="shop")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
                ])
            )
        return
    total_pages = (len(products) + 3) // 4
    current_page = min(page, total_pages - 1) if total_pages > 0 else 0
    start_idx = current_page * 4
    end_idx = start_idx + 4
    page_products = products[start_idx:end_idx]
    text = f"🔍 Результаты поиска по '{search_query}':\n"
    text += f"📄 Страница {current_page + 1} из {total_pages}\n\n"
    for product in page_products:
        text += f"🚬 {product.name} - {product.price} руб.\n"
        text += f"   {product.description[:50]}...\n\n"
    keyboard = []
    for i in range(0, len(page_products), 2):
        row = []
        for j in range(2):
            if i + j < len(page_products):
                product = page_products[i + j]
                row.append(InlineKeyboardButton(product.name, callback_data=f"product_{product.id}"))
        if row:
            keyboard.append(row)
    nav_buttons = []
    if current_page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️", callback_data=f"search_page_{current_page - 1}"))
    else:
        nav_buttons.append(InlineKeyboardButton("⏹️", callback_data="no_action"))
    nav_buttons.append(InlineKeyboardButton("🏠", callback_data="main_menu"))
    if current_page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("➡️", callback_data=f"search_page_{current_page + 1}"))
    else:
        nav_buttons.append(InlineKeyboardButton("⏹️", callback_data="no_action"))
    keyboard.append(nav_buttons)
    keyboard.append([InlineKeyboardButton("↩️ Новый поиск", callback_data="search")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        await update.callback_query.message.reply_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)

async def cancel_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Поиск отменен.", reply_markup=categories_keyboard())
    return ConversationHandler.END

async def show_category_products(update: Update, context: ContextTypes.DEFAULT_TYPE, category: Category, page: int = 0):
    query = update.callback_query
    user_id = query.from_user.id
    db = get_session(engine)
    try:
        products = db.query(Product).filter(Product.category == category, Product.is_active == True).all()
        total_pages = (len(products) + 3) // 4
        current_page = min(page, total_pages - 1) if total_pages > 0 else 0
        
        if not products:
            await query.edit_message_text(
                f"📦 Категория: {category.value}\n\n"
                f"😔 В данной категории пока нет доступных товаров.\n\n"
                f"Попробуйте другую категорию или проверьте позже.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("↩️ К категориям", callback_data="shop")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
                ])
            )
            return
        
        start_idx = current_page * 4
        end_idx = start_idx + 4
        page_products = products[start_idx:end_idx]
        user_states[user_id] = {'category': category, 'page': current_page, 'search_query': None}
        
        await query.edit_message_text(
            f"📦 Категория: {category.value}\n📄 Страница {current_page + 1} из {total_pages}",
            reply_markup=products_keyboard(page_products, current_page, total_pages, category)
        )
        
    except Exception as e:
        logger.error(f"Error in show_category_products: {e}")
        await query.answer("Произошла ошибка!")
    finally:
        db.close()

async def show_product_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id: int):
    query = update.callback_query
    db = get_session(engine)
    try:
        product = db.query(Product).filter(Product.id == product_id, Product.is_active == True).first()
        if not product:
            await query.answer("Товар не найден или недоступен!")
            return
        
        message_text = (
            f"🚬 {product.name}\n\n"
            f"{product.description}\n\n"
            f"💵 Цена: {product.price} руб.\n"
            f"📂 Категория: {product.category.value}"
        )
        
        if product.photo_gif_id:
            try:
                if product.photo_gif_id.endswith('.gif'):
                    await query.message.reply_animation(
                        animation=product.photo_gif_id,
                        caption=message_text,
                        reply_markup=product_keyboard(product.id)
                    )
                else:
                    await query.message.reply_photo(
                        photo=product.photo_gif_id,
                        caption=message_text,
                        reply_markup=product_keyboard(product.id)
                    )
            except Exception as e:
                logger.error(f"Error sending media: {e}")
                await query.message.reply_text(
                    message_text,
                    reply_markup=product_keyboard(product.id)
                )
        else:
            await query.message.reply_text(
                message_text,
                reply_markup=product_keyboard(product.id)
            )
        
        await query.answer()
        
    except Exception as e:
        logger.error(f"Error in show_product_detail: {e}")
    finally:
        db.close()

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if await handle_banned_user(update, context):
        return
    
    data = query.data
    
    try:
        if data == "shop":
            await show_shop_from_callback(query)
        elif data == "profile":
            await show_profile_from_callback(query)
        elif data == "orders":
            await show_orders_from_callback(query)
        elif data == "cart":
            await show_cart_from_callback(query)
        elif data == "main_menu":
            await go_to_main_menu(query)
        elif data == "search":
            await start_search(update, context)
        elif data == "add_balance":
            await query.answer("Используйте кнопку ниже для ввода суммы")
        elif data.startswith("check_payment_"):
            await handle_check_payment(query) 
        elif data == "no_action":
            await query.answer("Достигнут предел страниц!")
        elif data == "back_to_products":
            await query.message.reply_text("🏪 Магазин - выберите категорию:", reply_markup=categories_keyboard())
        elif data == "confirm_order":
            await confirm_order(query)
        elif data.startswith("category_"):
            category_name = data.split("_", 1)[1]
            try:
                category = Category[category_name]
                await show_category_products(update, context, category)
            except KeyError:
                await query.answer("Категория не найдена!")
        elif data.startswith("product_"):
            product_id = int(data.split("_")[1])
            await show_product_detail(update, context, product_id)
        elif data.startswith("page_"):
            parts = data.split("_")
            try:
                category = Category[parts[1]]
                page = int(parts[2])
                await show_category_products(update, context, category, page)
            except (KeyError, ValueError):
                await query.answer("Ошибка навигации!")
        elif data.startswith("search_page_"):
            page = int(data.split("_")[2])
            user_id = query.from_user.id
            await show_search_results(update, context, user_id, page)
        elif data.startswith("add_cart_"):
            product_id = int(data.split("_")[2])
            await add_to_cart(query, product_id)
        elif data.startswith("buy_now_"):
            product_id = int(data.split("_")[2])
            await buy_now(query, product_id)
        elif data.startswith("remove_cart_"):
            cart_item_id = int(data.split("_")[2])
            await remove_from_cart(query, cart_item_id)
            
    except Exception as e:
        logger.error(f"Error in handle_callback: {e}")
        await query.answer("Произошла ошибка!")

async def go_to_main_menu(query):
    with open(PHOTO_PATH, 'rb') as photo:
        await query.message.reply_photo(
            photo=photo,
            caption="🚬 Добро пожаловать в магазин электронных сигарет!\n\nВыберите нужный раздел:",
            reply_markup=main_menu_keyboard()
        )

async def add_to_cart(query, product_id):
    db = get_session(engine)
    try:
        user = db.query(User).filter(User.user_id == query.from_user.id).first()
        product = db.query(Product).filter(Product.id == product_id).first()
        
        if not product:
            await query.answer("Товар не найден!")
            return
        
        cart_item = db.query(CartItem).filter(
            CartItem.user_id == user.id,
            CartItem.product_id == product_id
        ).first()
        
        if cart_item:
            cart_item.quantity += 1
            new_quantity = cart_item.quantity
        else:
            cart_item = CartItem(user_id=user.id, product_id=product_id, quantity=1)
            db.add(cart_item)
            new_quantity = 1
        
        db.commit()

        await query.message.reply_text(
            f"✅ {product.name} добавлен в корзину!\n"
            f"📦 Количество: {new_quantity} шт.\n"
            f"💵 Сумма: {new_quantity * product.price} руб."
        )
        
        await query.answer(f"✅ {product.name} добавлен в корзину!")
        
    except Exception as e:
        logger.error(f"Error in add_to_cart: {e}")
        await query.answer("Ошибка при добавлении в корзину!")
    finally:
        db.close()

async def buy_now(query, product_id):
    db = get_session(engine)
    try:
        user = db.query(User).filter(User.user_id == query.from_user.id).first()
        product = db.query(Product).filter(Product.id == product_id).first()
        
        if not product:
            await query.answer("Товар не найден!")
            return
        
        if product.price < 1500:
            await query.answer("❌ Минимальная сумма заказа - 1500 рублей!")
            return
        
        if user.balance < product.price:
            await query.message.reply_text(
                f"❌ Недостаточно средств на балансе!\n"
                f"💵 Нужно: {product.price} руб.\n"
                f"💳 На балансе: {user.balance} руб.\n\n"
                f"Пополните баланс в разделе 👤 Профиль",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💵 Пополнить баланс", callback_data="add_balance")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
                ])
            )
            await query.answer("❌ Недостаточно средств на балансе!")
            return
        
        order = Order(user_id=user.id, total_amount=product.price, status='pending')
        db.add(order)
        db.commit()
        
        order_item = OrderItem(order_id=order.id, product_id=product_id, quantity=1, price=product.price)
        db.add(order_item)
        
        user.balance -= product.price
        user.orders_count += 1
        db.commit()
        
        order_info = (
            f"ФИО: \n"
            f"Заказ #{order.order_number}\n"
            f"Сумма: {product.price} руб.\n"
            f"Товар: {product.name} x1 = {product.price} руб.\n"
            f"Доставка: 500р\n"
            f"Адрес почты России: \n"
            f"Номер телефона: "
        )
        
        telegram_url = f"https://t.me/example?text={urllib.parse.quote(order_info)}"
        
        await query.answer("✅ Заказ создан!")
        
        await query.message.reply_text(
            f"✅ Заказ #{order.order_number} создан!\n"
            f"💵 Сумма: {product.price} руб.\n\n"
            f"📦 Для указания адреса доставки и номера телефона нажмите кнопку ниже:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📦 Указать адрес и телефон", url=telegram_url)],
                [InlineKeyboardButton("📋 Мои заказы", callback_data="orders")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
            ])
        )
        
    except Exception as e:
        logger.error(f"Error in buy_now: {e}")
        await query.answer("Произошла ошибка!")
    finally:
        db.close()

async def handle_add_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки пополнения баланса"""
    query = update.callback_query
    await query.answer()
    
    try:
        await query.message.reply_text(
            "💵 *Пополнение баланса*\n\n"
            "Введите сумму для пополнения (минимум 100 рублей):",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад в профиль", callback_data="profile")]
            ])
        )
        return PAYMENT_AMOUNT
    except Exception as e:
        logger.error(f"Error in handle_add_balance: {e}")
        await query.message.reply_text("❌ Произошла ошибка!")
        return ConversationHandler.END
    
async def handle_payment_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ввода суммы для пополнения"""
    try:
        amount_text = update.message.text.strip()
        
        try:
            amount = int(amount_text)
        except ValueError:
            await update.message.reply_text(
                "❌ Пожалуйста, введите корректную сумму (только цифры):",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад в профиль", callback_data="profile")]
                ])
            )
            return PAYMENT_AMOUNT
        
        if amount < 1:
            await update.message.reply_text(
                "❌ Минимальная сумма пополнения - 1 рубль:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад в профиль", callback_data="profile")]
                ])
            )
            return PAYMENT_AMOUNT
        
        if amount > 189000:
            await update.message.reply_text(
                "❌ Максимальная сумма пополнения - 189,000 рублей:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад в профиль", callback_data="profile")]
                ])
            )
            return PAYMENT_AMOUNT
        
        user_id = update.effective_user.id
        await update.message.reply_text("🔄 Создаем платеж...")
        
        payment_result = await asyncio.get_event_loop().run_in_executor(
            None, get_payment_qr_code, amount
        )
        
        payment_id, payment_link, qr_link = payment_result
        
        if not qr_link:
            await update.message.reply_text(
                "❌ Ошибка при создании платежа. Попробуйте позже.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад в профиль", callback_data="profile")]
                ])
            )
            return ConversationHandler.END
        
        payment_sessions[payment_id] = {
            'user_id': user_id,
            'amount': amount,
            'created_at': time.time(),
            'status': 'pending'
        }
        
        message_text = (
            f"💵 *Платеж создан!*\n\n"
            f"💰 Сумма: {amount} руб.\n"
            f"🔗 ID платежа: `{payment_id}`\n\n"
            f"📱 *Инструкция по оплате:*\n"
            f"1. Отсканируйте QR-код ниже\n"
            f"2. Или перейдите по ссылке: {qr_link}\n"
            f"3. Оплатите счет в течение 15 минут\n"
            f"4. Баланс пополнится автоматически\n\n"
            f"⏰ Время на оплату: 15 минут"
        )
        
        await update.message.reply_text(
            message_text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 Открыть ссылку оплаты", url=qr_link)],
                [InlineKeyboardButton("🔄 Проверить статус", callback_data=f"check_payment_{payment_id}")],
                [InlineKeyboardButton("🔙 Назад в профиль", callback_data="profile")]
            ])
        )
        
        asyncio.create_task(check_payment_status_loop(payment_id, user_id, amount))
        
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error in handle_payment_amount: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при создании платежа.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад в профиль", callback_data="profile")]
            ])
        )
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error in handle_payment_amount: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при создании платежа.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад в профиль", callback_data="profile")]
            ])
        )
        return ConversationHandler.END
    
async def check_payment_status_loop(payment_id, user_id, expected_amount):
    """Фоновая задача для проверки статуса платежа"""
    try:
        max_checks = 30
        checks_done = 0
        
        for i in range(max_checks):
            await asyncio.sleep(30) 
            checks_done += 1
            
            status = await asyncio.get_event_loop().run_in_executor(
                None, check_payment_status, payment_id
            )
            
            if status == "completed":
                actual_amount = await asyncio.get_event_loop().run_in_executor(
                    None, get_payment_amount, payment_id
                )
                
                amount_to_add = actual_amount if actual_amount else expected_amount
                
                await process_successful_payment(payment_id, user_id, amount_to_add)
                break
                
            elif status == "failed":
                await process_failed_payment(payment_id, user_id)
                break
                
            elif status == "error":
                print(f"Ошибка при проверке платежа {payment_id}")
                
            if payment_id in payment_sessions:
                payment_sessions[payment_id]['status'] = status
                payment_sessions[payment_id]['last_check'] = time.time()
                payment_sessions[payment_id]['checks_done'] = checks_done
            
        else:
            await process_expired_payment(payment_id, user_id)
            
    except Exception as e:
        logger.error(f"Error in check_payment_status_loop for {payment_id}: {e}")

async def process_expired_payment(payment_id, user_id):
    """Обработка истекшего платежа"""
    try:
        from telegram import Bot
        bot = Bot(token=BOT_TOKEN)
        
        expire_text = (
            f"⏰ *Время оплаты истекло!*\n\n"
            f"🔗 ID платежа: `{payment_id}`\n\n"
            f"Платеж был активен 15 минут, но не был оплачен.\n"
            f"Создайте новый платеж для пополнения баланса."
        )
        
        await bot.send_message(
            chat_id=user_id,
            text=expire_text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💵 Создать новый платеж", callback_data="add_balance")],
                [InlineKeyboardButton("👤 Профиль", callback_data="profile")]
            ])
        )
        
        if payment_id in payment_sessions:
            del payment_sessions[payment_id]
            
        logger.info(f"Истекший платеж {payment_id} для пользователя {user_id}")
        
    except Exception as e:
        logger.error(f"Error in process_expired_payment: {e}")

async def cleanup_task():
    """Фоновая задача для очистки старых сессий"""
    while True:
        try:
            cleaned_count = await asyncio.get_event_loop().run_in_executor(
                None, cleanup_old_sessions, payment_sessions, 30
            )
            if cleaned_count > 0:
                logger.info(f"Очищено {cleaned_count} старых сессий платежей")
            
            await asyncio.sleep(3600)
            
        except Exception as e:
            logger.error(f"Error in cleanup_task: {e}")
            await asyncio.sleep(300)

async def send_payment_status_update(query, payment_id):
    """Отправляет обновление статуса платежа"""
    try:
        if payment_id in payment_sessions:
            session = payment_sessions[payment_id]
            status = session['status']
            
            if status == 'completed':
                message = "✅ Платеж уже завершен и средства зачислены!"
            elif status == 'failed':
                message = "❌ Платеж не прошел. Попробуйте создать новый."
            elif status == 'pending':
                checks_done = session.get('checks_done', 0)
                message = f"🔄 Платеж обрабатывается... (проверка {checks_done}/30)"
            else:
                message = "⚡ Статус платежа неизвестен."
                
            await query.answer(message)
        else:
            await query.answer("❌ Сессия платежа не найдена!")
            
    except Exception as e:
        logger.error(f"Error in send_payment_status_update: {e}")
        await query.answer("❌ Ошибка при проверке статуса!")

async def process_successful_payment(payment_id, user_id, amount):
    """Обработка успешного платежа"""
    try:
        db = get_session(engine)
        user = db.query(User).filter(User.user_id == user_id).first()
        
        if user:
            user.balance += amount
            db.commit()
            
            from telegram import Bot
            bot = Bot(token=BOT_TOKEN)
            
            success_text = (
                f"✅ *Платеж подтвержден!*\n\n"
                f"💰 Зачислено: {amount} руб.\n"
                f"💳 Новый баланс: {user.balance} руб.\n"
                f"🔗 ID платежа: `{payment_id}`\n\n"
                f"Теперь вы можете совершать покупки! 🎉"
            )
            
            await bot.send_message(
                chat_id=user_id,
                text=success_text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🛍️ В магазин", callback_data="shop")],
                    [InlineKeyboardButton("👤 Профиль", callback_data="profile")]
                ])
            )
            
            if payment_id in payment_sessions:
                payment_sessions[payment_id]['status'] = 'completed'
                payment_sessions[payment_id]['actual_amount'] = amount
                
            logger.info(f"Успешный платеж {payment_id} на сумму {amount} руб. для пользователя {user_id}")
            
    except Exception as e:
        logger.error(f"Error in process_successful_payment: {e}")
    finally:
        db.close()

async def process_failed_payment(payment_id, user_id):
    """Обработка неудачного платежа"""
    try:
        from telegram import Bot
        bot = Bot(token=BOT_TOKEN)
        
        fail_text = (
            f"❌ *Платеж не прошел!*\n\n"
            f"🔗 ID платежа: `{payment_id}`\n\n"
            f"Попробуйте создать новый платеж или обратитесь в поддержку."
        )
        
        await bot.send_message(
            chat_id=user_id,
            text=fail_text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💵 Попробовать снова", callback_data="add_balance")],
                [InlineKeyboardButton("🆘 Поддержка", url="https://t.me/")]
            ])
        )
        
        if payment_id in payment_sessions:
            payment_sessions[payment_id]['status'] = 'failed'
            
        logger.info(f"Неудачный платеж {payment_id} для пользователя {user_id}")
        
    except Exception as e:
        logger.error(f"Error in process_failed_payment: {e}")

async def handle_check_payment(query):
    """Обработчик проверки статуса платежа"""
    try:
        payment_id = query.data.replace("check_payment_", "")
        await send_payment_status_update(query, payment_id)
            
    except Exception as e:
        logger.error(f"Error in handle_check_payment: {e}")
        await query.answer("❌ Ошибка при проверке статуса!")

async def cancel_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена процесса пополнения через команду"""
    await update.message.reply_text(
        "❌ Пополнение баланса отменено.",
        reply_markup=profile_keyboard()
    )
    return ConversationHandler.END

async def confirm_order(query):
    db = get_session(engine)
    try:
        user = db.query(User).filter(User.user_id == query.from_user.id).first()
        cart_items = db.query(CartItem).filter(CartItem.user_id == user.id).all()
        if not cart_items:
            await query.answer("❌ Корзина пуста!")
            return
        
        total_amount = sum(item.quantity * item.product.price for item in cart_items)
        if total_amount < 1500:
            await query.message.reply_text("❌ Минимальная сумма заказа - 1500 рублей. Добавьте еще товаров в корзину.")
            return
        
        if user.balance < total_amount:
            await query.message.reply_text(
                f"❌ Недостаточно средств на балансе!\n"
                f"💵 Нужно: {total_amount} руб.\n"
                f"💳 На балансе: {user.balance} руб.\n\n"
                f"Пополните баланс в разделе 👤 Профиль",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💵 Пополнить баланс", callback_data="profile")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
                ])
            )
            await query.answer("❌ Недостаточно средств на балансе!")
            return

        order = Order(user_id=user.id, total_amount=total_amount, status='pending')
        db.add(order)
        db.commit()
        
        order_items = []
        for item in cart_items:
            order_item = OrderItem(order_id=order.id, product_id=item.product_id, quantity=item.quantity, price=item.product.price)
            db.add(order_item)
            order_items.append(item)
        
        user.balance -= total_amount
        user.orders_count += 1
        db.query(CartItem).filter(CartItem.user_id == user.id).delete()
        db.commit()
        
        order_info = f"ФИО: \nЗаказ #{order.order_number}\nСумма: {total_amount} руб.\nТовары:\n"
        
        for item in order_items:
            order_info += f"- {item.product.name} x{item.quantity} = {item.quantity * item.product.price} руб.\n"
        
        order_info += "Доставка: 500р\nАдрес почты России: \nНомер телефона: "
        
        telegram_url = f"https://t.me/example?text={urllib.parse.quote(order_info)}"
        
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("📦 Указать адрес и телефон", url=telegram_url)],
            [InlineKeyboardButton("📋 Мои заказы", callback_data="orders")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ])
        
        await query.message.reply_text(
            f"✅ Заказ #{order.order_number} создан!\n"
            f"💵 Сумма: {total_amount} руб.\n\n"
            f"📦 Для указания адреса доставки и номера телефона нажмите кнопку ниже:",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Error in confirm_order: {e}")
        await query.answer("Произошла ошибка при оформлении заказа!")
    finally:
        db.close()

async def cancel_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик отмены платежа из callback"""
    query = update.callback_query
    await query.answer()
    
    await query.message.reply_text(
        "❌ Пополнение баланса отменено.",
        reply_markup=profile_keyboard()
    )
    return ConversationHandler.END

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    search_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_search, pattern="^search$")],
        states={SEARCH_QUERY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search_query)]},
        fallbacks=[CommandHandler('cancel', cancel_search)]
    )
    
    payment_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_add_balance, pattern="^add_balance$")],
        states={
            PAYMENT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_payment_amount)]
        },
        fallbacks=[
            CommandHandler('cancel', cancel_payment),
            CallbackQueryHandler(cancel_payment_callback, pattern="^profile$")
        ]
    )
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", show_menu))
    application.add_handler(CommandHandler("shop", show_shop))
    application.add_handler(CommandHandler("profile", show_profile))
    application.add_handler(CommandHandler("orders", show_orders))
    application.add_handler(CommandHandler("cart", show_cart))
    application.add_handler(search_conv_handler)
    application.add_handler(payment_conv_handler)
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    application.job_queue.run_once(lambda context: asyncio.create_task(cleanup_task()), when=1)
    
    logger.info("Бот запущен с полной платежной системой!")
    application.run_polling()

if __name__ == "__main__":
    main()