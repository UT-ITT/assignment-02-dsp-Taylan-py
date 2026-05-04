import pyaudio
import numpy as np
import pyglet
from pyglet.window import key
from pyglet import shapes
import threading
import time

# --- 1. Konfiguration ---
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
CHUNK = 1024        

VOLUME_THRESHOLD = 3000  
LONG_SOUND_DURATION = 0.6 
DEBOUNCE = 0.3            

MENU_TITLE = "ASTRO NAVIGATOR"
MENU_ITEMS = ["START GAME", "OPTIONS", "MULTIPLAYER", "EXIT"]
# Simplified font list for better compatibility
FONT_FAMILY = 'Arial' 
COLOR_TEXT = (240, 240, 240, 255)
COLOR_HIGHLIGHT_TEXT = (255, 215, 0, 255)
COLOR_STATUS = (100, 255, 100, 200)

class GameState:
    def __init__(self):
        self.selected_index = 0
        self.status_msg = "CLAP for DOWN | LONG SHOUT for UP"
        self.running = True

state = GameState()

def audio_listener_thread():
    p = pyaudio.PyAudio()
    try:
        stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                        input=True, frames_per_buffer=CHUNK)
    except Exception as e:
        print(f"Could not open audio stream: {e}")
        return

    sound_start_time = None
    last_action_time = 0

    while state.running:
        try:
            data = stream.read(CHUNK, exception_on_overflow=False)
            samples = np.frombuffer(data, dtype=np.int16)
            volume = np.linalg.norm(samples) / np.sqrt(len(samples))

            if volume > VOLUME_THRESHOLD:
                if sound_start_time is None:
                    sound_start_time = time.time()
            else:
                if sound_start_time is not None:
                    duration = time.time() - sound_start_time
                    current_time = time.time()

                    if current_time - last_action_time > DEBOUNCE:
                        if duration > LONG_SOUND_DURATION:
                            state.selected_index = (state.selected_index - 1) % len(MENU_ITEMS)
                            state.status_msg = f"↑ LONG SOUND ({duration:.1f}s)"
                        else:
                            state.selected_index = (state.selected_index + 1) % len(MENU_ITEMS)
                            state.status_msg = "↓ SHORT CLAP"
                        last_action_time = current_time
                    sound_start_time = None
        except:
            break

    stream.stop_stream()
    stream.close()
    p.terminate()

class PrettyMenuWindow(pyglet.window.Window):
    def __init__(self):
        super().__init__(width=1280, height=720, caption="Voice Control", resizable=True)
        self.main_batch = pyglet.graphics.Batch()
        self.bg_batch = pyglet.graphics.Batch()
        self.menu_labels = []
        self._initialize_visuals()

    def _initialize_visuals(self):
        cx, cy = self.width // 2, self.height // 2
        
        self.bg_rect = shapes.Rectangle(0, 0, self.width, self.height, 
                                        color=(10, 10, 30), batch=self.bg_batch)

        self.highlight_box = shapes.Rectangle(0, 0, 420, 70, 
                                              color=(255, 215, 0, 60), batch=self.main_batch)

        # REMOVED 'bold=True' to fix the TypeError
        self.title_label = pyglet.text.Label(MENU_TITLE,
                          font_name=FONT_FAMILY, font_size=54,
                          x=cx, y=self.height - 100, anchor_x='center', anchor_y='center',
                          color=COLOR_TEXT, batch=self.main_batch)

        self.status_label = pyglet.text.Label(state.status_msg,
                          font_name=FONT_FAMILY, font_size=16,
                          x=cx, y=50, anchor_x='center', anchor_y='center',
                          color=COLOR_STATUS, batch=self.main_batch)

        start_y = cy + 80
        for i, item in enumerate(MENU_ITEMS):
            label = pyglet.text.Label(item,
                          font_name=FONT_FAMILY, font_size=32,
                          x=cx, y=start_y - (i * 80),
                          anchor_x='center', anchor_y='center',
                          color=COLOR_TEXT, batch=self.main_batch)
            self.menu_labels.append(label)

    def on_draw(self):
        self.clear()
        self.status_label.text = state.status_msg
        for i, label in enumerate(self.menu_labels):
            if i == state.selected_index:
                label.color = COLOR_HIGHLIGHT_TEXT
                self.highlight_box.x = label.x - (self.highlight_box.width // 2)
                self.highlight_box.y = label.y - (self.highlight_box.height // 2)
                self.highlight_box.visible = True
            else:
                label.color = COLOR_TEXT
        self.bg_batch.draw()
        self.main_batch.draw()

    def on_key_press(self, symbol, modifiers):
        if symbol == key.ENTER:
            print(f"Selected: {MENU_ITEMS[state.selected_index]}")
            if MENU_ITEMS[state.selected_index] == "EXIT":
                self.close()

    def on_close(self):
        state.running = False
        super().on_close()

if __name__ == "__main__":
    threading.Thread(target=audio_listener_thread, daemon=True).start()
    window = PrettyMenuWindow()
    pyglet.app.run()