"""
Standalone preview server for Letter Swap game.
Run with: python tmp/preview_server.py
"""
from flask import Flask, render_template
from flask_socketio import SocketIO
import random

app = Flask(__name__, template_folder='.', static_folder='.', static_url_path='')
app.config['SECRET_KEY'] = 'preview-secret'
socketio = SocketIO(app, cors_allowed_origins="*")

# Game state
game_state = {
    'target': '',
    'current_chars': [],
    'space_indices': [],  # Indices where spaces are (fixed positions)
    'is_running': False,
    'swap_interval': 2.5
}

def get_random_wrong_index():
    """Find a random index where current char doesn't match target (excluding spaces)"""
    wrong_indices = [
        i for i, c in enumerate(game_state['current_chars'])
        if i not in game_state['space_indices'] and c != game_state['target'][i]
    ]
    if not wrong_indices:
        return None
    return random.choice(wrong_indices)

def find_char_position(char, exclude_index):
    """Find where a specific character is currently located, excluding a given index"""
    chars = game_state['current_chars']
    for i, c in enumerate(chars):
        if i != exclude_index and i not in game_state['space_indices'] and c == char:
            return i
    return None

def perform_swap():
    """Pick a random wrong position and swap with the correct letter's current location"""
    # Find a random position that has the wrong letter
    idx_a = get_random_wrong_index()

    if idx_a is None:
        # All letters are in correct positions
        socketio.emit('game_complete', {'message': 'Word revealed!'})
        game_state['is_running'] = False
        return False

    # Find where the correct letter for this position currently is
    needed_char = game_state['target'][idx_a]
    idx_b = find_char_position(needed_char, idx_a)

    if idx_b is None:
        # This shouldn't happen if the puzzle is valid
        game_state['is_running'] = False
        return False

    # Swap in server state
    chars = game_state['current_chars']
    chars[idx_a], chars[idx_b] = chars[idx_b], chars[idx_a]

    # Emit swap instruction to display
    socketio.emit('swap', {
        'indexA': idx_a,
        'indexB': idx_b
    })
    return True

def game_loop():
    """Background task that triggers swaps at intervals"""
    while game_state['is_running']:
        socketio.sleep(game_state['swap_interval'])
        if game_state['is_running']:
            if not perform_swap():
                break

@app.route('/')
def index():
    return render_template('preview.html')

@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('start_game')
def handle_start_game(data):
    """Start a new game with the given target word"""
    target = data.get('target', 'JURASSIC PARK').upper()

    game_state['target'] = target

    # Find space positions (these stay fixed)
    game_state['space_indices'] = [i for i, c in enumerate(target) if c == ' ']

    # Extract only non-space characters and shuffle them
    non_space_chars = [c for c in target if c != ' ']
    random.shuffle(non_space_chars)

    # Build the display array with spaces in correct positions
    current_chars = []
    non_space_idx = 0
    for i, c in enumerate(target):
        if c == ' ':
            current_chars.append(' ')
        else:
            current_chars.append(non_space_chars[non_space_idx])
            non_space_idx += 1

    game_state['current_chars'] = current_chars
    game_state['is_running'] = True

    # Send initial state to display
    socketio.emit('init_display', {
        'chars': game_state['current_chars'],
        'length': len(target)
    })

    # Start background game loop using SocketIO's task system
    socketio.start_background_task(game_loop)

@socketio.on('stop_game')
def handle_stop_game():
    """Stop the current game"""
    game_state['is_running'] = False

@socketio.on('manual_swap')
def handle_manual_swap():
    """Trigger a single swap manually"""
    if game_state['current_chars']:
        perform_swap()

@socketio.on('reset_game')
def handle_reset_game(data):
    """Reset and start with a new word"""
    game_state['is_running'] = False
    socketio.sleep(0.1)  # Brief pause to stop loop
    handle_start_game(data)

if __name__ == '__main__':
    print("Starting Letter Swap Preview Server...")
    print("Open http://localhost:5001 in your browser")
    socketio.run(app, host='0.0.0.0', port=5001, debug=True)
