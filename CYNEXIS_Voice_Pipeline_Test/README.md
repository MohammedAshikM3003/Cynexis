# CYNEXIS Voice Pipeline Test

This browser prototype tests the voice interaction concept:

Microphone -> browser SpeechRecognition (STT) -> mock intent/action layer -> browser SpeechSynthesis (TTS) -> laptop speakers.

It is not yet connected to the CYNEXIS Python/FastAPI backend, ESP32, physical robot, or final local AI models.

## Run

Open `index.html` in Chrome or Edge and allow microphone access.

Try:
- CYNEXIS, say hello to everyone
- CYNEXIS, move forward
- CYNEXIS, stop
- What is your name?
- What can you do?

The voice you hear is your browser/operating-system voice. Later it will be replaced by the selected CYNEXIS local TTS voice.
