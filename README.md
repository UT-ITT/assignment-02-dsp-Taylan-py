# Vocal & Audio Input Games Collection

This repository contains two experimental Python games that utilize real-time audio processing to control gameplay. One focuses on vocal pitch accuracy, while the other uses whistling frequency shifts for navigation.

## 🚀 Built With
* **Python 3.11.15**
* **Pyglet**: High-performance windowing and multimedia library.
* **PyAudio**: Real-time audio I/O.
* **NumPy**: Fast Fourier Transform (FFT) and mathematical processing.

---

## 🎮 The Games

### 1. Vocal Pitch Trainer
A tool designed to help singers improve their pitch accuracy. The game plays a reference note, and the player must match that pitch with their voice and hold it to progress.

* **How to Play:**
    1. Listen to the target note.
    2. Sing into your microphone to move the red marker.
    3. Match the pitch of the target box (it will turn yellow when you are close).
    4. Hold the pitch until the progress bar fills up.
* **Controls:**
    * `SPACE`: Replay the target note.
    * `F`: Toggle Fullscreen.
    * `R`: Reset Highscore (on Game Over screen).

To run: python karaoke_trainer.py

### 2. Astro Navigator (Whistle Control)
A menu-based navigation experiment where the interface is controlled by the frequency glide of a whistle.

* **How to Play:**
    * Whistle a rising tone (low to high) to move the selection **UP**.
    * Whistle a falling tone (high to low) to move the selection **DOWN**.
* **Controls:**
    * `ENTER`: Confirm selection.
    * `F`: Toggle Fullscreen.
    * `ESC`: Exit.

To run: python chirp.py
---

## 🛠️ Setup & Installation

### Prerequisites
Ensure you have a working microphone connected and set as your system's **default input device**.

### Environment Setup
We recommend using Conda to manage the environment. You can use the provided `environment.yaml` file:
```bash
# Create the environment
conda env create -f environment.yaml

# Activate the environment
conda activate <env_name>

Additionally "sounddevice" has to be installed via pip