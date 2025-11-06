# --------------------------------------------------------------
#  IMPORTS
# --------------------------------------------------------------
from ollama import chat
from ollama import ChatResponse
from murf import Murf
import sounddevice as sd
import numpy as np
from pydub import AudioSegment
import io, os, sys, requests, json, pathlib, traceback, shutil
import random
from typing import List, Tuple
import subprocess, tempfile, platform
import whisper
import pathlib
import argparse

response_history = [""]
banned_words_list = [
  "cunt",
	"fag",
	"faggot",
	"tranny",
	"nigger",
	"puff",
	"blackie",
	"incel",
	"rape",
	"nazi",
	"dick",
	"cock",
]
random_prompts = [
  "Talk about cats",
	"Talk about gummy bears",
	"Eri",
	"Talk about something",
	"Talk about something silly",
	"Talk about something random",
	"Talk about vtuber life",
	"Talk about being a virtual girl",
	"Compliment yourself",
	"Roast Eri",
	"Roast the viewers",
	"Say something nice about Eri",
	"Talk about your code",
	"Talk about you aspirations",
	"Talk about what makes you angry",
	"Tell us a joke",
	"Tell us a secret",
	"Do you wish you had legs",
]

# intervalID = 0
# delay = 20000
# min_delay = 20000
# max_delay = 40000

# max_history = 100

# --------------------------------------------------------------
#  COLOUR HELPERS 
# --------------------------------------------------------------
def color(text, *, fore=None, back=None, bold=False, underline=False):
    """
    Returns *text* wrapped in ANSI codes.

    Parameters
    ----------
    fore: int|str|None
        Standard colour name (e.g. "red") or 0‑255 256‑color index.
    back: int|str|None
        Same for background.
    bold, underline: bool
        Add style flags.
    """
    codes = []

    # style flags
    if bold:
        codes.append("1")
    if underline:
        codes.append("4")

    # map simple colour names to the 30‑37 range
    std = {
        "black":   30, "red": 31, "green": 32, "yellow": 33,
        "blue":    34, "magenta": 35, "cyan": 36, "white": 37
    }

    # foreground
    if isinstance(fore, str):
        codes.append(str(std[fore.lower()]))
    elif isinstance(fore, int):               # treat as 256‑color index
        codes.append(f"38;5;{fore}")
    # background
    if isinstance(back, str):
        codes.append(str(std[back.lower()] + 10))   # 40‑47 = 10 higher
    elif isinstance(back, int):
        codes.append(f"48;5;{back}")

    seq = ";".join(codes) or "0"     # "0" = reset if nothing else
    return f"\x1b[{seq}m{text}\x1b[0m"

# --------------------------------------------------------------
#  HISTORY HELPERS
# --------------------------------------------------------------
# Lets the AI know the conversation so far
def build_history_string():
  if "" in response_history: return

  #  history limit, possibly 100?
  if (len(response_history) == max_history): response_history.remove(0)

  content = "(Here is the chat history this session, please refer to it when needed. "
  for message in response_history:
    content += f"{message}, "

  content += ")"
  return content

# --------------------------------------------------------------
#  CONTENT FILTERING
# --------------------------------------------------------------
# filter out undesirable words from user prompt and AI response
def filter_word(text_to_filter):
  separated_words = text_to_filter.split(" ")

  for word in separated_words:
    for banned_word in banned_words_list:
      if word == banned_word:
        print(f"{word} has been filtered out.")
        separated_words.remove(word)
        

  return " ".join(separated_words)

# --------------------------------------------------------------
#  USER INPUT / RANDOM PROMPT
# --------------------------------------------------------------
# Get the users input as the prompt
def get_user_prompt():
  print("Enter a chat message.")
  user_input  = input("") # change to user input
  user_prompt = filter_word(user_input)
  
  prompt = f"{user_prompt}"

  # change prompt to something after, might break if blank

  return prompt

# --------------------------------------------------------------
#  TTS / Audio
# --------------------------------------------------------------
def _download_mp3(url: str) -> bytes:
    """
    Download the URL that Murf returns and make sure it looks like an MP3.
    If not, raise a descriptive RuntimeError.
    """
    r = requests.get(url, allow_redirects=True, timeout=15)

    # -----------------------------------------------------------------
    # 1️⃣ Status code must be 2xx
    # -----------------------------------------------------------------
    if not r.ok:
        raise RuntimeError(
            f"Failed to download audio – HTTP {r.status_code} from {url}\n"
            f"Response body (first 200 bytes):\n{r.text[:200]!r}"
        )

    # -----------------------------------------------------------------
    # 2️⃣ Content‑Type header should be audio/* (most providers use
    #    'audio/mpeg' for MP3).  Some CDNs omit it – fall back to sniffing.
    # -----------------------------------------------------------------
    ct = r.headers.get("Content-Type", "").lower()
    if not ct.startswith("audio/"):
        # Very common that a 403/404 page comes back as text/html.
        # Show the first few bytes so you can see if it’s HTML/JSON.
        preview = r.content[:200]
        raise RuntimeError(
            f"URL did not return audio – Content‑Type={ct!r}\n"
            f"Received {len(r.content)} bytes. First 200 bytes preview:\n"
            f"{preview!r}"
        )

    # -----------------------------------------------------------------
    # 3️⃣ Basic sanity‑check on size – MP3s are rarely < 1 KB (unless error page).
    # -----------------------------------------------------------------
    if len(r.content) < 1024:
        raise RuntimeError(
            f"Downloaded audio is suspiciously small ({len(r.content)} bytes). "
            f"Probably an error page. First 200 bytes:\n{r.content[:200]!r}"
        )

    # -----------------------------------------------------------------
    # 4️⃣ (Optional) Write to a temp file so you can examine it with ffplay,
    #    Audacity, etc.  Helpful during development.
    # -----------------------------------------------------------------
    if os.getenv("DEBUG_DUMP_MP3"):
        tmp_path = pathlib.Path("/tmp") / f"murftts_{int(time.time())}.mp3"
        tmp_path.write_bytes(r.content)
        print(f"[DEBUG] Dumped raw MP3 to {tmp_path}")

    return r.content

def _play_with_system_player(mp3_bytes: bytes):
    # Write a temp file (auto‑deleted on close)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        tmp.write(mp3_bytes)
        tmp_path = tmp.name

    # List of candidate commands we know how to invoke
    candidates = [
        ("ffplay",   ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", tmp_path]),
        ("mpg123",   ["mpg123", "--quiet", tmp_path]),
        ("mpv",      ["mpv", "--no-video", "--quiet", tmp_path]),
        ("cvlc",     ["cvlc", "--play-and-exit", "--quiet", tmp_path]),
    ]

    for name, cmd in candidates:
        if shutil.which(name):                 # command exists on this system?
            try:
                subprocess.run(cmd, check=True)
                break                         # success → exit loop
            except subprocess.CalledProcessError as e:
                print(f"[WARN] {name} exited with error: {e}", file=sys.stderr)
        else:
            print(f"[INFO] {name} not found – trying next player...", file=sys.stderr)

    else:
        raise RuntimeError(
            "No supported CLI audio player found. Install ffmpeg (ffplay), mpg123, mpv, or vlc."
        )

    # Clean up the temporary file
    try:
        os.unlink(tmp_path)
    except OSError:
        pass

def play_tts(prompt: str):
    client = Murf(api_key="ap2_c18e6c32-a3bb-403e-9c8e-f87869795b06")
    resp   = client.text_to_speech.generate(
                text=prompt,
                voice_id="bn-IN-anwesha",
                  style = "Conversational",
                  pitch = 15,
                  rate = 10,
                multi_native_locale="en-UK",
            )
    mp3 = _download_mp3(resp.audio_file)

    _play_with_system_player(mp3);



#  have AI give response upon load to spin up ollama, then need keep alive setting adjusted
#  give a random response if left without interaction, on a randomized timer
#  stop random response timer if interaction made and block random response for some time too allow response to interaction
# add ruleset for random response
def get_random_int(max):
  return #Math.floor(Math.random() * max);

# remove random prompt from array so AI doesn"t repeat, need to add LOTS more random prompts
def get_random_response():
  index = get_random_int(len(random_prompts)) - 1
  if (index < 0): index = 0

  response = random_prompts[index]
  print(f"Random prompt {index}/{len(random_prompts)}: {response}")

  return response

def random_response_delay():
  delay = get_random_int(max_delay)
  if (delay < min_delay): delay += min_delay
  get_response(True)

# --------------------------------------------------------------
#  MAIN CHAT LOOP
# --------------------------------------------------------------
def get_response(is_random = False):
  #clearInterval(intervalID);
  #print(f"Delay {intervalID} has been cancelled.")

  print(color(' '.join(response_history), fore="magenta"))

  prompt = ""
  if (is_random):
    prompt = get_random_response()
  else:
    prompt = get_user_prompt()

  if "/bye/" in prompt: 
    os.system('clear') 
    return # !!! only for debugging and testing, remove on prod !!!!

  print(f"user prompt: {color(prompt, fore='white')}")
  #history = build_history_string()

  print(color("Thinking...", fore="yellow")) 

  response: ChatResponse = chat(model="yui3:latest", messages=[
  {
    "role": "user",
    "content": f"({response_history}), Here is the current chat message: {prompt}",
  },
  ])
    #print(response["message"]["content"])
    # or access fields directly from the response object

  print(color(f"Reply: {filter_word(response.message.content)}", fore="cyan"))
  print("______________________________________________________")

  play_tts(filter_word(response.message.content).lower())

  response_history.append(f"(MESSAGE user {prompt} MESSAGE assistant {response.message.content})")

  output_text = f'\nMESSAGE user {prompt}\nMESSAGE assistant {response.message.content}'

  with open("history.txt", "a", encoding="utf-8") as f:
      f.write(output_text)

  get_response(False);

def transcribe(audio_path: pathlib.Path, model_name: str = "base"):
  model = whisper.load_model('base')
  result = model.transcribe(str(audio_path))
  return result["text"]

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Whisper batch transcription")
    parser.add_argument("audio", type=pathlib.Path, help="Path to an audio file (any format ffmpeg supports)")
    parser.add_argument("-m", "--model", default="base", help="Whisper model size")
    args = parser.parse_args()

    print("Transcribing …")
    txt = transcribe(args.audio, args.model)
    print("\n--- RESULT ----------------------------------------------------------")
    print(txt)
    # Optional: on Windows enable ANSI handling (colorama does it automatically
    # when you import it, but we’re not using colorama directly here).
    if sys.platform.startswith('win'):
        import os
        os.system('')   # enables VT processing on recent Windows builds
    os.system('clear')
    get_response(False);
#  add ability to interact using voice
#  add ability to respond to users by name and recognize regular users
#  speed up response time
#  convert to python