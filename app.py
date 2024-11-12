import os
import numpy as np
import scipy.fftpack
import sounddevice as sd
import time
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import threading


# Constants
SAMPLE_FREQ = 44100
WINDOW_SIZE = 2048
#WINDOW_STEP = 2000
WINDOW_STEP = 1000
NUM_HPS = 5
POWER_THRESH = 1e-6
CONCERT_PITCH = 440
#WHITE_NOISE_THRESH = 0.2
WHITE_NOISE_THRESH = 0.05
DELTA_FREQ = SAMPLE_FREQ / WINDOW_SIZE
OCTAVE_BANDS = [31, 63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]
HANN_WINDOW = np.hanning(WINDOW_SIZE)
ALL_NOTES = ["A", "A#", "B", "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#"]

app = Flask(__name__)
socketio = SocketIO(app)

is_running = False
note_buffer = ["1", "2"]

def find_closest_note(pitch):
    i = int(np.round(np.log2(pitch / CONCERT_PITCH) * 12))
    closest_note = ALL_NOTES[i % 12] + str(4 + (i + 9) // 12)
    closest_pitch = CONCERT_PITCH * 2 ** (i / 12)
    return closest_note, closest_pitch

def callback(in_data, frames, time, status):
    global note_buffer
    if status:
        print(status)
        return

    if any(in_data):
        window_samples = np.concatenate((np.zeros(WINDOW_SIZE), in_data[:, 0]))[-WINDOW_SIZE:]
        signal_power = (np.linalg.norm(window_samples, ord=2) ** 2) / len(window_samples)

        if signal_power < POWER_THRESH:
            return

        hann_samples = window_samples * HANN_WINDOW
        magnitude_spec = abs(scipy.fftpack.fft(hann_samples)[:len(hann_samples)//2])
        
        #to the front
        socketio.emit('fft_data', {'fft': magnitude_spec.tolist()})


        for j in range(len(OCTAVE_BANDS) - 1):
            ind_start = int(OCTAVE_BANDS[j] / DELTA_FREQ)
            ind_end = int(OCTAVE_BANDS[j + 1] / DELTA_FREQ)
            ind_end = ind_end if len(magnitude_spec) > ind_end else len(magnitude_spec)

            avg_energy_per_freq = (np.linalg.norm(magnitude_spec[ind_start:ind_end], ord=2) ** 2) / (ind_end - ind_start)
            avg_energy_per_freq = avg_energy_per_freq ** 0.5

            for i in range(ind_start, ind_end):
                magnitude_spec[i] = magnitude_spec[i] if magnitude_spec[i] > WHITE_NOISE_THRESH * avg_energy_per_freq else 0

            mag_spec_ipol = np.interp(np.arange(0, len(magnitude_spec), 1 / NUM_HPS), np.arange(0, len(magnitude_spec)), magnitude_spec)
            mag_spec_ipol = mag_spec_ipol / np.linalg.norm(mag_spec_ipol, ord=2)
            hps_spec = mag_spec_ipol.copy()

            for i in range(NUM_HPS):
                tmp_hps_spec = np.multiply(hps_spec[:int(np.ceil(len(mag_spec_ipol)/(i+1)))], mag_spec_ipol[::(i+1)])
                if not any(tmp_hps_spec):
                    break

                hps_spec = tmp_hps_spec
                max_ind = np.argmax(hps_spec)
                max_freq = max_ind * (SAMPLE_FREQ / WINDOW_SIZE) / NUM_HPS

                closest_note, closest_pitch = find_closest_note(max_freq)
                note_buffer.insert(0, closest_note)
                note_buffer.pop()

                socketio.emit('note_detected', {'note': closest_note})

def run_tuner():
    global is_running
    with sd.InputStream(channels=1, callback=callback, blocksize=WINDOW_STEP, samplerate=SAMPLE_FREQ):
        while is_running:
            time.sleep(0.5)

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('start_tuner')
def handle_start_tuner():
    global is_running
    if not is_running:
        is_running = True
        threading.Thread(target=run_tuner).start()
        emit('tuner_started', {'message': 'Tuner started!'})

@socketio.on('stop_tuner')  
def handle_stop_tuner():
    global is_running
    is_running = False
    emit('tuner_stopped', {'message': 'Tuner stopped!'})

if __name__ == '__main__':
    socketio.run(app)
