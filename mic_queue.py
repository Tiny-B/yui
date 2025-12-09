# mic_queue.py   (save this in the same folder as your main script)
import queue
import sounddevice as sd

SAMPLE_RATE = 16000          # Whisper, Vosk, and Google all prefer 16 kHz
CHANNELS     = 1             # mono

def microphone_stream(chunk_ms: int = 100):
    """
    Returns a thread‑safe `queue.Queue` that receives raw PCM bytes.
    The caller can read from the queue at any time.
    chunk_ms – size of each audio block (lower = lower latency, but more API calls)
    """
    q = queue.Queue()

    def callback(indata, frames, time, status):
        """sounddevice calls us with a NumPy array; we push raw bytes."""
        if status:
            print(f"[mic] {status}", flush=True)
        # sounddevice gives us int16 by default → just cast to bytes
        q.put(bytes(indata))

    stream = sd.RawInputStream(
        samplerate=SAMPLE_RATE,
        blocksize=int(SAMPLE_RATE * (chunk_ms / 1000)),
        dtype='int16',
        channels=CHANNELS,
        callback=callback,
    )
    stream.start()      # start capturing immediately
    return q, stream
