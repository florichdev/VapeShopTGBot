"""
Конфигурационный файл для Vape Shop
ИНСТРУКЦИЯ: Скопируйте этот файл как config.py и заполните своими данными
"""

# Telegram Bot
BOT_TOKEN = 'YOUR_BOT_TOKEN_HERE'
BOT_USERNAME = 'your_bot_username'

# Администраторы (Telegram ID)
ADMIN_IDS = [123456789]

# Flask Admin Panel
SECRET_KEY = 'your-secret-key-for-flask-sessions'
FLASK_HOST = '0.0.0.0'
FLASK_PORT = 5000
DEBUG = True

# Database
DATABASE_PATH = 'shared_database.db'

# Payment settings (если используются платежи)
PAYMENT_TOKEN = 'YOUR_PAYMENT_PROVIDER_TOKEN'  # ЮKassa, Stripe и т.д.
PAYMENT_PROVIDER = 'provider_name'

# Настройки магазина
SHOP_NAME = 'Vape Shop'
CURRENCY = 'RUB'
CURRENCY_SYMBOL = '₽'

# Уведомления
NOTIFICATION_CHAT_ID = 123456789  # ID чата для уведомлений о заказах

# Логирование
LOG_LEVEL = 'INFO'
LOG_FILE = 'shop.log'