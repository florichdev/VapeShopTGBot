import uuid
import os
import enum
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

Base = declarative_base()

class Category(enum.Enum):
    DISPOSABLE = "Одноразовые вейпы"
    HOOKAH = "Электронные кальяны"
    POD = "POD Системы"
    CARTRIDGES = "Картриджи"
    SNUS = "Снюс"
    LIQUIDS = "Жидкости"
    TOBACCO = "Табак для кальяна"

def generate_order_id():
    return str(uuid.uuid4())[:8].upper()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(100))
    first_name = Column(String(100))
    last_name = Column(String(100))
    password_hash = Column(String(200))
    balance = Column(Float, default=0.0)
    orders_count = Column(Integer, default=0)
    is_admin = Column(Boolean, default=False)
    is_banned = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    
    cart_items = relationship("CartItem", back_populates="user")
    orders = relationship("Order", back_populates="user")
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Product(Base):
    __tablename__ = 'products'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    price = Column(Float, nullable=False)
    photo_gif_id = Column(String(200))
    external_url = Column(String(500))
    quantity = Column(Integer, default=0)
    category = Column(Enum(Category), nullable=False)
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    last_checked = Column(DateTime) 

class CartItem(Base):
    __tablename__ = 'cart_items'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    product_id = Column(Integer, ForeignKey('products.id'))
    quantity = Column(Integer, default=1)
    
    user = relationship("User", back_populates="cart_items")
    product = relationship("Product")

class Order(Base):
    __tablename__ = 'orders'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    total_amount = Column(Float)
    status = Column(String(50), default='pending')
    tracking_number = Column(String(100), nullable=True)
    shipping_address = Column(Text, nullable=True)
    phone_number = Column(String(20), nullable=True)
    order_number = Column(String(20), unique=True, default=generate_order_id)
    created_at = Column(DateTime, default=datetime.now)
    
    user = relationship("User", back_populates="orders")
    items = relationship("OrderItem", back_populates="order")

class OrderItem(Base):
    __tablename__ = 'order_items'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey('orders.id'))
    product_id = Column(Integer, ForeignKey('products.id'))
    quantity = Column(Integer, default=1)
    price = Column(Float, nullable=False)
    
    order = relationship("Order", back_populates="items")
    product = relationship("Product")

def init_db():
    db_path = 'shared_database.db'
    engine = create_engine(f'sqlite:///{db_path}', echo=False)
    Base.metadata.create_all(engine)
    
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        # Тестовые данные для товаров - все неактивные по умолчанию
        if db.query(Product).count() == 0:
            test_products = [
                Product(name="HQD CUVIE Plus", description="Одноразовый вейп 2000 затяжек", price=1290, category=Category.DISPOSABLE, is_active=False),
                Product(name="ELF BAR 600", description="Одноразовый вейп с мятным вкусом", price=1490, category=Category.DISPOSABLE, is_active=False),
                Product(name="Puff Bar", description="Компактный одноразовый вейп", price=1190, category=Category.DISPOSABLE, is_active=False),
                Product(name="Maskking", description="Одноразовый вейп премиум класса", price=1690, category=Category.DISPOSABLE, is_active=False),
                Product(name="IGET Legend", description="Мощный одноразовый вейп", price=1590, category=Category.DISPOSABLE, is_active=False),
                Product(name="Vozol Star", description="Стильный одноразовый вейп", price=1390, category=Category.DISPOSABLE, is_active=False),
                Product(name="Bang XXL", description="Одноразовый вейп на 3000 затяжек", price=1790, category=Category.DISPOSABLE, is_active=False),
                Product(name="Lost Mary", description="Популярный одноразовый вейп", price=1490, category=Category.DISPOSABLE, is_active=False),
                
                Product(name="IQOS ILUMA Prime", description="Премиум POD система", price=6990, category=Category.POD, is_active=False),
                Product(name="JUUL Starter Kit", description="Набор для начала использования", price=2990, category=Category.POD, is_active=False),
                Product(name="Vaporesso XROS", description="Современная POD система", price=2490, category=Category.POD, is_active=False),
                Product(name="Uwell Caliburn", description="Популярная POD система", price=2190, category=Category.POD, is_active=False),
                Product(name="Smok Novo", description="Компактная POD система", price=1990, category=Category.POD, is_active=False),
                Product(name="Voopoo Drag", description="Мощная POD система", price=3490, category=Category.POD, is_active=False),
                
                Product(name="Jam Monster", description="Жидкость с вкусом джема", price=790, category=Category.LIQUIDS, is_active=False),
                Product(name="Nasty Juice", description="Премиум жидкость", price=890, category=Category.LIQUIDS, is_active=False),
                Product(name="Dinner Lady", description="Классическая жидкость", price=690, category=Category.LIQUIDS, is_active=False),
                Product(name="Element", description="Американская жидкость", price=990, category=Category.LIQUIDS, is_active=False),
                Product(name="Riot Squad", description="Энергетическая жидкость", price=850, category=Category.LIQUIDS, is_active=False),
                Product(name="Doozy", description="Британская жидкость", price=750, category=Category.LIQUIDS, is_active=False),
                
                Product(name="JUUL Pods Mango", description="Картриджи с манговым вкусом", price=490, category=Category.CARTRIDGES, is_active=False),
                Product(name="IQOS TEREA", description="Картриджи для IQOS", price=590, category=Category.CARTRIDGES, is_active=False),
                Product(name="GLO Hyper", description="Картриджи для GLO", price=520, category=Category.CARTRIDGES, is_active=False),
                Product(name="Ploom Tech", description="Картриджи для Ploom", price=480, category=Category.CARTRIDGES, is_active=False),
            ]
            db.add_all(test_products)
            db.commit()
            
    except Exception as e:
        print(f"Произошла ошибка: {e}")
        db.rollback()
    finally:
        db.close()
    
    return engine

def get_session(engine):
    Session = sessionmaker(bind=engine)
    return Session()