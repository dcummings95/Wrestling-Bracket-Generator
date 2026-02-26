import os
import json
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from parser import parse_excel, parse_csv
from bracket_matcher import BracketMatcher
from models import Event, Bracket
from database import (
    init_db, create_user, get_user_by_username, get_user_by_id, verify_password,
    save_event, update_event, get_event, get_user_events, delete_event
)
import secrets
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

app.secret_key = os.getenv('SECRET_KEY')
if not app.secret_key:
    raise ValueError("SECRET_KEY must be set in .env file. Run: python -c \"import secrets; print(secrets.token_hex(32))\" to generate one")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = None 

init_db()

wrestlers_store = {}


class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username


@login_manager.user_loader
def load_user(user_id):
    db_user = get_user_by_id(int(user_id))
    if db_user:
        return User(db_user.id, db_user.username)
    return None


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def cleanup_old_sessions():
    """Remove session data older than 1 hour to prevent memory leaks."""
    cutoff = datetime.now() - timedelta(hours=1)
    to_delete = [sid for sid, data in wrestlers_store.items() 
                 if data.get('timestamp', datetime.now()) < cutoff]
    for sid in to_delete:
        del wrestlers_store[sid]


@app.errorhandler(404)
def not_found(e):
    flash('Page not found', 'error')
    return redirect(url_for('index'))


@app.errorhandler(500)
def server_error(e):
    flash('An unexpected error occurred. Please try again.', 'error')
    return redirect(url_for('index'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        db_user = get_user_by_username(username)
        
        if db_user and verify_password(db_user, password):
            user = User(db_user.id, db_user.username)
            login_user(user)
            flash('Logged in successfully', 'success')
            
            next_page = request.args.get('next')
            return redirect(next_page if next_page else url_for('index'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully', 'success')
    return redirect(url_for('login'))


@app.route('/')
@login_required
def index():
    events_data = get_user_events(current_user.id)
    events = [Event.from_dict(e['data']) for e in events_data]
    return render_template('index.html', events=events)


@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            try:
                if filename.endswith('.csv'):
                    wrestlers = parse_csv(filepath)
                else:
                    wrestlers = parse_excel(filepath)
                
                cleanup_old_sessions()
                
                session_id = os.urandom(8).hex()
                wrestlers_store[session_id] = {
                    'wrestlers': wrestlers,
                    'timestamp': datetime.now()
                }
                
                flash(f'Successfully loaded {len(wrestlers)} wrestlers', 'success')
                return redirect(url_for('create_event', session_id=session_id))
            
            except ValueError as e:
                flash(f'Error parsing file: {e}', 'error')
                return redirect(request.url)
            except Exception as e:
                flash(f'Unexpected error: {e}', 'error')
                return redirect(request.url)
            finally:
                if os.path.exists(filepath):
                    os.remove(filepath)
        else:
            flash('Invalid file type. Please upload .xlsx, .xls, or .csv', 'error')
            return redirect(request.url)
    
    return render_template('upload.html')


@app.route('/create-event/<session_id>', methods=['GET', 'POST'])
@login_required
def create_event(session_id):
    if session_id not in wrestlers_store:
        flash('Session expired. Please upload file again.', 'error')
        return redirect(url_for('upload'))
    
    wrestlers = wrestlers_store[session_id]['wrestlers']
    
    if request.method == 'POST':
        event_name = request.form.get('event_name', 'Unnamed Event')
        event_date = request.form.get('event_date', '')
        num_mats = min(int(request.form.get('num_mats', 3)), 4)
        bracket_size = int(request.form.get('bracket_size', 4))
        
        matcher = BracketMatcher(wrestlers, bracket_size=bracket_size)
        brackets, unmatched = matcher.match_all(num_mats=num_mats)
        
        event_id = os.urandom(8).hex()
        event = Event(
            id=event_id,
            name=event_name,
            date=event_date,
            num_mats=num_mats,
            bracket_size=bracket_size,
            brackets=brackets,
            unmatched_wrestlers=unmatched
        )
        
        if save_event(event_id, current_user.id, event_name, event_date, num_mats, event.to_dict()):
            del wrestlers_store[session_id]
            flash('Event created successfully', 'success')
            return redirect(url_for('view_event', event_id=event_id))
        else:
            flash('Error saving event', 'error')
            return redirect(url_for('upload'))
    
    return render_template('create_event.html', 
                         session_id=session_id, 
                         wrestler_count=len(wrestlers),
                         wrestlers=wrestlers)


@app.route('/event/<event_id>')
@login_required
def view_event(event_id):
    event_data = get_event(event_id, current_user.id)
    
    if not event_data:
        flash('Event not found', 'error')
        return redirect(url_for('index'))
    
    event = Event.from_dict(event_data['data'])
    return render_template('event.html', event=event)


@app.route('/event/<event_id>/delete', methods=['POST'])
@login_required
def delete_event_route(event_id):
    if delete_event(event_id, current_user.id):
        flash('Event deleted successfully', 'success')
    else:
        flash('Event not found', 'error')
    
    return redirect(url_for('index'))


@app.route('/event/<event_id>/print')
@login_required
def print_event(event_id):
    event_data = get_event(event_id, current_user.id)
    
    if not event_data:
        flash('Event not found', 'error')
        return redirect(url_for('index'))
    
    event = Event.from_dict(event_data['data'])
    return render_template('print_brackets.html', event=event)


@app.route('/event/<event_id>/scoresheets')
@login_required
def scoresheets(event_id):
    event_data = get_event(event_id, current_user.id)
    
    if not event_data:
        flash('Event not found', 'error')
        return redirect(url_for('index'))
    
    event = Event.from_dict(event_data['data'])
    return render_template('scoresheets.html', event=event)


@app.route('/event/<event_id>/print-scoresheets')
@login_required
def print_scoresheets(event_id):
    event_data = get_event(event_id, current_user.id)
    
    if not event_data:
        flash('Event not found', 'error')
        return redirect(url_for('index'))
    
    event = Event.from_dict(event_data['data'])
    return render_template('print_scoresheets.html', event=event)


@app.route('/api/event/<event_id>')
@login_required
def api_event(event_id):
    event_data = get_event(event_id, current_user.id)
    
    if not event_data:
        return jsonify({'error': 'Event not found'}), 404
    
    return jsonify(event_data['data'])


@app.route('/api/event/<event_id>/remove-wrestler', methods=['POST'])
@login_required
def remove_wrestler(event_id):
    event_data = get_event(event_id, current_user.id)
    
    if not event_data:
        return jsonify({'error': 'Event not found'}), 404
    
    event = Event.from_dict(event_data['data'])
    
    data = request.get_json()
    bracket_id = data.get('bracket_id')
    wrestler_id = data.get('wrestler_id')
    
    bracket = next((b for b in event.brackets if b.id == bracket_id), None)
    if not bracket:
        return jsonify({'error': 'Bracket not found'}), 404
    
    wrestler = next((w for w in bracket.wrestlers if w.id == wrestler_id), None)
    if not wrestler:
        return jsonify({'error': 'Wrestler not found'}), 404
    
    bracket.wrestlers.remove(wrestler)
    event.unmatched_wrestlers.append(wrestler)
    
    if update_event(event_id, current_user.id, event.name, event.date, event.num_mats, event.to_dict()):
        return jsonify({
            'success': True,
            'bracket': bracket.to_dict(),
            'unmatched_wrestlers': [w.to_dict() for w in event.unmatched_wrestlers]
        })
    else:
        return jsonify({'error': 'Failed to update event'}), 500


@app.route('/api/event/<event_id>/add-wrestler', methods=['POST'])
@login_required
def add_wrestler(event_id):
    event_data = get_event(event_id, current_user.id)
    
    if not event_data:
        return jsonify({'error': 'Event not found'}), 404
    
    event = Event.from_dict(event_data['data'])
    
    data = request.get_json()
    bracket_id = data.get('bracket_id')
    wrestler_id = data.get('wrestler_id')
    
    bracket = next((b for b in event.brackets if b.id == bracket_id), None)
    if not bracket:
        return jsonify({'error': 'Bracket not found'}), 404
    
    wrestler = next((w for w in event.unmatched_wrestlers if w.id == wrestler_id), None)
    if not wrestler:
        return jsonify({'error': 'Wrestler not found'}), 404
    
    if len(bracket.wrestlers) >= event.bracket_size:
        return jsonify({'error': f'Bracket is full (max {event.bracket_size} wrestlers)'}), 400
    
    bracket.wrestlers.append(wrestler)
    event.unmatched_wrestlers.remove(wrestler)
    
    if update_event(event_id, current_user.id, event.name, event.date, event.num_mats, event.to_dict()):
        return jsonify({
            'success': True,
            'bracket': bracket.to_dict(),
            'unmatched_wrestlers': [w.to_dict() for w in event.unmatched_wrestlers]
        })
    else:
        return jsonify({'error': 'Failed to update event'}), 500


@app.route('/api/event/<event_id>/delete-bracket', methods=['POST'])
@login_required
def delete_bracket(event_id):
    event_data = get_event(event_id, current_user.id)

    if not event_data:
        return jsonify({'error': 'Event not found'}), 404

    event = Event.from_dict(event_data['data'])

    data = request.get_json()
    bracket_id = data.get('bracket_id')

    bracket = next((b for b in event.brackets if b.id == bracket_id), None)
    if not bracket:
        return jsonify({'error': 'Bracket not found'}), 404

    event.unmatched_wrestlers.extend(bracket.wrestlers)
    event.brackets.remove(bracket)

    if update_event(event_id, current_user.id, event.name, event.date, event.num_mats, event.to_dict()):
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Failed to update event'}), 500


@app.route('/api/event/<event_id>/create-bracket', methods=['POST'])
@login_required
def create_bracket(event_id):
    event_data = get_event(event_id, current_user.id)

    if not event_data:
        return jsonify({'error': 'Event not found'}), 404

    event = Event.from_dict(event_data['data'])

    next_id = max((b.id for b in event.brackets), default=-1) + 1
    bracket = Bracket(id=next_id, wrestlers=[], mat_number=1)
    event.brackets.append(bracket)

    if update_event(event_id, current_user.id, event.name, event.date, event.num_mats, event.to_dict()):
        return jsonify({'success': True, 'bracket': bracket.to_dict()})
    else:
        return jsonify({'error': 'Failed to update event'}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
