import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from dataclasses import dataclass

DB_PATH = 'wrestling_app.db'

@dataclass
class User:
    id: int
    username: str
    password_hash: str

def init_db():
    """Create users table if it doesn't exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()

def create_user(username: str, password: str) -> bool:
    """Create a new user. Returns True if successful."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        password_hash = generate_password_hash(password)
        cursor.execute(
            'INSERT INTO users (username, password_hash) VALUES (?, ?)',
            (username, password_hash)
        )
        
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

def get_user_by_username(username: str) -> User | None:
    """Get user by username."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT id, username, password_hash FROM users WHERE username = ?', (username,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return User(id=row[0], username=row[1], password_hash=row[2])
    return None

def get_user_by_id(user_id: int) -> User | None:
    """Get user by ID."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT id, username, password_hash FROM users WHERE id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return User(id=row[0], username=row[1], password_hash=row[2])
    return None

def verify_password(user: User, password: str) -> bool:
    """Check if password matches user's hash."""
    return check_password_hash(user.password_hash, password)