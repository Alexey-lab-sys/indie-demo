import os
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from models import db, User, Game, Message
import bcrypt
from datetime import datetime

# ========== 1. СОЗДАЁМ ПРИЛОЖЕНИЕ ==========
app = Flask(__name__)
app.secret_key = 'supersecretkey'  # нужно для сессий

# ========== 2. НАСТРАИВАЕМ БАЗУ ДАННЫХ ==========
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///indie_demo.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Исправь опечатку!

# ========== 3. НАСТРАИВАЕМ ЗАГРУЗКУ ФАЙЛОВ ==========
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'zip', 'rar', '7z', 'exe', 'msi', 'dmg', 'pkg'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100 MB

# Создаём папку для загрузок, если её нет
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    """Проверяет расширение файла"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ========== 4. ИНИЦИАЛИЗИРУЕМ БД ==========
db.init_app(app)

# Создаём таблицы при первом запуске
with app.app_context():
    db.create_all()

# ========== 5. МАРШРУТЫ ==========

@app.route('/')
def index():
    """ Главная страница - показывает все одобренные игры."""
    games = Game.query.filter_by(is_approved=True).all()
    return render_template('index.html', games=games)

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Регистрация нового пользователя."""
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        # Хешируем пароль
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        # Создаём пользователя
        new_user = User(username=username, email=email, password_hash=hashed)

        try:
            db.session.add(new_user)
            db.session.commit()
            flash('Регистрация успешна! Войдите в аккаунт.', 'success')
            return redirect(url_for('login'))
        except:
            flash('Ошибка: пользователь или email уже существуют', 'danger')
            return redirect(url_for('register'))
    return render_template('register.html')


def is_admin():
    """Проверяет, является ли текущий пользователь администратором."""
    if 'username' not in session:
        return False
    # Админ — пользователь с id = 1 (или можно проверить по username)
    return session.get('username') == 'admin'


@app.route('/admin')
def admin_panel():
    """Админ-панель: список игр на модерацию."""
    if not is_admin():
        flash('Доступ запрещён. Только для администратора.', 'danger')
        return redirect(url_for('index'))
    
    # Игры на модерацию (не одобренные)
    pending_games = Game.query.filter_by(is_approved=False).all()
    # Все игры (для общего списка)
    all_games = Game.query.all()
    
    return render_template('admin.html', pending_games=pending_games, all_games=all_games)


@app.route('/admin/approve/<int:game_id>')
def approve_game(game_id):
    if not is_admin():
        flash('Доступ запрещён.', 'danger')
        return redirect(url_for('index'))
    
    game = Game.query.get_or_404(game_id)
    game.is_approved = True
    db.session.commit()
    flash(f'Игра "{game.title}" одобрена!', 'success')
    return redirect(url_for('admin_panel'))


@app.route('/admin/delete/<int:game_id>')
def delete_game(game_id):
    if not is_admin():
        flash('Доступ запрещён.', 'danger')
        return redirect(url_for('index'))
    
    game = Game.query.get_or_404(game_id)
    
    # Проверяем, есть ли файл у этой игры
    file_to_delete = game.demo_file_path
    
    # Удаляем игру из БД
    db.session.delete(game)
    db.session.commit()
    
    # Проверяем, используется ли этот файл другими играми
    if file_to_delete:
        # Ищем другие игры с таким же путём
        other_games = Game.query.filter_by(demo_file_path=file_to_delete).count()
        
        # Если никто больше не использует файл — удаляем его с диска
        if other_games == 0:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_to_delete)
            if os.path.exists(file_path):
                os.remove(file_path)
                flash(f'Файл "{file_to_delete}" удалён с диска.', 'info')
        else:
            flash(f'Файл "{file_to_delete}" оставлен, так как используется другими играми.', 'info')
    
    flash(f'Игра "{game.title}" удалена.', 'warning')
    return redirect(url_for('admin_panel'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Вход в аккаунт."""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()

        if user and bcrypt.checkpw(password.encode('utf-8'), user.password_hash):
            session['user_id'] = user.id
            session['username'] = user.username
            flash(f'Добро пожаловать, {user.username}!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Неверное имя пользователя или пароль', 'danger')
            return redirect(url_for('login'))
    return render_template('login.html')


@app.route('/chat')
def chat():
    """ Страница чата """
    # Проверяем, авторизован ли пользователь
    if 'user_id' not in session:
        flash('Сначала войдите в аккаунт, чтобы писать в чат!', 'danger')
        return redirect(url_for('login'))
    
    # Получаем все сообщения (сортировка по дате)
    messages = Message.query.order_by(Message.created_at.asc()).all()
    return render_template('chat.html', messages=messages)

@app.route('/send_message', methods=['POST'])
def send_message():
    """ Отправка нового сообщения """
    if 'user_id' not in session:
        return {'error': 'Не авторизован'}, 401
    
    text = request.form.get('text', '').strip()
    if not text:
        return {'error': 'Сообщение не может быть пустым'}, 400
    
    new_message = Message(
        text=text,
        user_id=session['user_id']
    )
    db.session.add(new_message)
    db.session.commit()
    
    return {'status': 'ok'}

@app.route('/get_messages')
def get_messages():
    """ API для получения новых сообщений (для автоподгрузки) """
    if 'user_id' not in session:
        return {'error': 'Не авторизован'}, 401
    
    # Получаем ID последнего сообщения, которое есть у пользователя
    last_id = request.args.get('last_id', 0, type=int)
    
    # Ищем сообщения, которые больше last_id
    new_messages = Message.query.filter(Message.id > last_id).order_by(Message.created_at.asc()).all()
    
    # Форматируем для JSON
    messages_data = []
    for msg in new_messages:
        messages_data.append({
            'id': msg.id,
            'username': msg.user.username,
            'text': msg.text,
            'created_at': msg.created_at.strftime('%H:%M')
        })
    
    return {'messages': messages_data}


@app.route('/logout')
def logout():
    """Выход из аккаунта."""
    session.clear()
    flash('Вы вышли из аккаунта.', 'info')
    return redirect(url_for('index'))

# ========== 6. ЗАГРУЗКА ИГРЫ ==========

@app.route('/upload', methods=['GET', 'POST'])
def upload_game():
    """Страница загрузки новой игры."""
    # Проверяем, авторизован ли пользователь
    if 'user_id' not in session:
        flash('Сначала войдите в аккаунт!', 'danger')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        # Получаем данные из формы
        title = request.form.get('title')
        description = request.form.get('description')
        genre = request.form.get('genre')
        platform = request.form.get('platform')
        
        # Проверяем обязательные поля
        if not title or not description:
            flash('Название и описание обязательны!', 'danger')
            return redirect(url_for('upload_game'))
        
        # Обрабатываем файл
        file = request.files.get('demo_file')
        filename = None
        
        if file and allowed_file(file.filename):
            # Безопасное имя файла + временная метка
            original_name = secure_filename(file.filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{timestamp}_{original_name}"
            
            # Сохраняем файл
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
        else:
            flash('Неверный формат файла. Разрешены: zip, rar, 7z, exe, msi, dmg, pkg', 'danger')
            return redirect(url_for('upload_game'))
        
        # Создаём игру в БД
        new_game = Game(
            title=title,
            description=description,
            genre=genre,
            platform=platform,
            demo_file_path=filename,
            developer_id=session['user_id'],
            is_approved=False,
            downloads_count=0
        )
        
        db.session.add(new_game)
        db.session.commit()
        
        flash('Игра успешно загружена! Ожидайте модерации.', 'success')
        return redirect(url_for('index'))
    
    # GET-запрос — показываем форму
    return render_template('upload.html')


@app.route('/download/<int:game_id>')
def download_game(game_id):
    """Скачивание демо-версии игры."""
    # Ищем игру
    game = Game.query.get_or_404(game_id)
    
    # Проверяем, одобрена ли игра
    if not game.is_approved:
        flash('Эта игра ещё не прошла модерацию.', 'danger')
        return redirect(url_for('index'))
    
    # Проверяем, есть ли файл
    if not game.demo_file_path:
        flash('Файл демо-версии не найден.', 'danger')
        return redirect(url_for('index'))
    
    # Увеличиваем счётчик скачиваний
    game.downloads_count = (game.downloads_count or 0) + 1
    db.session.commit()
    
    # Отдаём файл на скачивание
    return send_from_directory(
        app.config['UPLOAD_FOLDER'],
        game.demo_file_path,
        as_attachment=True,
        download_name=f"{game.title}_demo.zip"  # красивое имя файла
    )

# ========== 7. ЗАПУСК ==========

if __name__ == '__main__':
    app.run(debug=True)