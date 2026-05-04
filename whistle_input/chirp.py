import numpy as np
import sounddevice as sd
import pyglet
from pyglet.window import key
from pyglet import shapes
from pynput.keyboard import Key, Controller
import time

# --- 1. Konfiguration ---
CHANNELS = 1
RATE = 44100
CHUNK = 1024        
THRESHOLD = 150000  # Keep whatever volume worked for you here!
WHISTLE_RANGE = (120, 260) # Laser-focused exactly on your hum
MIN_DELTA = 30      # Hair-trigger sensitivity!

# --- 2. Styling ---
MENU_TITLE = "ASTRO NAVIGATOR"
MENU_ITEMS = ["START GAME", "OPTIONS", "MULTIPLAYER", "EXIT"]
FONT_FAMILY = ('Segoe UI', 'Trebuchet MS', 'Arial')
COLOR_TEXT = (240, 240, 240, 255)
COLOR_HIGHLIGHT_TEXT = (255, 215, 0, 255)
COLOR_STATUS = (0, 255, 204, 255)

# --- 3. Shared State Manager ---
class GameState:
    def __init__(self):
        self.selected_index = 0
        self.status_msg = "Sing 'ooouuuiii' (HOCH) oder 'iiiuuuooo' (RUNTER)"
        self.running = True

state = GameState()
pynput_keyboard = Controller()

# --- 4. Global Variables for Visualization ---
current_fft_bins = np.zeros(128)
current_freq_display = 0
current_vol_display = 0

last_freq = None
last_trigger_time = 0.0

# --- 5. SoundDevice Audio Callback ---
def audio_callback(indata, frames, time_info, status):
    global last_freq, last_trigger_time, current_fft_bins, current_freq_display, current_vol_display
    
    if time.time() - last_trigger_time < 0.4: # Cooldown to prevent spamming
        return

    samples = indata[:, 0]
    
    # FFT Math
    windowed = samples * np.hanning(len(samples))
    fft_data = np.fft.rfft(windowed)
    magnitudes = np.abs(fft_data)
    
    # Update visualizer bins (scaled down so they fit on screen)
    current_fft_bins = magnitudes[:128] / 2000.0 
    
    max_idx = np.argmax(magnitudes)
    freq = max_idx * RATE / CHUNK
    vol = magnitudes[max_idx]

    # Update Debug Variables for the screen
    current_freq_display = freq
    current_vol_display = vol

    # Whistle Detection Logic
    if WHISTLE_RANGE[0] < freq < WHISTLE_RANGE[1] and vol > THRESHOLD:
        if last_freq is not None:
            diff = freq - last_freq
            
            if diff > MIN_DELTA: 
                state.status_msg = f"↑ ERKANNT: HOCH ({int(freq)}Hz)"
                pynput_keyboard.press(Key.up)
                pynput_keyboard.release(Key.up)
                last_trigger_time = time.time()
                last_freq = None
                
            elif diff < -MIN_DELTA: 
                state.status_msg = f"↓ ERKANNT: RUNTER ({int(freq)}Hz)"
                pynput_keyboard.press(Key.down)
                pynput_keyboard.release(Key.down)
                last_trigger_time = time.time()
                last_freq = None
            else:
                last_freq = freq
        else:
            last_freq = freq
    else:
        # Reset if we drop below volume or outside range
        last_freq = None

stream = sd.InputStream(channels=CHANNELS, samplerate=RATE, blocksize=CHUNK, callback=audio_callback, dtype='int16', latency='low')
stream.start()

# --- 6. GUI Class ---
class PrettyMenuWindow(pyglet.window.Window):
    def __init__(self):
        super().__init__(width=1024, height=768, caption="Whistle Input: Astro Navigator", resizable=True)
        self.main_batch = pyglet.graphics.Batch()
        self.menu_labels = []
        
        # FFT Visualizer Setup
        self.fft_bars = [shapes.Line(x=0, y=0, x2=0, y2=0, thickness=4, color=(0, 153, 255), batch=self.main_batch) for _ in range(128)]
        
        self._initialize_visuals()

    def _initialize_visuals(self):
        cx, cy = self.width // 2, self.height // 2
        
        self.highlight_box = shapes.Rectangle(0, 0, 400, 60, color=(255, 215, 0, 80), batch=self.main_batch)
        self.title_label = pyglet.text.Label(MENU_TITLE, font_name=FONT_FAMILY, font_size=48, x=cx, y=self.height - 80, anchor_x='center', anchor_y='center', color=COLOR_TEXT, batch=self.main_batch)
        self.status_label = pyglet.text.Label(state.status_msg, font_name=FONT_FAMILY, font_size=20, x=cx, y=self.height - 140, anchor_x='center', anchor_y='center', color=COLOR_STATUS, batch=self.main_batch)

        # Debug Text
        self.debug_label = pyglet.text.Label("DEBUG INFO", font_name=FONT_FAMILY, font_size=14, x=20, y=self.height - 40, color=(150, 150, 150, 255), batch=self.main_batch)

        start_y = cy + 50
        for i, item in enumerate(MENU_ITEMS):
            label = pyglet.text.Label(item, font_name=FONT_FAMILY, font_size=28, x=cx, y=start_y - (i * 70), anchor_x='center', anchor_y='center', color=COLOR_TEXT, batch=self.main_batch)
            self.menu_labels.append(label)

        self._update_highlight_position()

    def _update_highlight_position(self):
        current_label = self.menu_labels[state.selected_index]
        self.highlight_box.x = current_label.x - (self.highlight_box.width // 2)
        self.highlight_box.y = current_label.y - (self.highlight_box.height // 2)

    def update(self, dt):
        # Update text
        if self.status_label.text != state.status_msg:
            self.status_label.text = state.status_msg
            self.status_label.color = (255, 204, 0, 255) # Flash yellow on change
        else:
            # Fade back to normal color slowly
            r, g, b, a = self.status_label.color
            if g < 255: self.status_label.color = (0, 255, 204, 255)

        for i, label in enumerate(self.menu_labels):
            label.color = COLOR_HIGHLIGHT_TEXT if i == state.selected_index else COLOR_TEXT
        self._update_highlight_position()

        # Update Debug Stats
        self.debug_label.text = f"Live Vol: {int(current_vol_display)} | Live Hz: {int(current_freq_display)}"

        # Update FFT Visualizer
        bar_spacing = self.width / 128
        for i, bar in enumerate(self.fft_bars):
            target_height = min(current_fft_bins[i], 150) 
            bar.x = bar.x2 = int(i * bar_spacing)
            bar.y, bar.y2 = 0, target_height
            
            # Color the bar pink if it's currently the loudest frequency
            if current_vol_display > THRESHOLD and i == int((current_freq_display * CHUNK) / RATE):
                bar.color = (255, 0, 102) 
            else:
                bar.color = (0, 153, 255)

    def on_draw(self):
        self.clear()
        self.main_batch.draw()

    def on_key_press(self, symbol, modifiers):
        if symbol == key.UP: state.selected_index = (state.selected_index - 1) % len(MENU_ITEMS)
        elif symbol == key.DOWN: state.selected_index = (state.selected_index + 1) % len(MENU_ITEMS)
        elif symbol == key.ESCAPE: self.on_close()

    def on_close(self):
        state.running = False
        stream.stop()
        stream.close()
        super().on_close()

if __name__ == "__main__":
    window = PrettyMenuWindow()
    pyglet.clock.schedule_interval(window.update, 1/60.0) # 60 FPS update loop
    pyglet.app.run()