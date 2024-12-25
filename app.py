from flask import Flask, render_template, request, redirect, session, url_for, flash
import psycopg2
from psycopg2.extras import RealDictCursor
from flask_bcrypt import Bcrypt
import re
import plotly.graph_objs as go
import plotly.io as pio
from datetime import datetime

app = Flask(__name__)
app.secret_key = "mylittlesecret"  # Секретный ключ для сессий
bcrypt = Bcrypt(app)

DB_CONFIG = {
    'dbname': 'db',
    'user': 'postgres',
    'password': '9453',
    'host': 'localhost',
    'port': '5432'
}

def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

# Выполнение SQL-запросов
def execute_query(query, params=(), fetchone=False, fetchall=False):
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            if fetchone:
                return cur.fetchone()
            if fetchall:
                return cur.fetchall()
            conn.commit()
    finally:
        conn.close()

# Валидация данных
def validate_phone(phone):
    return re.fullmatch(r"\d{11}", phone) is not None

def validate_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email) is not None

def validate_health_data(pulse, temperature, sugar_level, weight, growth):
    if not (0 <= pulse <= 300):
        raise ValueError("Пульс должен быть в диапазоне от 0 до 300.")
    if not (30.0 <= temperature <= 45.0):
        raise ValueError("Температура должна быть в диапазоне от 30.0 до 45.0.")
    if sugar_level < 0:
        raise ValueError("Уровень сахара должен быть неотрицательным.")
    if weight < 0:
        raise ValueError("Вес должен быть неотрицательным.")
    if not (50 < growth < 250):
        raise ValueError("Рост должен быть в диапазоне от 50 до 250.")


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')
        name = request.form['name']
        surname = request.form['surname']
        phone = request.form['phone']
        email = request.form['email']

        if not validate_phone(phone):
            flash("Некорректный номер телефона! Должен содержать 11 цифр.", "error")
            return redirect('/register')

        if not validate_email(email):
            flash("Некорректный email! Убедитесь, что он содержит '@' и домен.", "error")
            return redirect('/register')

        try:
            execute_query(
                "INSERT INTO users (username, password, name, surname, phone, email) VALUES (%s, %s, %s, %s, %s, %s)",
                (username, password, name, surname, phone, email)
            )
            flash("Регистрация успешна! Войдите в систему.", "success")
            return redirect('/login')
        except psycopg2.IntegrityError:
            flash("Пользователь уже существует или данные некорректны!", "error")
            return redirect('/register')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = execute_query("SELECT * FROM users WHERE username = %s", (username,), fetchone=True)

        if user and bcrypt.check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            return redirect('/dashboard')
        flash("Неверные учетные данные!", "error")
    return render_template('login.html')

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')  # Корректный возврат при отсутствии сессии

    # Получаем данные пользователя
    user = execute_query("SELECT * FROM users WHERE id = %s", (session['user_id'],), fetchone=True)

    if request.method == 'POST':
        try:
            pulse = int(request.form['pulse'])
            systolic = request.form['systolic']
            diastolic = request.form['diastolic']
            temperature = float(request.form['temperature'])
            sugar_level = float(request.form['sugar_level'])
            description = request.form['description']

            weight = user['weight']
            growth = user['growth']

            # Сохраняем данные
            execute_query(
                """
                INSERT INTO stats (user_id, pulse, systolic, diastolic, temperature, sugar_level, weight, growth, description)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (session['user_id'], pulse, systolic, diastolic, temperature, sugar_level, weight, growth, description)
            )
            flash("Данные успешно добавлены.", "success")
        except Exception as e:
            flash(f"Произошла ошибка при сохранении данных: {str(e)}", "error")

        return redirect(url_for('dashboard'))  # Возврат после обработки POST-запроса

    # Получаем данные для графика
    stats = execute_query("SELECT * FROM stats WHERE user_id = %s ORDER BY timestamp ASC", (session['user_id'],), fetchall=True)

    if not stats:
        flash("Нет данных для отображения графика.", "info")

    # Формируем графики
    try:
        timestamps = [stat['timestamp'] for stat in stats]  # Уже объекты datetime
        pulses = [stat['pulse'] for stat in stats]
        systolic = [stat['systolic'] for stat in stats]
        diastolic = [stat['diastolic'] for stat in stats]
        temperatures = [stat['temperature'] for stat in stats]
        sugar_levels = [stat['sugar_level'] for stat in stats]

        # Создаем графики Plotly
        graphs = []
        graphs = []
        graphs.append(go.Scatter(
            x=timestamps, y=pulses,
            mode='lines+markers',
            name='Пульс',
            line=dict(color='red')  # Красный цвет
        ))
        graphs.append(go.Scatter(
            x=timestamps, y=systolic,
            mode='lines+markers',
            name='Систолическое давление',
            line=dict(color='orange')  # Оранжевый цвет
        ))
        graphs.append(go.Scatter(
            x=timestamps, y=diastolic,
            mode='lines+markers',
            name='Диастолическое давление',
            line=dict(color='green')  # Зеленый цвет
        ))
        graphs.append(go.Scatter(
            x=timestamps, y=temperatures,
            mode='lines+markers',
            name='Температура',
            line=dict(color='purple')  # Фиолетовый цвет
        ))
        graphs.append(go.Scatter(
            x=timestamps, y=sugar_levels,
            mode='lines+markers',
            name='Уровень сахара',
            line=dict(color='brown')  # Коричневый цвет
        ))

        layout = go.Layout(
            title="Динамика показателей",
            xaxis=dict(title="Дата и время"),
            yaxis=dict(title="Значение"),
            plot_bgcolor="#f9f9f9",  # Светло-серый фон
            paper_bgcolor="#fff",
        )

        plot_html = pio.to_html(go.Figure(data=graphs, layout=layout), full_html=False)
    except Exception as e:
        plot_html = f"<p>Произошла ошибка при генерации графиков: {str(e)}</p>"


    return render_template('dashboard.html', stats=stats, user_name=user['name'], plot_html=plot_html)


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/home', methods=['GET', 'POST'])
def home():
    if 'user_id' not in session:
        return redirect('/login')

    if request.method == 'POST':
        new_weight = request.form['weight']
        new_growth = request.form['growth']

        try:
            execute_query(
                "UPDATE users SET weight = %s, growth = %s WHERE id = %s",
                (new_weight, new_growth, session['user_id'])
            )
            flash("Данные обновлены!", "success")
        except Exception:
            flash("Произошла ошибка при обновлении данных.", "error")

    user = execute_query("SELECT * FROM users WHERE id = %s", (session['user_id'],), fetchone=True)
    return render_template('home.html', user=user)

if __name__ == '__main__':
    app.run(debug=True)
