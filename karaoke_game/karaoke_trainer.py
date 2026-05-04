import threading
import numpy as np
import pyaudio
import pyglet
from pyglet import shapes
from pyglet.window import key
from pyglet.media.synthesis import Sine
import time
import os
from collections import deque

# --- AUDIO SETTINGS ---
CHUNK = 2048          
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
VOLUME_THRESHOLD = 20000

# --- GLOBAL VARIABLES ---
current_pitch = None
is_running = True
current_fft_bins = np.zeros(128) 

# A buffer to hold the last 5 pitch readings (Stops the red dot from jittering)
pitch_history = deque(maxlen=5) 

# Keeps synth players alive so Python's garbage collector doesn't mute them
active_players = []

# --- AUDIO PROCESSING THREAD ---
def audio_listener():
    global current_pitch, is_running, current_fft_bins
    p = pyaudio.PyAudio()
    try:
        # Add input_device_index=2 right here!
        stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, 
                        input=True, input_device_index=2, frames_per_buffer=CHUNK)
    except Exception as e:
        print(f"Error opening audio stream: {e}")
        return

    while is_running:
        try:
            # Prevent blocking indefinitely and crashing on underflow
            if stream.get_read_available() >= CHUNK:
                data = stream.read(CHUNK, exception_on_overflow=False)
                audio_data = np.frombuffer(data, dtype=np.int16)
                
                windowed = audio_data * np.hanning(len(audio_data))
                fft_data = np.fft.rfft(windowed)
                fft_magnitude = np.abs(fft_data)
                
                current_fft_bins = fft_magnitude[:128] / 400.0
                
                if np.max(fft_magnitude) > VOLUME_THRESHOLD:
                    peak_idx = np.argmax(fft_magnitude)
                    freqs = np.fft.rfftfreq(CHUNK, 1.0 / RATE)
                    dominant_freq = freqs[peak_idx]
                    
                    # Clamp frequency between 60Hz and 1000Hz to ignore background hiss/rumble
                    if 60 < dominant_freq < 1000: 
                        raw_pitch = 69 + 12 * np.log2(dominant_freq / 440.0)
                        pitch_history.append(raw_pitch)
                        
                        # Take the median of the last 5 readings to smooth out voice harmonics
                        current_pitch = np.median(pitch_history)
                    else:
                        pitch_history.clear()
                        current_pitch = None
                else:
                    pitch_history.clear()
                    current_pitch = None
            else:
                time.sleep(0.01) # Give the CPU a break if no audio is ready
        except Exception as e:
            print(f"Audio thread error: {e}")
            pass 

    stream.stop_stream()
    stream.close()
    p.terminate()

audio_thread = threading.Thread(target=audio_listener, daemon=True)
audio_thread.start()

# --- UTILITY FUNCTIONS ---
def get_note_name(midi_note):
    notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    octave = (midi_note // 12) - 1
    note_index = midi_note % 12
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

# Time Tracking
start_time = 0.0
elapsed_time = 0.0
best_time = load_highscore()

# --- PYGLET WINDOW & GRAPHICS ---
window = pyglet.window.Window(WINDOW_WIDTH, WINDOW_HEIGHT, "Vocal Pitch Trainer", resizable=True)
pyglet.gl.glClearColor(0.08, 0.08, 0.12, 1.0) 
batch = pyglet.graphics.Batch()

# UI Elements
status_label = pyglet.text.Label("Get Ready!", font_name='Segoe UI', font_size=40,
                                 anchor_x='center', color=(0, 255, 204, 255), batch=batch)

note_label = pyglet.text.Label("", font_name='Segoe UI', font_size=60,
                                anchor_x='center', color=(255, 255, 255, 255), batch=batch)

instructions_label = pyglet.text.Label("Press SPACE to replay | Press F for Fullscreen", font_name='Segoe UI', font_size=14,
                                anchor_x='center', color=(150, 150, 180, 255), batch=batch)

progress_label = pyglet.text.Label("Progress: 0/15", font_name='Segoe UI', font_size=20,
                                   x=30, color=(200, 200, 255, 255), batch=batch)

timer_label = pyglet.text.Label("Time: 0.00s", font_name='Segoe UI', font_size=20,
                                   anchor_x='right', color=(255, 204, 0, 255), batch=batch)

hs_text = "None" if best_time == float('inf') else f"{best_time:.2f}s"
highscore_label = pyglet.text.Label(f"Best: {hs_text}", font_name='Segoe UI', font_size=16,
                                   anchor_x='right', color=(100, 255, 100, 255), batch=batch)

# FFT Bars
fft_bars = []
for i in range(128):
    bar = shapes.Line(x=0, y=0, x2=0, y2=0, thickness=3, 
                      color=(0, 153, 255), batch=batch)
    fft_bars.append(bar)

# FFT Axis Labels
fft_labels = []
for freq in [0, 500, 1000, 2000]:
    lbl = pyglet.text.Label(f"{freq}Hz", font_name='Segoe UI', font_size=10,
                            color=(150, 150, 180, 255), anchor_x='center', batch=batch)
    bin_idx = int(freq * CHUNK / RATE)
    fft_labels.append((lbl, bin_idx))

def note_to_y(note):
    base_note = 50
    return (window.height // 2 - 50) + (note - base_note) * 15

# UI Shapes
target_box_bg = shapes.Rectangle(x=0, y=0, width=300, height=40, color=(40, 40, 60), batch=batch)
target_box = shapes.Rectangle(x=0, y=0, width=300, height=40, color=(100, 100, 120), batch=batch)
target_box.opacity = 150 

fill_bar = shapes.Rectangle(x=0, y=0, width=0, height=40, color=(0, 255, 204), batch=batch)

player_marker = shapes.Circle(x=0, y=0, radius=12, color=(255, 0, 102), batch=batch)
player_marker.visible = False

# --- AUDIO SYNTHESIS ---
def play_current_target():
    global active_players
    if current_target_idx < len(practice_notes):
        target_note = practice_notes[current_target_idx]
        freq = 440.0 * (2.0 ** ((target_note - 69) / 12.0))
        try:
            # Clean up old finished players
            active_players = [p for p in active_players if p.playing]
            
            tone = Sine(duration=1.5, frequency=freq)
            player = tone.play()
            active_players.append(player) # Keep reference alive
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
    
    # --- DYNAMIC LAYOUT ---
    center_x = window.width // 2
    
    status_label.x = center_x
    status_label.y = window.height - 80
    note_label.x = center_x
    note_label.y = window.height - 160
    instructions_label.x = center_x
    instructions_label.y = 40
    
    progress_label.y = window.height - 40
    timer_label.x = window.width - 30
    timer_label.y = window.height - 40
    highscore_label.x = window.width - 30
    highscore_label.y = window.height - 70

    target_box_bg.x = center_x - 150
    target_box.x = center_x - 150
    fill_bar.x = center_x - 150
    player_marker.x = center_x
    
    # Update FFT Visualizer
    bar_spacing = window.width / 128
    
    for lbl, bin_idx in fft_labels:
        lbl.x = bin_idx * bar_spacing
        lbl.y = 5  
        
    for i, bar in enumerate(fft_bars):
        target_height = min(current_fft_bins[i] * 1.5, 200) 
        bar.x = bar.x2 = int(i * bar_spacing)
        bar.y = 25  
        bar.y2 = 25 + target_height
        
        if current_pitch is not None and np.argmax(current_fft_bins) == i:
            bar.color = (255, 0, 102) 
        else:
            bar.color = (0, 153, 255) 

    # --- TIMER LOGIC ---
    if game_state in ["LISTEN", "SING"] and start_time > 0:
        elapsed_time = time.time() - start_time
        timer_label.text = f"Time: {elapsed_time:.2f}s"

    # --- WIN STATE ---
    if current_target_idx >= len(practice_notes):
        if game_state != "GAMEOVER":
            game_state = "GAMEOVER"
            status_label.text = "TRAINING COMPLETE!"
            status_label.color = (0, 255, 204, 255)
            
            if elapsed_time < best_time:
                best_time = elapsed_time
                save_highscore(best_time)
                note_label.color = (255, 204, 0, 255)
                note_label.text = "NEW RECORD!"
            else:
                note_label.text = f"Final Time: {elapsed_time:.2f}s"
                
            instructions_label.text = "Press ESC to Exit | Press R to Reset Highscore"
            instructions_label.visible = True
            target_box.visible = False
            target_box_bg.visible = False
            fill_bar.visible = False
            player_marker.visible = False
        return

    # --- GAMEPLAY LOGIC ---
    target_note = practice_notes[current_target_idx]
    target_box.y = note_to_y(target_note) - 20  
    target_box_bg.y = note_to_y(target_note) - 20
    fill_bar.y = note_to_y(target_note) - 20
    progress_label.text = f"Progress: {current_target_idx}/{len(practice_notes)}"

    if game_state == "START":
        state_timer += dt
        if state_timer > 1.0: 
            start_time = time.time() 
            game_state = "LISTEN"
            state_timer = 0.0
            play_current_target()
            
    elif game_state == "LISTEN":
        status_label.text = "LISTEN..."
        status_label.color = (0, 153, 255, 255)
        note_label.text = get_note_name(target_note)
        note_label.color = (255, 255, 255, 255)
        instructions_label.visible = False
        target_box.color = (100, 100, 120)
        player_marker.visible = False
        fill_bar.width = 0
        
        state_timer += dt
        if state_timer >= 1.5:
            game_state = "SING"
            state_timer = 0.0
            
    elif game_state == "SING":
        status_label.text = "MATCH THE PITCH"
        status_label.color = (255, 204, 0, 255)
        instructions_label.visible = True
        
        if current_pitch is not None:
            target_y = note_to_y(current_pitch)
            player_marker.y += (target_y - player_marker.y) * 0.3 
            player_marker.visible = True
            
            if abs(current_pitch - target_note) <= 1.0:
                target_box.color = (255, 204, 0) 
                match_progress += dt 
                
                if match_progress >= REQUIRED_HOLD_TIME:
                    current_target_idx += 1
                    match_progress = 0.0
                    game_state = "LISTEN"
                    state_timer = 0.0
                    play_current_target() 
            else:
                target_box.color = (100, 100, 120)
                match_progress = max(0, match_progress - dt * 2)
        else:
            player_marker.visible = False
            target_box.color = (100, 100, 120)
            match_progress = max(0, match_progress - dt * 2)

        fill_percentage = match_progress / REQUIRED_HOLD_TIME
        fill_bar.width = 300 * fill_percentage

@window.event
def on_draw():
    window.clear()
    batch.draw()

@window.event
def on_close():
    global is_running
    is_running = False

pyglet.clock.schedule_interval(update, 1/60.0)
pyglet.app.run()