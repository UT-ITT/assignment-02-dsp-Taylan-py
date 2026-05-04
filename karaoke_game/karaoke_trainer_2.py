import numpy as np
import sounddevice as sd
import pyglet
from pyglet import shapes
from pyglet.window import key
from pyglet.media.synthesis import Sine
import time
import os
from collections import deque

# --- AUDIO SETTINGS ---
CHUNK = 2048          
CHANNELS = 1
RATE = 44100
VOLUME_THRESHOLD = 20000 * 10  # Adjusted slightly for sounddevice array scaling

# --- GLOBAL VARIABLES ---
current_pitch = None
current_fft_bins = np.zeros(128) 
pitch_history = deque(maxlen=5) 
active_players = []

# --- SOUNDDEVICE AUDIO CALLBACK ---
# This replaces the entire pyaudio threading setup
def audio_callback(indata, frames, time_info, status):
    global current_pitch, current_fft_bins
    
    if status:
        print(f"Audio Status: {status}")

    # indata is a 2D array, we want the first channel
    audio_data = indata[:, 0]
    
    # Apply window and FFT
    windowed = audio_data * np.hanning(len(audio_data))
    fft_data = np.fft.rfft(windowed)
    fft_magnitude = np.abs(fft_data)
    
    # Scale bins for Pyglet visualizer
    current_fft_bins = (fft_magnitude[:128] / 400.0)
    
    if np.max(fft_magnitude) > VOLUME_THRESHOLD:
        peak_idx = np.argmax(fft_magnitude)
        freqs = np.fft.rfftfreq(CHUNK, 1.0 / RATE)
        dominant_freq = freqs[peak_idx]
        
        # Clamp frequency between 60Hz and 1000Hz 
        if 60 < dominant_freq < 1000: 
            raw_pitch = 69 + 12 * np.log2(dominant_freq / 440.0)
            pitch_history.append(raw_pitch)
            current_pitch = np.median(pitch_history)
        else:
            pitch_history.clear()
            current_pitch = None
    else:
        pitch_history.clear()
        current_pitch = None

# Open low-latency audio stream in the background
# We use dtype='int16' so your original volume threshold logic still works!
stream = sd.InputStream(
    channels=CHANNELS,
    samplerate=RATE,
    blocksize=CHUNK,
    callback=audio_callback,
    dtype='int16',
    latency='low'
)
stream.start()

# --- UTILITY FUNCTIONS ---
def get_note_name(midi_note):
    notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    octave = (int(midi_note) // 12) - 1
    note_index = int(midi_note) % 12
    return f"{notes[note_index]}{octave}"

def load_highscore():
    if os.path.exists("highscore.txt"):
        try:
            with open("highscore.txt", "r") as f:
                return float(f.read())
        except:
            pass
    return float('inf')

def save_highscore(score):
    with open("highscore.txt", "w") as f:
        f.write(f"{score:.2f}")

# --- GAME SETTINGS & DATA ---
WINDOW_WIDTH = 1024
WINDOW_HEIGHT = 768

practice_notes = [60, 62, 64, 65, 67, 60, 69, 67, 65, 62, 71, 72, 67, 64, 60]
current_target_idx = 0
match_progress = 0.0     
REQUIRED_HOLD_TIME = 0.8 

game_state = "START" 
state_timer = 0.0
start_time = 0.0
elapsed_time = 0.0
best_time = load_highscore()

# --- PYGLET WINDOW & GRAPHICS ---
window = pyglet.window.Window(WINDOW_WIDTH, WINDOW_HEIGHT, "Vocal Pitch Trainer", resizable=True)
pyglet.gl.glClearColor(0.08, 0.08, 0.12, 1.0) 
batch = pyglet.graphics.Batch()

# UI Elements
status_label = pyglet.text.Label("Get Ready!", font_name='Segoe UI', font_size=40, anchor_x='center', color=(0, 255, 204, 255), batch=batch)
note_label = pyglet.text.Label("", font_name='Segoe UI', font_size=60, anchor_x='center', color=(255, 255, 255, 255), batch=batch)
instructions_label = pyglet.text.Label("Press SPACE to replay | Press F for Fullscreen", font_name='Segoe UI', font_size=14, anchor_x='center', color=(150, 150, 180, 255), batch=batch)
progress_label = pyglet.text.Label("Progress: 0/15", font_name='Segoe UI', font_size=20, x=30, color=(200, 200, 255, 255), batch=batch)
timer_label = pyglet.text.Label("Time: 0.00s", font_name='Segoe UI', font_size=20, anchor_x='right', color=(255, 204, 0, 255), batch=batch)

hs_text = "None" if best_time == float('inf') else f"{best_time:.2f}s"
highscore_label = pyglet.text.Label(f"Best: {hs_text}", font_name='Segoe UI', font_size=16, anchor_x='right', color=(100, 255, 100, 255), batch=batch)

# FFT Bars & UI Shapes
fft_bars = [shapes.Line(x=0, y=0, x2=0, y2=0, thickness=3, color=(0, 153, 255), batch=batch) for _ in range(128)]
fft_labels = [(pyglet.text.Label(f"{freq}Hz", font_name='Segoe UI', font_size=10, color=(150, 150, 180, 255), anchor_x='center', batch=batch), int(freq * CHUNK / RATE)) for freq in [0, 500, 1000, 2000]]

target_box_bg = shapes.Rectangle(x=0, y=0, width=300, height=40, color=(40, 40, 60), batch=batch)
target_box = shapes.Rectangle(x=0, y=0, width=300, height=40, color=(100, 100, 120), batch=batch)
target_box.opacity = 150 
fill_bar = shapes.Rectangle(x=0, y=0, width=0, height=40, color=(0, 255, 204), batch=batch)
player_marker = shapes.Circle(x=0, y=0, radius=12, color=(255, 0, 102), batch=batch)
player_marker.visible = False

def note_to_y(note):
    return (window.height // 2 - 50) + (note - 50) * 15

# --- AUDIO SYNTHESIS ---
def play_current_target():
    global active_players
    if current_target_idx < len(practice_notes):
        target_note = practice_notes[current_target_idx]
        freq = 440.0 * (2.0 ** ((target_note - 69) / 12.0))
        try:
            active_players = [p for p in active_players if p.playing]
            player = Sine(duration=1.5, frequency=freq).play()
            active_players.append(player) 
        except Exception as e:
            print(f"Synth error: {e}")

# --- INPUT HANDLING ---
@window.event
def on_key_press(symbol, modifiers):
    global best_time
    if symbol == key.SPACE and game_state == "SING":
        play_current_target()
    elif symbol == key.F:
        window.set_fullscreen(not window.fullscreen)
    elif symbol == key.R and game_state == "GAMEOVER":
        best_time = float('inf')
        save_highscore(best_time)
        highscore_label.text = "Best: None"

# --- GAME LOOP ---
def update(dt):
    global current_target_idx, match_progress, game_state, state_timer, start_time, elapsed_time, best_time
    
    center_x = window.width // 2
    status_label.x, status_label.y = center_x, window.height - 80
    note_label.x, note_label.y = center_x, window.height - 160
    instructions_label.x, instructions_label.y = center_x, 40
    progress_label.y = window.height - 40
    timer_label.x, timer_label.y = window.width - 30, window.height - 40
    highscore_label.x, highscore_label.y = window.width - 30, window.height - 70
    
    target_box_bg.x = target_box.x = fill_bar.x = center_x - 150
    player_marker.x = center_x
    
    bar_spacing = window.width / 128
    for lbl, bin_idx in fft_labels:
        lbl.x, lbl.y = bin_idx * bar_spacing, 5  
        
    for i, bar in enumerate(fft_bars):
        target_height = min(current_fft_bins[i] * 1.5, 200) 
        bar.x = bar.x2 = int(i * bar_spacing)
        bar.y, bar.y2 = 25, 25 + target_height
        bar.color = (255, 0, 102) if current_pitch is not None and np.argmax(current_fft_bins) == i else (0, 153, 255) 

    if game_state in ["LISTEN", "SING"] and start_time > 0:
        elapsed_time = time.time() - start_time
        timer_label.text = f"Time: {elapsed_time:.2f}s"

    if current_target_idx >= len(practice_notes):
        if game_state != "GAMEOVER":
            game_state = "GAMEOVER"
            status_label.text, status_label.color = "TRAINING COMPLETE!", (0, 255, 204, 255)
            if elapsed_time < best_time:
                best_time = elapsed_time
                save_highscore(best_time)
                note_label.text, note_label.color = "NEW RECORD!", (255, 204, 0, 255)
            else:
                note_label.text = f"Final Time: {elapsed_time:.2f}s"
            instructions_label.text = "Press ESC to Exit | Press R to Reset Highscore"
            instructions_label.visible = True
            target_box.visible = target_box_bg.visible = fill_bar.visible = player_marker.visible = False
        return

    target_note = practice_notes[current_target_idx]
    target_box.y = target_box_bg.y = fill_bar.y = note_to_y(target_note) - 20
    progress_label.text = f"Progress: {current_target_idx}/{len(practice_notes)}"

    if game_state == "START":
        state_timer += dt
        if state_timer > 1.0: 
            start_time, game_state, state_timer = time.time(), "LISTEN", 0.0
            play_current_target()
            
    elif game_state == "LISTEN":
        status_label.text, status_label.color = "LISTEN...", (0, 153, 255, 255)
        note_label.text, note_label.color = get_note_name(target_note), (255, 255, 255, 255)
        instructions_label.visible, target_box.color, player_marker.visible, fill_bar.width = False, (100, 100, 120), False, 0
        state_timer += dt
        if state_timer >= 1.5:
            game_state, state_timer = "SING", 0.0
            
    elif game_state == "SING":
        status_label.text, status_label.color = "MATCH THE PITCH", (255, 204, 0, 255)
        instructions_label.visible = True
        
        if current_pitch is not None:
            target_y = note_to_y(current_pitch)
            player_marker.y += (target_y - player_marker.y) * 0.3 
            player_marker.visible = True
            
            if abs(current_pitch - target_note) <= 1.0:
                target_box.color = (255, 204, 0) 
                match_progress += dt 
                if match_progress >= REQUIRED_HOLD_TIME:
                    current_target_idx, match_progress, game_state, state_timer = current_target_idx + 1, 0.0, "LISTEN", 0.0
                    play_current_target() 
            else:
                target_box.color, match_progress = (100, 100, 120), max(0, match_progress - dt * 2)
        else:
            player_marker.visible, target_box.color, match_progress = False, (100, 100, 120), max(0, match_progress - dt * 2)

        fill_bar.width = 300 * (match_progress / REQUIRED_HOLD_TIME)

@window.event
def on_draw():
    window.clear()
    batch.draw()

@window.event
def on_close():
    stream.stop()
    stream.close()

pyglet.clock.schedule_interval(update, 1/60.0)
pyglet.app.run()