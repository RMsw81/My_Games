import re
import os
import base64
import mimetypes
from flask import Flask, jsonify, render_template, redirect, url_for, request, flash, send_from_directory
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import pymysql.cursors
import datetime
import json

# Aggiungi il MIME type per i file .wasm
mimetypes.add_type('application/wasm', '.wasm')

# Genera una chiave segreta casuale di 24 byte
secret_key = base64.urlsafe_b64encode(os.urandom(24)).decode('utf-8')

app = Flask(__name__)
app.config['SECRET_KEY'] = secret_key

# Leggi le variabili d'ambiente
db_host = 'RobertaMerlo.mysql.pythonanywhere-services.com'
db_user = 'RobertaMerlo'
db_password = 'Y9puX%40a8'
db_name = 'RobertaMerlo$db'

# Crea la connessione al database
def get_db_connection():
    try:
        return pymysql.connect(
            host=db_host,
            user=db_user,
            password=db_password,
            database=db_name,
            port=3306,  # porta predefinita
            cursorclass=pymysql.cursors.DictCursor
        )
    except pymysql.MySQLError as e:
        print(f"Errore nella connessione al database: {e}")
        return None

# Inizializza Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# UserMixin e User
class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    connection = get_db_connection()
    if connection is None:
        return None  # Gestione dell'errore di connessione
    try:
        with connection.cursor() as cursor:
            sql = 'SELECT * FROM user WHERE id = %s'
            cursor.execute(sql, (user_id,))
            user = cursor.fetchone()
            if user:
                return User(user['id'], user['username'])
    except pymysql.MySQLError as e:
        print(f"Errore nel caricamento dell'utente: {e}")
    finally:
        connection.close()
    return None

# Funzione per creare il database e la tabella
def create_database_and_table():
    connection = pymysql.connect(
        host=db_host,
        user=db_user,
        password=db_password
    )
    try:
        with connection.cursor() as cursor:
            # Crea il database, se non esiste
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
            connection.commit()

        # Connettiti al database appena creato
        connection.select_db(db_name)

        # Crea la tabella degli utenti, se non esiste
        with connection.cursor() as cursor:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(255) NOT NULL UNIQUE,
                    password VARCHAR(510) NOT NULL
                )
            ''')
            connection.commit()
    except pymysql.MySQLError as e:
        print(f"Errore nella creazione del database o della tabella: {e}")
    finally:
        connection.close()

# Esegui la creazione del database e della tabella prima di avviare l'app
create_database_and_table()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start_p', methods=['GET'])
@login_required
def start_p():
    # Definisci il percorso del file HTML
    index_path = os.path.join(app.root_path, 'p/build/web/index.html')

    # Controlla se il file esiste
    if not os.path.isfile(index_path):
        return jsonify({'error': 'File non trovato', 'path': index_path}), 404

    # Se il file esiste, invialo come risposta
    return send_from_directory('p/build/web', 'index.html')

@app.route('/p.apk')
@login_required
def serve_apk():
    return send_from_directory('/home/RobertaMerlo/My_Games/p/build/web', 'p.apk')

@app.route('/assets/games/<path:filename>')
@login_required
def serve_game_assets(filename):
    assets_directory = os.path.join(app.root_path, 'p/build/web/assets/games')
    return send_from_directory(assets_directory, filename)

def validate_password(password):
    """Verifica se la password soddisfa i criteri richiesti."""
    if len(password) < 8:
        return False
    if not re.search(r'[A-Z]', password):
        return False
    if not re.search(r'[0-9]', password):
        return False
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False
    return True

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        # Verifica che tutti i campi siano compilati
        if not username or not password or not confirm_password:
            flash('Tutti i campi sono richiesti', 'danger')
            return redirect(url_for('register'))

        # Verifica che l'username sia una email valida
        if not re.match(r"[^@]+@[^@]+\.[^@]+", username):
            flash('L\'username deve essere un\'email valida.', 'danger')
            return redirect(url_for('register'))

        # Verifica la validità della password
        if not validate_password(password):
            flash('La password deve contenere almeno 8 caratteri, una lettera maiuscola, un numero e un carattere speciale.', 'danger')
            return redirect(url_for('register'))

        # Verifica se la password e la conferma password corrispondono
        if password != confirm_password:
            flash('Le password non corrispondono.', 'danger')
            return redirect(url_for('register'))

        connection = get_db_connection()
        if connection is None:
            flash('Errore nella connessione al database', 'danger')
            return redirect(url_for('register'))

        try:
            with connection.cursor() as cursor:
                sql = 'SELECT * FROM user WHERE username = %s'
                cursor.execute(sql, (username,))
                user = cursor.fetchone()

                if user:
                    flash('Username già esistente. Per favore scegli un nome diverso.', 'danger')
                    return redirect(url_for('register'))

                hashed_password = generate_password_hash(password)
                sql = 'INSERT INTO user (username, password) VALUES (%s, %s)'
                cursor.execute(sql, (username, hashed_password))
                connection.commit()
                flash('Registrazione avvenuta con successo! Per favore effettua il login.', 'success')

                return redirect(url_for('login'))
        except pymysql.MySQLError as e:
            flash(f'Errore durante la registrazione: {e}', 'danger')
            print(f"Errore durante la registrazione: {e}")
        finally:
            connection.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        connection = get_db_connection()
        if connection is None:
            flash('Errore nella connessione al database', 'danger')
            return redirect(url_for('login'))

        try:
            with connection.cursor() as cursor:
                sql = 'SELECT * FROM user WHERE username = %s'
                cursor.execute(sql, (username,))
                user = cursor.fetchone()

                if user and check_password_hash(user['password'], password):
                    user_obj = User(user['id'], user['username'])
                    login_user(user_obj)
                    return redirect(url_for('index'))
                else:
                    flash('Accesso fallito. Controlla username e/o password', 'danger')
        except pymysql.MySQLError as e:
            flash(f'Errore durante il login: {e}', 'danger')
            print(f"Errore nel database durante il login: {e}")
        finally:
            connection.close()
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))
    
# Rotta per la pagina del Puzzle Game (download_p.html)
@app.route('/down_p')
def down_p():
    return render_template('download_p.html')

# Rotta per la pagina del Memory Game (download_m.html)
@app.route('/down_m')
def down_m():
    return render_template('download_m.html')
# Nuova route per servire i file .wasm
@app.route('/<path:filename>')
@login_required
def serve_file(filename):
    return send_from_directory('p/build/web', filename)

@app.route('/user', methods=['GET'])
@login_required
def get_user():
    """Restituisce il nome dell'utente loggato."""
    return jsonify({'username': current_user.username})

if __name__ == '__main__':
    app.run(debug=True)
