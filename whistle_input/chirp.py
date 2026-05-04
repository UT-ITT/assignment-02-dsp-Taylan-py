import pyaudio
import numpy as np
import pyglet
from pyglet.window import key
from pyglet import shapes
from pynput.keyboard import Key, Controller
import threading
import time

# --- 1. Konfiguration ---
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
CHUNK = 1024        # (1P) Low Latency
THRESHOLD = 500000  # (2P) Robust against noise
WHISTLE_RANGE = (500, 2500)
MIN_DELTA = 100     # (3P) Upwards/Downwards Erkennung

# --- 2. Styling ---
MENU_TITLE = "ASTRO NAVIGATOR"
MENU_ITEMS = ["START GAME", "OPTIONS", "MULTIPLAYER", "EXIT"]
FONT_FAMILY = ('Trebuchet MS', 'Verdana', 'Arial', 'sans-serif')
COLOR_TEXT = (240, 240, 240, 255)
COLOR_HIGHLIGHT_TEXT = (255, 215, 0, 255)
COLOR_STATUS = (100, 255, 100, 200)

# --- 3. Shared State Manager ---
class GameState:
    def __init__(self):
        self.selected_index = 0
        self.status_msg = "Pfeife 'ooouuuiii' für HOCH, 'iiiuuuooo' für RUNTER"
        self.running = True

state = GameState()
pynput_keyboard = Controller()

# --- 4. Audio Thread ---
def audio_listener_thread():
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                    input=True, frames_per_buffer=CHUNK)
    
    last_freq = None
    print("Audio Thread: Höre zu...")

    while state.running:
        try:
            data = stream.read(CHUNK, exception_on_overflow=False)
            samples = np.frombuffer(data, dtype=np.int16)
            
            # FIX: np.abs statt sqrt/mean**2 um Overflows zu verhindern
            if np.abs(samples).mean() < 50:
                continue

            fft_data = np.fft.rfft(samples * np.hanning(len(samples)))
            magnitudes = np.abs(fft_data)
            max_idx = np.argmax(magnitudes)
            freq = max_idx * RATE / CHUNK

            if WHISTLE_RANGE[0] < freq < WHISTLE_RANGE[1] and magnitudes[max_idx] > THRESHOLD:
                if last_freq is not None:
                    diff = freq - last_freq
                    
                    if diff > MIN_DELTA: 
                        state.status_msg = f"↑ Pfeifen: HOCH ({int(freq)}Hz)"
                        # (1P) Triggered key events work
                        pynput_keyboard.press(Key.up)
                        pynput_keyboard.release(Key.up)
                        time.sleep(0.3) 
                        last_freq = None
                    
                    elif diff < -MIN_DELTA: 
                        state.status_msg = f"↓ Pfeifen: RUNTER ({int(freq)}Hz)"
                        # (1P) Triggered key events work
                        pynput_keyboard.press(Key.down)
                        pynput_keyboard.release(Key.down)
                        time.sleep(0.3)
                        last_freq = None
                    else:
                        last_freq = freq
                else:
                    last_freq = freq
            else:
                last_freq = None
        except Exception as e:
            print(f"Audio Fehler im Thread: {e}")
            break

    stream.stop_stream()
    stream.close()
    p.terminate()
    print("Audio Thread: Beendet.")

# --- 5. GUI Class (Pyglet 2.0+ Kompatibel) ---
class PrettyMenuWindow(pyglet.window.Window):
    def __init__(self):
        super().__init__(width=1280, height=720, caption="Whistle Input: Astro Navigator", resizable=True)
        self.set_minimum_size(800, 600)
        
        self.main_batch = pyglet.graphics.Batch()
        self.bg_batch = pyglet.graphics.Batch()
        
        self.menu_labels = []
        self._initialize_visuals()

    def _initialize_visuals(self):
        cx, cy = self.width // 2, self.height // 2
        
        # 1. Hintergrund
        self.bg_rect = shapes.Rectangle(0, 0, self.width, self.height, 
                                        color=(15, 15, 45), batch=self.bg_batch)

        # 2. Selection Highlight Box
        self.highlight_box = shapes.Rectangle(0, 0, 400, 60, 
                                              color=(255, 215, 0, 80), batch=self.main_batch)

        # 3. Title 
        self.title_label = pyglet.text.Label(MENU_TITLE,
                          font_name=FONT_FAMILY, font_size=48,
                          x=cx, y=self.height - 80, anchor_x='center', anchor_y='center',
                          color=COLOR_TEXT, batch=self.main_batch)

        # 4. Status Text
        self.status_label = pyglet.text.Label(state.status_msg,
                          font_name=FONT_FAMILY, font_size=14,
                          x=cx, y=40, anchor_x='center', anchor_y='center',
                          color=COLOR_STATUS, batch=self.main_batch)

        # 5. Menu Items generieren
        start_y = cy + 100
        for i, item in enumerate(MENU_ITEMS):
            label = pyglet.text.Label(item,
                          font_name=FONT_FAMILY, font_size=28,
                          x=cx, y=start_y - (i * 70),
                          anchor_x='center', anchor_y='center',
                          color=COLOR_TEXT, batch=self.main_batch)
            self.menu_labels.append(label)

        self._update_highlight_position()

    def _update_highlight_position(self):
        current_label = self.menu_labels[state.selected_index]
        self.highlight_box.x = current_label.x - (self.highlight_box.width // 2)
        self.highlight_box.y = current_label.y - (self.highlight_box.height // 2)

    def on_resize(self, width, height):
        self.bg_rect.width = width
        self.bg_rect.height = height
        
        cx = width // 2
        self.title_label.x = cx
        self.title_label.y = height - 80
        self.status_label.x = cx
        
        start_y = height // 2 + 100
        for i, label in enumerate(self.menu_labels):
            label.x = cx
            label.y = start_y - (i * 70)
            
        self._update_highlight_position()
        super().on_resize(width, height)

    def on_draw(self):
        self.clear()
        
        if self.status_label.text != state.status_msg:
            self.status_label.text = state.status_msg
            
        for i, label in enumerate(self.menu_labels):
            if i == state.selected_index:
                label.color = COLOR_HIGHLIGHT_TEXT
            else:
                label.color = COLOR_TEXT
                
        self._update_highlight_position()
        
        self.bg_batch.draw()
        self.main_batch.draw()

    def on_key_press(self, symbol, modifiers):
        # Das Fenster reagiert auf die echten simulierten Tastendrücke von Pynput!
        if symbol == key.UP:
            state.selected_index = (state.selected_index - 1) % len(MENU_ITEMS)
        elif symbol == key.DOWN:
            state.selected_index = (state.selected_index + 1) % len(MENU_ITEMS)
        elif symbol == key.ENTER:
            print(f"Ausgewählt: {MENU_ITEMS[state.selected_index]}")
            if MENU_ITEMS[state.selected_index] == "EXIT":
                self.on_close()
        elif symbol == key.F:
            self.set_fullscreen(not self.fullscreen)
        elif symbol == key.ESCAPE:
            self.on_close()

    def on_close(self):
        state.running = False
        super().on_close()

if __name__ == "__main__":
    # 1. Starte Audio-Thread im Hintergrund
    threading.Thread(target=audio_listener_thread, daemon=True).start()
    
    # 2. Starte GUI im Vordergrund
    print("Starte GUI... (Ignoriere eventuelle ALSA/Jack Warnungen in der Konsole, die sind normal)")
    window = PrettyMenuWindow()
    pyglet.app.run()