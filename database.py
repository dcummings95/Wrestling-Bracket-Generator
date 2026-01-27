import sqlite3
import json
from werkzeug.security import generate_password_hash, check_password_hash
from dataclasses import dataclass

DB_PATH = 'wrestling_app.db'

@dataclass
class User:
    id: int
    username: str
    password_hash: str

def init_db():
    """Create users and events tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            date TEXT NOT NULL,
            num_mats INTEGER NOT NULL,
            data TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
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


# Event storage functions

def save_event(event_id: str, user_id: int, name: str, date: str, num_mats: int, event_data: dict) -> bool:
    """Save an event to the database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute(
            'INSERT INTO events (id, user_id, name, date, num_mats, data) VALUES (?, ?, ?, ?, ?, ?)',
            (event_id, user_id, name, date, num_mats, json.dumps(event_data))
        )
        
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

def get_event(event_id: str, user_id: int) -> dict | None:
    """Get a single event by ID for a specific user."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        'SELECT id, user_id, name, date, num_mats, data FROM events WHERE id = ? AND user_id = ?',
        (event_id, user_id)
    )
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            'id': row[0],
            'user_id': row[1],
            'name': row[2],
            'date': row[3],
            'num_mats': row[4],
            'data': json.loads(row[5])
        }
    return None

def get_user_events(user_id: int) -> list[dict]:
    """Get all events for a user."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        'SELECT id, user_id, name, date, num_mats, data, created_at FROM events WHERE user_id = ? ORDER BY created_at DESC',
        (user_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    
    events = []
    for row in rows:
        events.append({
            'id': row[0],
            'user_id': row[1],
            'name': row[2],
            'date': row[3],
            'num_mats': row[4],
            'data': json.loads(row[5]),
            'created_at': row[6]
        })
    return events

def delete_event(event_id: str, user_id: int) -> bool:
    """Delete an event."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM events WHERE id = ? AND user_id = ?', (event_id, user_id))
    deleted = cursor.rowcount > 0
    
    conn.commit()
    conn.close()
    return deleted