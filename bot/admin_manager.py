#!/usr/bin/env python3
import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from werkzeug.security import generate_password_hash
from bot.database import User, Base, init_db

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

class SimpleAdminManager:
    def __init__(self):
        db_path = os.path.join(os.path.dirname(__file__), '..', 'shared_database.db')
        self.engine = create_engine(f'sqlite:///{db_path}', echo=False)
        self.Session = sessionmaker(bind=self.engine)
    
    def show_admins_simple(self):
        """Показать администраторов с ID и логинами"""
        db = self.Session()
        try:
            admins = db.query(User).filter(User.is_admin == True).all()
            
            if not admins:
                print("❌ Администраторы не найдены")
                return
            
            print("\n" + "="*50)
            print("👥 СПИСОК АДМИНИСТРАТОРОВ")
            print("="*50)
            
            for admin in admins:
                print(f"ID: {admin.id}")
                print(f"Логин: {admin.username}")
                print(f"User ID: {admin.user_id}")
                print("-" * 30)
            
        finally:
            db.close()
    
    def delete_admin(self, admin_id):
        """Удалить администратора по ID"""
        db = self.Session()
        try:
            admin = db.query(User).filter(User.id == admin_id, User.is_admin == True).first()
            
            if not admin:
                print(f"❌ Администратор с ID {admin_id} не найден")
                return False
            
            db.delete(admin)
            db.commit()
            
            print(f"✅ Администратор {admin.username} (ID: {admin.id}) удален")
            return True
            
        except Exception as e:
            db.rollback()
            print(f"❌ Ошибка при удалении: {e}")
            return False
        finally:
            db.close()
    
    def change_password(self, admin_id, new_password):
        """Сменить пароль администратора"""
        db = self.Session()
        try:
            admin = db.query(User).filter(User.id == admin_id, User.is_admin == True).first()
            
            if not admin:
                print(f"❌ Администратор с ID {admin_id} не найден")
                return False
            
            admin.password_hash = generate_password_hash(new_password)
            db.commit()
            
            print(f"✅ Пароль администратора {admin.username} (ID: {admin.id}) изменен")
            print(f"Новый пароль: {new_password}")
            return True
            
        except Exception as e:
            db.rollback()
            print(f"❌ Ошибка при смене пароля: {e}")
            return False
        finally:
            db.close()
    
    def add_admin(self, user_id, username, password):
        """Добавить нового администратора"""
        db = self.Session()
        try:
            existing_user = db.query(User).filter(User.user_id == user_id).first()
            
            if existing_user:
                if existing_user.is_admin:
                    print(f"❌ Пользователь с user_id {user_id} уже является администратором")
                    return False
                
                existing_user.is_admin = True
                existing_user.password_hash = generate_password_hash(password)
                db.commit()
                print(f"✅ Существующий пользователь {username} повышен до администратора")
                print(f"Пароль: {password}")
                return True
            
            new_admin = User(
                user_id=user_id,
                username=username,
                first_name="Admin",
                last_name="User",
                is_admin=True,
                balance=0.0,
                orders_count=0,
                is_banned=False
            )
            new_admin.password_hash = generate_password_hash(password)
            
            db.add(new_admin)
            db.commit()
            
            print(f"✅ Новый администратор {username} успешно добавлен!")
            print(f"User ID: {user_id}")
            print(f"Пароль: {password}")
            
            return True
            
        except Exception as e:
            db.rollback()
            print(f"❌ Ошибка при добавлении администратора: {e}")
            return False
        finally:
            db.close()

def main():
    """Основная функция"""
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python admin_manager.py list - показать всех админов")
        print("  python admin_manager.py add <user_id> <username> <password> - добавить админа")
        print("  python admin_manager.py delete <id> - удалить админа по ID")
        print("  python admin_manager.py password <id> <новый_пароль> - сменить пароль")
        return
    
    command = sys.argv[1].lower()
    manager = SimpleAdminManager()
    
    if command == "list":
        manager.show_admins_simple()
    
    elif command == "add" and len(sys.argv) >= 5:
        user_id = int(sys.argv[2])
        username = sys.argv[3]
        password = sys.argv[4]
        manager.add_admin(user_id, username, password)
    
    elif command == "delete" and len(sys.argv) >= 3:
        manager.delete_admin(int(sys.argv[2]))
    
    elif command == "password" and len(sys.argv) >= 4:
        manager.change_password(int(sys.argv[2]), sys.argv[3])
    
    else:
        print("❌ Неверная команда или недостаточно параметров")
        print("Доступные команды:")
        print("  list")
        print("  add <user_id> <username> <password>")
        print("  delete <id>")
        print("  password <id> <новый_пароль>")

if __name__ == "__main__":
    main()