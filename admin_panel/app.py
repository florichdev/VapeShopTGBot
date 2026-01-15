import os
import sys
import threading
import time
import json
import enum
import requests
from datetime import datetime
from sqlalchemy import func, Date
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Float, Enum
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from bot.database import Base, User, Product, Order, OrderItem, CartItem, Category, init_db

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'
app.config['SECRET_KEY'] = 'admin-panel-secret'

engine = create_engine('sqlite:///shared_database.db')
Session = sessionmaker(bind=engine)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class AdminUser(UserMixin):
    def __init__(self, user_id):
        self.id = user_id

class OrderNote(Base):
    __tablename__ = 'order_notes'
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey('orders.id'))
    text = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

class OrderStatusHistory(Base):
    __tablename__ = 'order_status_history'
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey('orders.id'))
    status = Column(String(50))
    changed_at = Column(DateTime, default=datetime.now)

init_db()

def send_telegram_notification(user_id, message):
    try:
        try:
            from config import BOT_TOKEN
        except ImportError:
            print("⚠️ Файл config.py не найден!")
            return False
            
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        
        payload = {
            'chat_id': int(user_id),
            'text': message,
            'parse_mode': 'HTML'
        }
        
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            print(f"Уведомление отправлено пользователю {user_id}")
            return True
        else:
            error_data = response.json()
            print(f"Ошибка Telegram API: {response.status_code} - {error_data}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"Ошибка сети при отправке уведомления: {e}")
        return False
    except Exception as e:
        print(f"Неизвестная ошибка при отправке уведомления: {e}")
        return False

def check_product_availability(url):
    """
    Проверяет наличие товара на внешнем сайте
    Возвращает True если товар в наличии, False если нет
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        page_text = soup.get_text().lower().replace(' ', '')
        
        no_stock_indicators = [
            'нетиспользоватьсейчас', 'нетвналичии', 'распродано', 'outofstock',
            'недоступно', 'temporarilyoutofstock', 'ожидаетсяпоступление'
        ]
        
        for indicator in no_stock_indicators:
            if indicator in page_text:
                return False
        
        add_to_cart_selectors = [
            'a.btn--stock-info.cart-add',
            'a[class*="cart-add"]',
            'a[class*="add-to-cart"]',
            'button[class*="cart-add"]',
            'button[class*="add-to-cart"]',
            'a.btn-primary[onclick*="cart"]',
            'button.btn-primary[onclick*="cart"]'
        ]
        
        for selector in add_to_cart_selectors:
            if soup.select(selector):
                return True
        
        cart_elements = soup.find_all(class_=lambda x: x and any(word in str(x).lower() for word in ['cart', 'add-to', 'buy', 'купить']))
        if cart_elements:
            for element in cart_elements:
                if not any(word in element.get_text().lower() for word in ['нет', 'распродано', 'ожидается']):
                    return True
        
        return False
        
    except Exception as e:
        print(f"Ошибка при проверке товара {url}: {e}")
        return False

def check_single_product(product_id):
    db = Session()
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if product and product.external_url:
            is_available = check_product_availability(product.external_url)
            product.is_active = is_available
            product.last_checked = datetime.now()
            db.commit()
            return (product_id, is_available)
    except Exception as e:
        print(f"Ошибка при проверке товара {product_id}: {e}")
    finally:
        db.close()
    return (product_id, False)

def background_checker():
    """Фоновая задача для проверки наличия товаров"""
    while True:
        try:
            db = Session()
            products = db.query(Product).filter(Product.external_url.isnot(None)).all()
            
            with ThreadPoolExecutor(max_workers=5) as executor:
                results = list(executor.map(
                    lambda p: check_single_product(p.id), 
                    products
                ))
            
            print(f"Проверено {len(results)} товаров")
            time.sleep(3600)
        except Exception as e:
            print(f"Ошибка в фоновой задаче: {e}")
            time.sleep(300)

checker_thread = threading.Thread(target=background_checker, daemon=True)
checker_thread.start()

@login_manager.user_loader
def load_user(user_id):
    db = Session()
    try:
        user = db.query(User).filter(User.id == user_id, User.is_admin == True).first()
        if user:
            return AdminUser(user.id)
    finally:
        db.close()
    return None

@app.template_filter('groupby')
def groupby_filter(items, attribute):
    """Фильтр для группировки элементов по атрибуту"""
    groups = {}
    for item in items:
        key = getattr(item, attribute, None)
        if key not in groups:
            groups[key] = []
        groups[key].append(item)
    return groups.items()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        db = Session()
        try:
            user = db.query(User).filter(User.username == username, User.is_admin == True).first()
            
            if user and user.check_password(password):
                admin_user = AdminUser(user.id)
                login_user(admin_user)
                flash('Успешный вход в систему!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Неверные учетные данные или недостаточно прав', 'error')
        finally:
            db.close()
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    db = Session()
    try:
        stats = {
            'total_users': db.query(User).count(),
            'total_products': db.query(Product).count(),
            'total_orders': db.query(Order).count(),
            'pending_orders': db.query(Order).filter(Order.status == 'pending').count()
        }
        return render_template('dashboard.html', stats=stats)
    finally:
        db.close()

@app.route('/check_availability/<int:product_id>')
@login_required
def check_availability(product_id):
    """Проверить наличие конкретного товара"""
    db = Session()
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if product and product.external_url:
            is_available = check_product_availability(product.external_url)
            product.is_active = is_available
            product.last_checked = datetime.now()
            db.commit()
            flash(f'Товар {"в наличии" if is_available else "нет в наличии"}!', 'success')
        else:
            flash('Невозможно проверить товар без внешней ссылки!', 'warning')
        return redirect(url_for('products'))
    finally:
        db.close()

@app.route('/sync_all_products')
@login_required
def sync_all_products():
    """Синхронизировать все товары"""
    db = Session()
    try:
        products = db.query(Product).filter(Product.external_url.isnot(None)).all()
        checked_count = 0
        available_count = 0
        
        for product in products:
            is_available = check_product_availability(product.external_url)
            product.is_active = is_available
            product.last_checked = datetime.now()
            if is_available:
                available_count += 1
            checked_count += 1
        
        db.commit()
        flash(f'Проверено {checked_count} товаров. В наличии: {available_count}', 'success')
        return redirect(url_for('products'))
    finally:
        db.close()

@app.route('/products', methods=['GET'])
@login_required
def products():
    db = Session()
    try:
        products_list = db.query(Product).order_by(Product.category, Product.id.desc()).all()
        
        return render_template('products.html', products=products_list)
    finally:
        db.close()

@app.route('/products/add', methods=['POST'])
@login_required
def add_product():
    db = Session()
    try:
        external_url = request.form.get('external_url', '')
        is_active = 'is_active' in request.form
        
        final_active = False
        
        if external_url:
            is_available = check_product_availability(external_url)
            final_active = is_available 
            if is_available:
                flash('Товар проверен и доступен в наличии!', 'success')
            else:
                flash('Товар проверен - нет в наличии!', 'warning')
        elif is_active:
            final_active = True
            flash('⚠️ Товар активирован без проверки по ссылке!', 'warning')
        
        new_product = Product(
            name=request.form['name'],
            description=request.form['description'],
            price=float(request.form['price']),
            photo_gif_id=request.form.get('photo_gif_id', ''),
            external_url=external_url,
            category=request.form['category'],
            is_active=final_active,
            last_checked=datetime.now() if external_url else None
        )
        db.add(new_product)
        db.commit()
        flash('Товар успешно добавлен!')
        return redirect(url_for('products'))
    finally:
        db.close()

@app.route('/products/edit/<int:product_id>', methods=['POST'])
@login_required
def edit_product(product_id):
    db = Session()
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        
        if product:
            product.name = request.form['name']
            product.description = request.form['description']
            product.price = float(request.form['price'])
            product.photo_gif_id = request.form.get('photo_gif_id', '')
            old_external_url = product.external_url
            product.external_url = request.form.get('external_url', '') 
            product.category = request.form['category']
            
            if product.external_url and product.external_url != old_external_url:
                is_available = check_product_availability(product.external_url)
                product.is_active = is_available
                product.last_checked = datetime.now()
                status_msg = "в наличии" if is_available else "нет в наличии"
                flash(f'Товар проверен - {status_msg}!', 'info')
            elif not product.external_url and 'is_active' in request.form:
                product.is_active = True
                flash('⚠️ Товар активирован без проверки по ссылке!', 'warning')
            elif not product.external_url:
                product.is_active = False
            
            db.commit()
            flash('Товар успешно обновлен!')
        
        return redirect(url_for('products'))
    finally:
        db.close()

@app.route('/products/delete/<int:product_id>', methods=['POST'])
@login_required
def delete_product(product_id):
    db = Session()
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if product:
            db.query(CartItem).filter(CartItem.product_id == product_id).delete()
            
            order_items = db.query(OrderItem).filter(OrderItem.product_id == product_id).all()
            for item in order_items:
                order = db.query(Order).filter(Order.id == item.order_id).first()
                if order:
                    order.total_amount -= item.price * item.quantity
                db.delete(item)
            
            db.delete(product)
            db.commit()
            
            return jsonify({'success': True, 'message': 'Товар успешно удален!'})
        else:
            return jsonify({'success': False, 'message': 'Товар не найден!'}), 404
            
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': f'Ошибка при удалении товара: {str(e)}'}), 500
    finally:
        db.close()

@app.route('/debug_check/<path:url>')
@login_required
def debug_check(url):
    """Отладочная функция для проверки работы парсера"""
    result = check_product_availability(url)
    return jsonify({
        'url': url,
        'available': result,
        'message': 'Товар в наличии' if result else 'Товара нет в наличии'
    })

@app.route('/products/toggle/<int:product_id>')
@login_required
def toggle_product(product_id):
    db = Session()
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        
        if product:
            new_status = not product.is_active
            product.is_active = new_status
            
            if new_status and not product.external_url:
                flash('⚠️ Внимание: товар активирован без проверки по ссылке!', 'warning')
            elif new_status:
                flash('✅ Товар активирован вручную', 'success')
            else:
                flash('✅ Товар деактивирован', 'success')
            
            db.commit()
        
        return redirect(url_for('products'))
    finally:
        db.close()

@app.route('/orders')
@login_required
def orders():
    db = Session()
    try:
        active_orders = db.query(Order).filter(Order.status != 'delivered').order_by(Order.created_at.desc()).all()
        
        delivered_orders = db.query(Order).filter(Order.status == 'delivered').order_by(Order.created_at.desc()).all()
        
        for order in delivered_orders:
            order.status_history = db.query(OrderStatusHistory).filter(
                OrderStatusHistory.order_id == order.id
            ).order_by(OrderStatusHistory.changed_at.desc()).all()
            
        return render_template('orders.html', orders=active_orders, delivered_orders=delivered_orders)
    finally:
        db.close()

@app.route('/orders/<int:order_id>/details')
@login_required
def order_details(order_id):
    db = Session()
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if order:
            return jsonify({
                'order_number': order.order_number,
                'user_id': order.user_id,
                'total_amount': order.total_amount,
                'status': order.status,
                'tracking_number': order.tracking_number or '',
                'shipping_address': order.shipping_address or '',
                'phone_number': order.phone_number or '',
                'created_at': order.created_at.isoformat()
            })
        return jsonify({'error': 'Order not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()

@app.route('/orders/<int:order_id>/notes')
@login_required
def order_notes(order_id):
    db = Session()
    try:
        notes = db.query(OrderNote).filter(OrderNote.order_id == order_id).order_by(OrderNote.created_at.desc()).all()
        return jsonify([{
            'text': note.text,
            'created_at': note.created_at.isoformat()
        } for note in notes])
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()

@app.route('/orders/add-note', methods=['POST'])
@login_required
def add_order_note():
    db = Session()
    try:
        order_id = request.form['order_id']
        note_text = request.form['note']
        
        note = OrderNote(order_id=order_id, text=note_text)
        db.add(note)
        db.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        db.close()

@app.route('/orders/update-tracking', methods=['POST'])
@login_required
def update_tracking():
    db = Session()
    try:
        order_id = request.form['order_id']
        tracking_number = request.form.get('tracking_number', '')
        shipping_address = request.form.get('shipping_address', '')
        phone_number = request.form.get('phone_number', '')
        
        order = db.query(Order).filter(Order.id == order_id).first()
        if order:
            old_tracking_number = order.tracking_number
            
            order.tracking_number = tracking_number
            order.shipping_address = shipping_address
            order.phone_number = phone_number
            db.commit()
            
            if tracking_number and tracking_number != old_tracking_number:
                user = db.query(User).filter(User.id == order.user_id).first()
                if user:
                    message = (
                        f"📦 <b>Обновление информации о заказе</b>\n\n"
                        f"🔖 Номер заказа: #{order.order_number}\n"
                        f"📦 Вашему заказу присвоен трек-номер: {tracking_number}\n\n"
                        f"📍 Адрес доставки: {shipping_address or 'уточняется'}\n"
                        f"📞 Телефон: {phone_number or 'уточняется'}"
                    )
                    send_telegram_notification(user.user_id, message)
            
        return jsonify({'success': True})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        db.close()

@app.route('/orders/delete/<int:order_id>')
@login_required
def delete_order(order_id):
    db = Session()
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if order:
            db.query(OrderItem).filter(OrderItem.order_id == order_id).delete()
            db.query(OrderNote).filter(OrderNote.order_id == order_id).delete()
            db.query(OrderStatusHistory).filter(OrderStatusHistory.order_id == order_id).delete()
            
            db.delete(order)
            db.commit()
            flash('Заказ удален успешно!')
        return redirect(url_for('orders'))
    except Exception as e:
        db.rollback()
        flash(f'Ошибка при удалении заказа: {str(e)}')
        return redirect(url_for('orders'))
    finally:
        db.close()

@app.route('/orders/contact-user/<int:order_id>')
@login_required
def contact_order_user(order_id):
    db = Session()
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if order and order.user:
            telegram_url = f"https://t.me/{order.user.username}" if order.user.username else f"tg://user?id={order.user.user_id}"
            return redirect(telegram_url)
        else:
            flash('Пользователь не найден или не имеет username!')
            return redirect(url_for('orders'))
    finally:
        db.close()

@app.route('/orders/update-status/<int:order_id>', methods=['POST'])
@login_required
def update_order_status(order_id):
    db = Session()
    try:
        new_status = request.form['status']
        order = db.query(Order).filter(Order.id == order_id).first()
        
        if order and order.user_id:
            user = db.query(User).filter(User.id == order.user_id).first()
            if not user:
                flash('❌ Пользователь не найден!')
                return redirect(url_for('orders'))
            
            history = OrderStatusHistory(
                order_id=order_id,
                status=new_status
            )
            db.add(history)
            
            order.status = new_status
            db.commit()
            
            status_translations = {
                'pending': '⏳ Ожидает обработки',
                'processing': '🔧 Обрабатывается',
                'shipped': '🚚 Отправлен',
                'delivered': '✅ Доставлен',
                'cancelled': '❌ Отменен'
            }
            
            message = (
                f"📦 <b>Обновление статуса заказа</b>\n\n"
                f"🔖 Номер заказа: #{order.order_number}\n"
                f"📊 Статус: {status_translations.get(new_status, new_status)}\n"
            )
            
            if new_status == 'shipped' and order.tracking_number:
                message += f"📦 Трек-номер: {order.tracking_number}\n"
            
            success = send_telegram_notification(user.user_id, message)
            
            if success:
                flash('✅ Статус заказа обновлен и уведомление отправлено!')
            else:
                flash('⚠️ Статус заказа обновлен, но уведомление не отправлено!')
        
        return redirect(url_for('orders'))
        
    except Exception as e:
        db.rollback()
        flash(f'❌ Ошибка при обновлении статуса: {str(e)}')
        return redirect(url_for('orders'))
    finally:
        db.close()

@app.route('/orders/<int:order_id>/status-history')
@login_required
def order_status_history(order_id):
    db = Session()
    try:
        history = db.query(OrderStatusHistory).filter(
            OrderStatusHistory.order_id == order_id
        ).order_by(OrderStatusHistory.changed_at.desc()).all()
        
        return jsonify([{
            'status': item.status,
            'changed_at': item.changed_at.isoformat()
        } for item in history])
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()

@app.route('/users')
@login_required
def users():
    db = Session()
    try:
        users_list = db.query(User).order_by(User.created_at.desc()).all()
        
        for user in users_list:
            user.created_at_date = user.created_at.strftime('%Y-%m-%d')
            
        return render_template('users.html', users=users_list)
    finally:
        db.close()

@app.route('/users/toggle/<int:user_id>', methods=['POST'])
@login_required
def toggle_user(user_id):
    db = Session()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.is_banned = not user.is_banned
            db.commit()
            status = "разблокирован" if not user.is_banned else "заблокирован"
            flash(f'Пользователь {status}!')
        return redirect(url_for('users'))
    finally:
        db.close()

@app.route('/create-test-order')
@login_required
def create_test_order():
    db = Session()
    try:
        test_user = db.query(User).filter(User.username == 'test_user').first()
        if not test_user:
            test_user = User(
                user_id=999999999,
                username='test_user',
                first_name='Test',
                last_name='User',
                balance=5000.0
            )
            db.add(test_user)
            db.commit()
        
        test_order = Order(
            user_id=test_user.id,
            total_amount=2500.0,
            status='processing',
            tracking_number='RB123456789RU',
            shipping_address='г. Москва, ул. Тестовая, д. 123, кв. 45'
        )
        db.add(test_order)
        db.commit()
        
        status_history = [
            OrderStatusHistory(order_id=test_order.id, status='pending'),
            OrderStatusHistory(order_id=test_order.id, status='processing')
        ]
        db.add_all(status_history)
        
        notes = [
            OrderNote(order_id=test_order.id, text='Тестовый заказ для демонстрации'),
            OrderNote(order_id=test_order.id, text='Клиент указал адрес почты России')
        ]
        db.add_all(notes)
        
        db.commit()
        
        flash('Тестовый заказ создан успешно!')
        return redirect(url_for('orders'))
    
    except Exception as e:
        db.rollback()
        flash(f'Ошибка при создании тестового заказа: {str(e)}')
        return redirect(url_for('orders'))
    finally:
        db.close()

@app.route('/add-balance/<int:user_id>', methods=['POST'])
@login_required
def add_user_balance(user_id):
    db = Session()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            amount = float(request.form['amount'])
            user.balance += amount
            db.commit()
            flash(f'Баланс пользователя {user.username} пополнен на {amount} руб.!')
        return redirect(url_for('users'))
    except Exception as e:
        db.rollback()
        flash(f'Ошибка при пополнении баланса: {str(e)}')
        return redirect(url_for('users'))
    finally:
        db.close()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)