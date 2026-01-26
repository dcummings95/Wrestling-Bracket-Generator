import os
import json
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from werkzeug.utils import secure_filename
from parser import parse_excel, parse_csv
from matcher import BracketMatcher
from models import Event

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

events_store = {}
wrestlers_store = {}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    return render_template('index.html', events=events_store.values())


@app.route('/upload', methods=['GET', 'POST'])
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
                
                session_id = os.urandom(8).hex()
                wrestlers_store[session_id] = wrestlers
                
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
def create_event(session_id):
    if session_id not in wrestlers_store:
        flash('Session expired. Please upload file again.', 'error')
        return redirect(url_for('upload'))
    
    wrestlers = wrestlers_store[session_id]
    
    if request.method == 'POST':
        event_name = request.form.get('event_name', 'Unnamed Event')
        event_date = request.form.get('event_date', '')
        num_mats = int(request.form.get('num_mats', 3))
        bracket_size = int(request.form.get('bracket_size', 4))
        
        matcher = BracketMatcher(wrestlers, bracket_size=bracket_size)
        brackets, unmatched = matcher.match_all(num_mats=num_mats)
        
        event_id = os.urandom(8).hex()
        event = Event(
            id=event_id,
            name=event_name,
            date=event_date,
            num_mats=num_mats,
            brackets=brackets,
            unmatched_wrestlers=unmatched
        )
        events_store[event_id] = event
        
        del wrestlers_store[session_id]
        
        return redirect(url_for('view_event', event_id=event_id))
    
    return render_template('create_event.html', 
                         session_id=session_id, 
                         wrestler_count=len(wrestlers),
                         wrestlers=wrestlers)


@app.route('/event/<event_id>')
def view_event(event_id):
    if event_id not in events_store:
        flash('Event not found', 'error')
        return redirect(url_for('index'))
    
    event = events_store[event_id]
    return render_template('event.html', event=event)


@app.route('/event/<event_id>/print')
def print_event(event_id):
    if event_id not in events_store:
        flash('Event not found', 'error')
        return redirect(url_for('index'))
    
    event = events_store[event_id]
    return render_template('print_brackets.html', event=event)


@app.route('/event/<event_id>/scoresheets')
def scoresheets(event_id):
    if event_id not in events_store:
        flash('Event not found', 'error')
        return redirect(url_for('index'))
    
    event = events_store[event_id]
    return render_template('scoresheets.html', event=event)


@app.route('/event/<event_id>/print-scoresheets')
def print_scoresheets(event_id):
    if event_id not in events_store:
        flash('Event not found', 'error')
        return redirect(url_for('index'))
    
    event = events_store[event_id]
    return render_template('print_scoresheets.html', event=event)


@app.route('/api/event/<event_id>')
def api_event(event_id):
    if event_id not in events_store:
        return jsonify({'error': 'Event not found'}), 404
    
    event = events_store[event_id]
    return jsonify(event.to_dict())


@app.route('/api/event/<event_id>/remove-wrestler', methods=['POST'])
def remove_wrestler(event_id):
    """Remove a wrestler from a bracket and move to unmatched."""
    if event_id not in events_store:
        return jsonify({'error': 'Event not found'}), 404
    
    data = request.get_json()
    bracket_id = data.get('bracket_id')
    wrestler_id = data.get('wrestler_id')
    
    event = events_store[event_id]
    
    # Find the bracket and wrestler
    bracket = next((b for b in event.brackets if b.id == bracket_id), None)
    if not bracket:
        return jsonify({'error': 'Bracket not found'}), 404
    
    wrestler = next((w for w in bracket.wrestlers if w.id == wrestler_id), None)
    if not wrestler:
        return jsonify({'error': 'Wrestler not found'}), 404
    
    # Remove from bracket and add to unmatched
    bracket.wrestlers.remove(wrestler)
    event.unmatched_wrestlers.append(wrestler)
    
    return jsonify({
        'success': True,
        'bracket': bracket.to_dict(),
        'unmatched_wrestlers': [w.to_dict() for w in event.unmatched_wrestlers]
    })


@app.route('/api/event/<event_id>/add-wrestler', methods=['POST'])
def add_wrestler(event_id):
    """Add an unmatched wrestler to a bracket."""
    if event_id not in events_store:
        return jsonify({'error': 'Event not found'}), 404
    
    data = request.get_json()
    bracket_id = data.get('bracket_id')
    wrestler_id = data.get('wrestler_id')
    
    event = events_store[event_id]
    
    # Find the bracket and wrestler
    bracket = next((b for b in event.brackets if b.id == bracket_id), None)
    if not bracket:
        return jsonify({'error': 'Bracket not found'}), 404
    
    wrestler = next((w for w in event.unmatched_wrestlers if w.id == wrestler_id), None)
    if not wrestler:
        return jsonify({'error': 'Wrestler not found'}), 404
    
    # Check if bracket is full
    if len(bracket.wrestlers) >= 4:
        return jsonify({'error': 'Bracket is full (max 4 wrestlers)'}), 400
    
    # Add to bracket and remove from unmatched
    bracket.wrestlers.append(wrestler)
    event.unmatched_wrestlers.remove(wrestler)
    
    return jsonify({
        'success': True,
        'bracket': bracket.to_dict(),
        'unmatched_wrestlers': [w.to_dict() for w in event.unmatched_wrestlers]
    })


if __name__ == '__main__':
    app.run(debug=True, port=5000)