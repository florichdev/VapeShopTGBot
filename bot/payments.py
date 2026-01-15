import time
import requests
import pyzbar.pyzbar as pyzbar
import re
from playwright.sync_api import sync_playwright
from io import BytesIO
from PIL import Image
from config import STEAM_TRADER_COOKIES

def get_valid_session():
    """Используем готовые рабочие куки"""
    try:
        print("🔄 Используем готовые куки из конфига...")
        
        required_cookies = ['sid', 'csrf_token']
        for req_cookie in required_cookies:
            if req_cookie not in STEAM_TRADER_COOKIES:
                print(f"❌ Отсутствует важное куки в конфиге: {req_cookie}")
                return None, None
        
        cookies = STEAM_TRADER_COOKIES
        csrf_token = STEAM_TRADER_COOKIES['csrf_token']
        
        print(f"✅ Используем куки: {len(cookies)} шт.")
        print(f"✅ CSRF токен: {csrf_token[:20]}...")
        
        return cookies, csrf_token
        
    except Exception as e:
        print(f"❌ Ошибка при загрузке куки из конфига: {str(e)}")
        return None, None

def create_payment(amount):
    """Создает платеж и возвращает payment_id и ссылку на оплату"""
    try:
        print(f"💰 Создаем платеж на сумму: {amount} руб.")
        
        cookies, csrf_token = get_valid_session()
        
        if not cookies or not csrf_token:
            print("❌ Не удалось получить валидную сессию")
            return None, None
        
        headers = {
            'accept': 'application/json, text/javascript, */*; q=0.01',
            'accept-language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'origin': 'https://steam-trader.com',
            'referer': 'https://steam-trader.com/deposit/',
            'sec-ch-ua': '"Chromium";v="136", "Google Chrome";v="136", "Not:A-Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
            'x-requested-with': 'XMLHttpRequest'
        }
        
        data = {
            'payment_type': '28',
            'amount': str(amount),
            'fee': '1', 
            'csrf_token': csrf_token,
        }
        
        print(f"📤 Отправляем запрос на создание платежа...")
        print(f"🔑 Используем CSRF: {csrf_token[:20]}...")
        print(f"🍪 Используем куки: {len(cookies)} шт.")
        
        session = requests.Session()
        
        for name, value in cookies.items():
            session.cookies.set(name, value)
        
        response = session.post(
            'https://steam-trader.com/deposit/pay/',
            headers=headers,
            data=data,
            timeout=30
        )
        
        print(f"📥 Статус ответа: {response.status_code}")
        
        if response.status_code == 200:
            try:
                response_data = response.json()
                print(f"✅ Ответ JSON: {response_data}")
                
                if response_data.get('success'):
                    payment_url = response_data.get('redirect')
                    if payment_url:
                        payment_id = payment_url.split('/')[-2] if payment_url.endswith('/') else payment_url.split('/')[-1]
                        payment_link = f'https://payment.tome.ge/{payment_id}/receipt'
                        print(f"✅ Платеж создан! ID: {payment_id}")
                        return payment_id, payment_link
                    else:
                        print("❌ В ответе нет redirect ссылки")
                else:
                    error_msg = response_data.get('error', 'Неизвестная ошибка')
                    print(f"❌ Ошибка при создании платежа: {error_msg}")
            except Exception as e:
                print(f"❌ Ошибка парсинга JSON: {str(e)}")
                print(f"📄 Текст ответа: {response.text}")
        else:
            print(f"❌ HTTP ошибка: {response.status_code}")
            print(f"📄 Текст ответа: {response.text}")
                
        return None, None
        
    except Exception as e:
        print(f"❌ Исключение при создании платежа: {str(e)}")
        return None, None

def decode_qr_code(image_data):
    """Декодирует QR-код из изображения и возвращает ссылку."""
    try:
        image = Image.open(BytesIO(image_data))
        decoded_objects = pyzbar.decode(image)
        if decoded_objects:
            return decoded_objects[0].data.decode('utf-8')
        else:
            print("❌ QR-код не найден в изображении.")
            return None
    except Exception as e:
        print(f"❌ Ошибка при декодировании QR-кода: {str(e)}")
        return None

def get_qr_code_from_payment(payment_link):
    """Получает QR-код со страницы платежа"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        try:
            print(f"🌐 Открываем страницу платежа: {payment_link}")
            page.goto(payment_link, wait_until="networkidle")
            time.sleep(3)
            
            qr_areas = [
                {'x': 500, 'y': 100, 'width': 300, 'height': 300},
                {'x': 450, 'y': 80, 'width': 350, 'height': 350},
                {'x': 400, 'y': 50, 'width': 400, 'height': 400},
                {'x': 300, 'y': 0, 'width': 500, 'height': 500},
            ]
            
            qr_data = None
            for clip in qr_areas:
                try:
                    print(f"📸 Делаем скриншот области: {clip}")
                    screenshot = page.screenshot(clip=clip)
                    qr_data = decode_qr_code(screenshot)
                    if qr_data:
                        print(f"✅ QR-код найден!")
                        break
                except Exception as e:
                    print(f"⚠️ Ошибка при скриншоте: {str(e)}")
                    continue
            
            if qr_data:
                print(f"🔗 Ссылка из QR-кода: {qr_data}")
                return qr_data
            else:
                print("❌ Не удалось найти QR-код, возвращаем ссылку на оплату")
                return payment_link
                
        except Exception as e:
            print(f"❌ Ошибка при получении QR-кода: {str(e)}")
            return payment_link
        finally:
            browser.close()

def get_payment_qr_code(amount):
    """Основная функция для получения QR-кода оплаты"""
    payment_id, payment_link = create_payment(amount)
    
    if not payment_link:
        return None, None, None
    
    qr_link = get_qr_code_from_payment(payment_link)
    
    return payment_id, payment_link, qr_link

def check_payment_status(payment_id):
    """Проверяет статус платежа"""
    try:
        payment_url = f"https://payment.tome.ge/{payment_id}/receipt"
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            try:
                print(f"🔍 Проверяем статус платежа: {payment_url}")
                page.goto(payment_url, wait_until="networkidle")
                time.sleep(2)
                
                page_text = page.content().lower()
                
                success_indicators = ['оплачено', 'успешно', 'success', 'completed', 'подтвержден']
                failed_indicators = ['отклонен', 'ошибка', 'error', 'failed', 'отменен']
                
                for indicator in success_indicators:
                    if indicator in page_text:
                        print(f"✅ Платеж {payment_id} успешен!")
                        browser.close()
                        return "completed"
                
                for indicator in failed_indicators:
                    if indicator in page_text:
                        print(f"❌ Платеж {payment_id} отклонен!")
                        browser.close()
                        return "failed"
                
                print(f"🔄 Платеж {payment_id} в обработке")
                browser.close()
                return "pending"
                
            except Exception as e:
                print(f"❌ Ошибка при проверке статуса: {str(e)}")
                browser.close()
                return "error"
                
    except Exception as e:
        print(f"❌ Критическая ошибка при проверке статуса: {str(e)}")
        return "error"

def get_payment_amount(payment_id):
    """Получает сумму платежа"""
    try:
        payment_url = f"https://payment.tome.ge/{payment_id}/receipt"
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            try:
                page.goto(payment_url, wait_until="networkidle")
                time.sleep(2)
                
                page_text = page.content()
                
                amount_patterns = [
                    r'(\d+[\s,]*\d*\.?\d+)\s*руб',
                    r'(\d+[\s,]*\d*\.?\d+)\s*rub',
                    r'сумма[:\s]*(\d+[\s,]*\d*\.?\d+)',
                    r'(\d+[\s,]*\d*)\s*₽'
                ]
                
                for pattern in amount_patterns:
                    matches = re.search(pattern, page_text, re.IGNORECASE)
                    if matches:
                        amount_str = matches.group(1).replace(' ', '').replace(',', '.')
                        try:
                            amount = float(amount_str)
                            browser.close()
                            return int(amount)
                        except:
                            continue
                
                browser.close()
                return None
                
            except Exception as e:
                print(f"❌ Ошибка при получении суммы: {str(e)}")
                browser.close()
                return None
                
    except Exception as e:
        print(f"❌ Критическая ошибка при получении суммы: {str(e)}")
        return None

def cleanup_old_sessions(payment_sessions, max_age_minutes=30):
    """Очищает старые сессии платежей"""
    current_time = time.time()
    expired_sessions = []
    
    for payment_id, session in payment_sessions.items():
        session_age = current_time - session['created_at']
        if session_age > max_age_minutes * 60:
            expired_sessions.append(payment_id)
    
    for payment_id in expired_sessions:
        del payment_sessions[payment_id]
        print(f"🗑️ Удалена expired сессия: {payment_id}")
    
    return len(expired_sessions)