import os
from flask import Flask, render_template, abort, request
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

# --- Настройки подключения к БД (такие же, как в боте) ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'bot_database.db')

engine = create_engine(f'sqlite:///{DB_PATH}')
Base = declarative_base()
Session = sessionmaker(bind=engine)

# --- Копия модели User из кода бота ---
class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True, nullable=False)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    referrer_id = Column(Integer, nullable=True)
    referral_count = Column(Integer, default=0)
    is_subscribed = Column(Boolean, default=False)
    registration_date = Column(DateTime, default=datetime.now)

# --- Создание Flask-приложения ---
app = Flask(__name__)

@app.route('/')
def index():
    """Главная страница, которая отображает список пользователей с сортировкой."""
    session = Session()
    try:
        # Получаем параметры сортировки из URL
        sort_by = request.args.get('sort', 'registration_date')  # По умолчанию сортируем по дате
        order = request.args.get('order', 'desc')  # По умолчанию по убыванию
        
        total_users = session.query(User).count()
        subscribed_users = session.query(User).filter(User.is_subscribed == True).count()
        
        # Определяем поле для сортировки
        if sort_by == 'referral_count':
            sort_field = User.referral_count
        else:
            sort_field = User.registration_date
        
        # Применяем сортировку
        if order == 'asc':
            all_users = session.query(User).order_by(sort_field.asc()).all()
        else:
            all_users = session.query(User).order_by(sort_field.desc()).all()
        
        return render_template('index.html', 
                             users=all_users, 
                             total_users=total_users,
                             subscribed_users=subscribed_users,
                             current_sort=sort_by,
                             current_order=order)
    finally:
        session.close()

@app.route('/top50')
def top50():
    """Страница TOP-50 - пользователи с 50+ рефералами."""
    session = Session()
    try:
        # Находим пользователей с 50+ рефералами, сортируем по количеству рефералов
        top_users = session.query(User).filter(User.referral_count >= 50).order_by(User.referral_count.desc()).all()
        
        return render_template('top50.html', top_users=top_users, total_top=len(top_users))
    finally:
        session.close()

@app.route('/user/<int:user_id>')
def user_details(user_id):
    """Страница с детальной информацией о пользователе и его рефералах."""
    session = Session()
    try:
        # Находим основного пользователя (того, на кого кликнули)
        referrer = session.query(User).filter(User.user_id == user_id).first()
        
        # Если пользователь с таким ID не найден, показываем ошибку 404
        if not referrer:
            abort(404, description="Пользователь не найден")
            
        # Находим всех, кого он пригласил (его рефералов)
        # Ищем пользователей, у которых в поле referrer_id стоит ID нашего пользователя
        referrals = session.query(User).filter(User.referrer_id == user_id).order_by(User.registration_date.asc()).all()
        
        return render_template('user_detail.html', referrer=referrer, referrals=referrals)
    finally:
        session.close()


if __name__ == '__main__':
    print("🚀 Запуск веб-панели администратора...")
    print("✅ Откройте в браузере: http://127.0.0.1:5001")
    app.run(debug=True, port=5001)
