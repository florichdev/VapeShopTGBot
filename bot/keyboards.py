import urllib.parse
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from database import Category

def main_menu_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("🛍️ Магазин", callback_data="shop"),
            InlineKeyboardButton("👤 Профиль", callback_data="profile")
        ],
        [
            InlineKeyboardButton("📦 Заказы", callback_data="orders"),
            InlineKeyboardButton("🛒 Корзина", callback_data="cart")
        ],
        [
            InlineKeyboardButton("📢 Наш канал", url="https://t.me/"),
            InlineKeyboardButton("⭐ Отзывы", url="https://t.me/")
        ],
        [
            InlineKeyboardButton("🆘 Поддержка", url="https://t.me/")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def balance_keyboard():
    keyboard = [
        [InlineKeyboardButton("💵 Пополнить баланс", callback_data="add_balance")],
        [InlineKeyboardButton("📦 Мои заказы", callback_data="orders")],
        [InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def profile_keyboard():
    keyboard = [
        [InlineKeyboardButton("💵 Пополнить баланс", callback_data="add_balance")],
        [InlineKeyboardButton("📦 Мои заказы", callback_data="orders")],
        [InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def orders_keyboard():
    keyboard = [
        [InlineKeyboardButton("↩️ В главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def cart_keyboard():
    keyboard = [
        [InlineKeyboardButton("🛍️ В магазин", callback_data="shop")],
        [InlineKeyboardButton("↩️ В главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def categories_keyboard():
    keyboard = [
        [InlineKeyboardButton("🔍 Поиск товара", callback_data="search")],
        [InlineKeyboardButton("💨 Одноразовые вейпы", callback_data="category_DISPOSABLE")],
        [InlineKeyboardButton("🪔 Электронные кальяны", callback_data="category_HOOKAH")],
        [
            InlineKeyboardButton("💨 POD Системы", callback_data="category_POD"),
            InlineKeyboardButton("️🛠️ Картриджи", callback_data="category_CARTRIDGES")
        ],
        [
            InlineKeyboardButton("🍃 Снюс", callback_data="category_SNUS"),
            InlineKeyboardButton("🧪 Жидкости", callback_data="category_LIQUIDS")
        ],
        [InlineKeyboardButton("🍂 Табак для кальяна", callback_data="category_TOBACCO")],
        [InlineKeyboardButton("↩️ В главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def products_keyboard(products, current_page, total_pages, category):
    keyboard = []
    
    for i in range(0, len(products), 2):
        row = []
        for j in range(2):
            if i + j < len(products):
                product = products[i + j]
                row.append(InlineKeyboardButton(
                    product.name,
                    callback_data=f"product_{product.id}"
                ))
        if row:
            keyboard.append(row)
    
    nav_buttons = []
    if current_page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️", callback_data=f"page_{category.name}_{current_page - 1}"))
    else:
        nav_buttons.append(InlineKeyboardButton("⏹️", callback_data="no_action"))
    
    nav_buttons.append(InlineKeyboardButton("🏠", callback_data="main_menu"))
    
    if current_page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("➡️", callback_data=f"page_{category.name}_{current_page + 1}"))
    else:
        nav_buttons.append(InlineKeyboardButton("⏹️", callback_data="no_action"))
    
    keyboard.append(nav_buttons)
    keyboard.append([InlineKeyboardButton(f"📄 Страница {current_page + 1}/{total_pages}", callback_data="page_info")])
    keyboard.append([InlineKeyboardButton("↩️ К категориям", callback_data="shop")])
    
    return InlineKeyboardMarkup(keyboard)

def product_keyboard(product_id):
    keyboard = [
        [
            InlineKeyboardButton("🛒 В корзину", callback_data=f"add_cart_{product_id}"),
            InlineKeyboardButton("💰 Купить сейчас", callback_data=f"buy_now_{product_id}")
        ],
        [InlineKeyboardButton("↩️ Назад", callback_data="back_to_products")]
    ]
    return InlineKeyboardMarkup(keyboard)

def search_keyboard():
    keyboard = [
        [InlineKeyboardButton("↩️ Отменить поиск", callback_data="shop")]
    ]
    return InlineKeyboardMarkup(keyboard)

def cart_items_keyboard(cart_items):
    keyboard = []
    
    for item in cart_items:
        keyboard.append([InlineKeyboardButton(
            f"❌ Удалить {item.product.name}",
            callback_data=f"remove_cart_{item.id}"
        )])
    
    keyboard.append([InlineKeyboardButton("💳 Оформить заказ", callback_data="confirm_order")])
    keyboard.append([InlineKeyboardButton("↩️ В главное меню", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(keyboard)

def after_order_keyboard(order_number, total_amount, order_items):
    order_info = f"Заказ #{order_number}\nСумма: {total_amount} руб.\nТовары:\n"
    
    for item in order_items:
        order_info += f"- {item.product.name} x{item.quantity} = {item.quantity * item.product.price} руб.\n"
    
    order_info += "Адрес почты России: \nНомер телефона: "
    telegram_url = f"https://t.me/example?text={urllib.parse.quote(order_info)}"
    
    keyboard = [
        [InlineKeyboardButton("📦 Указать адрес и телефон", url=telegram_url)],
        [InlineKeyboardButton("📋 Мои заказы", callback_data="orders")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)