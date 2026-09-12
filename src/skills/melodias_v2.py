import subprocess
import json
import os
def play_sound(note, duration):
    frequency = {
        'C4': 261.63,
        'D4': 293.66,
        'E4': 329.63,
        'F4': 349.23,
        'G4': 392.00,
        'A4': 440.00,
        'B4': 493.88,
        'C5': 523.25
    }
    
    if note not in frequency:
        return
    
    freq = frequency[note]
    command = f"play -n synth {duration} sine {freq}"
    subprocess.call(command, shell=True)
def compose_melody(melody):
    for note, duration in melody:
        play_sound(note, duration)
def run(params):
    melody = params.get('melody', [])
    compose_melody(melody)
    return {"status": "melody played"}