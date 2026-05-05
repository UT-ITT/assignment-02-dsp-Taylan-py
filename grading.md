# Taylan-py (11.5/15P)

## 1 - Karaoke Game (7/7P)
* frequency detection works correctly and robustly
    * yep (3P)
* the game is playable, does not crash, and is (kind of) fun to play
    * yep, really nice! (2P)
* the game tracks some kind of score for correctly sung notes
    * yep (1P)
* low latency between input and detection
    * yep (1P)


## 2 - Whistle Input (4.5/7P)
* upwards and downwards whistling is detected correctly and robustly
    * whistling doesn't work, only works for deep voices (1.5P)
*  detection is robust against background noise
    * speaking triggers input sometimes (1P)
* low latency between input and detection
    * yep (1P)
* triggered key events work
    * yep (1P)
* We really enjoyed screaming at our computers with the second script :D 
    * buuuuut please don't use pyaudio, since it doesn't work with newer python versions

## Code-Quality and .venv used (0/1P)
* karaoke script and whistle script named incorrectly
* no input device selectable
* no requirements.txt