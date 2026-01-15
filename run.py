import subprocess
import threading

def run_bot():
    # Функция для запуска Telegram-бота.
    subprocess.run(["python", "bot/main.py"])

def run_admin_panel():
    # Функция для запуска админ-панели.
    subprocess.run(["python", "admin_panel/app.py"])

if __name__ == '__main__':
    # Запуск Telegram-бота в отдельном потоке
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.start()

    # Запуск админ-панели в основном потоке
    run_admin_panel()