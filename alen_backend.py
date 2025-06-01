import requests
import asyncio
import edge_tts
import whisper
import tempfile
import sounddevice as sd
import soundfile as sf
import torch
import json
import os
import pyttsx3
import speech_recognition as sr
import webbrowser
import subprocess
import requests
import pyautogui
import ctypes
import datetime
import threading
from stable_baselines3 import PPO
from sentence_transformers import SentenceTransformer
import numpy as np
from queue import Queue
from rapidfuzz import process

PREFERENCES_FILE = "user_preferences.json"
INTERACTIONS_FILE = "interaction_dataset.json"
MEMORY_FILE = "memory.json"
ALIASES_FILE = "custom_aliases.json"

def load_aliases():
    if os.path.exists(ALIASES_FILE):
        with open(ALIASES_FILE, "r") as f:
            return json.load(f)
    return {}

def save_aliases(aliases):
    with open(ALIASES_FILE, "w") as f:
        json.dump(aliases, f, indent=4)

def apply_aliases(text):
    aliases = load_aliases()
    return aliases.get(text.lower().strip(), text)

def load_preferences():
    if os.path.exists(PREFERENCES_FILE):
        with open(PREFERENCES_FILE, "r") as f:
            return json.load(f)
    return {"voice_rate": 180}

def save_preferences(prefs):
    with open(PREFERENCES_FILE, "w") as f:
        json.dump(prefs, f, indent=4)

speech_queue = Queue()

def speak(text):
    speech_queue.put(text)
    if speech_queue.qsize() == 1:
        threading.Thread(target=_speak_loop).start()

def _speak_loop():
    engine = pyttsx3.init()
    prefs = load_preferences()
    engine.setProperty('rate', prefs.get("voice_rate", 180))

    while not speech_queue.empty():
        text = speech_queue.get()
        engine.say(text)
        engine.runAndWait()

def log_interaction(state, action, reward):
    interaction = {
        "state": state,
        "action": action,
        "reward": reward,
        "timestamp": datetime.datetime.now().isoformat()
    }
    if os.path.exists(INTERACTIONS_FILE):
        with open(INTERACTIONS_FILE, "r") as f:
            data = json.load(f)
    else:
        data = []

    data.append(interaction)

    with open(INTERACTIONS_FILE, "w") as f:
        json.dump(data, f, indent=4)

    if len(data) % 20 == 0:
        threading.Thread(target=train_rl_model).start()

def train_rl_model():
    try:
        print("⚙ Training RL model (auto-trigger)...")
        from trainer import train_alen_rl_model
        train_alen_rl_model()
        print("✅ Model trained and saved as alen_rl_model.zip")
    except Exception as e:
        print(f"RL training failed: {e}")


def predict_response_from_model(user_input):
    model_path = "alen_rl_model.zip"
    if not os.path.exists(model_path):
        return None  # Model hasn't been trained yet

    try:
        device = "cpu" 
        model = PPO.load(model_path, device=device)
        encoder = SentenceTransformer("multi-qa-MiniLM-L6-cos-v1", device=device)

        state_vec = encoder.encode(user_input)
        action_idx, _ = model.predict(np.array(state_vec), deterministic=True)

        with open("interaction_dataset.json", "r") as f:
            data = json.load(f)
            actions = list({item["action"] for item in data})
            if action_idx < len(actions):
                return actions[action_idx]
    except Exception as e:
        print(f"RL model prediction failed: {e}")
        return None

    return None

def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return {}
    with open(MEMORY_FILE, "r") as f:
        return json.load(f)

def save_memory(memory):
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=4)

from fuzzywuzzy import fuzz

def memory_response(command, threshold=85):
    command = command.strip().lower()
    memory = load_memory()
    best_match = None
    best_score = 0

    for key in memory.keys():
        score = fuzz.ratio(command, key)
        if score > best_score and score >= threshold:
            best_score = score
            best_match = key

    if best_match:
        return memory[best_match]
    return None


def teach_memory(command, answer):
    memory = load_memory()
    memory[command.lower()] = answer
    save_memory(memory)
    # Save as alias if misheard/shortform
    aliases = load_aliases()
    if answer.lower() != command.lower():
        aliases[command.lower()] = answer.lower()
        save_aliases(aliases)

# Speech-to-text function
def list_audio_devices():
    print(sd.query_devices())

def listen():
    try:
        print("Listening...")
        duration = 3  # seconds
        samplerate = 16000

        # Optional: specify device index
        device_info = sd.query_devices(kind='input')
        print(f"Using input device: {device_info['name']}")

        audio = sd.rec(int(samplerate * duration), samplerate=samplerate, channels=1, dtype='float32')
        sd.wait()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            sf.write(f.name, audio, samplerate)
            model = whisper.load_model("small.en")
            result = model.transcribe(f.name)
            return result["text"]

    except Exception as e:
        return f"Voice recognition error: {e}"




# Check if running as admin
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

# === APP INDEXING CONFIG ===
FOLDER_INDEX_FILE = "folder_index.json"

def build_folder_index():
    base_paths = [
        os.path.expanduser("~"),                   # Home (includes Downloads, Desktop, etc.)
        "C:\\", "D:\\", "E:\\"                     # Common root drives (customize as needed)
    ]
    folders = {}

    for base in base_paths:
        for root, dirs, _ in os.walk(base):
            for folder in dirs:
                folder_name = folder.lower()
                folder_path = os.path.join(root, folder)
                if folder_name not in folders:
                    folders[folder_name] = folder_path
            # Optional: prevent scanning too deep for performance
            break  # Comment this if you want full recursion

    with open(FOLDER_INDEX_FILE, "w") as f:
        json.dump(folders, f, indent=4)
    return folders

def load_folder_index():
    if os.path.exists(FOLDER_INDEX_FILE):
        with open(FOLDER_INDEX_FILE, "r") as f:
            return json.load(f)
    return build_folder_index()


APP_INDEX_FILE = "app_index.json"
START_MENU_PATHS = [
    r"C:\\ProgramData\\Microsoft\\Windows\\Start Menu\\Programs",
    os.path.expandvars(r"%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs")
]



def build_app_index():
    if "WindowsApps" not in root:
        apps[app_name] = os.path.join(root, file)

    apps = {}

    # Include existing Start Menu logic
    for path in START_MENU_PATHS:
        for root, _, files in os.walk(path):
            for file in files:
                if file.lower().endswith(".lnk"):
                    app_name = os.path.splitext(file)[0].lower()
                    apps[app_name] = os.path.join(root, file)

    # NEW: Also scan common folders for .exe files
    additional_paths = [
        os.path.expanduser("~/Desktop"),
        r"C:\Program Files",
        r"C:\Program Files (x86)"
    ]
    for base_path in additional_paths:
        for root, _, files in os.walk(base_path):
            for file in files:
                if file.lower().endswith(".exe"):
                    app_name = os.path.splitext(file)[0].lower()
                    apps[app_name] = os.path.join(root, file)

    with open(APP_INDEX_FILE, "w") as f:
        json.dump(apps, f, indent=4)

    return apps


def load_app_index():
    if os.path.exists(APP_INDEX_FILE):
        with open(APP_INDEX_FILE, "r") as f:
            return json.load(f)
    else:
        return build_app_index()

def find_best_app_match(query, threshold=75):
    apps = load_app_index()
    matches = process.extract(query.lower(), apps.keys(), limit=1, score_cutoff=threshold)
    if matches:
        best = matches[0][0]
        return apps[best]
    return None

def open_app_by_name(app_name):
    path = find_best_app_match(app_name)
    if path:
        os.startfile(path)
        return f"Opening {app_name.title()}."
    return f"Sorry, I couldn't find an app named {app_name}."

def find_best_folder_match(name, threshold=75):
    folders = load_folder_index()
    matches = process.extract(name.lower(), folders.keys(), limit=1, score_cutoff=threshold)
    if matches:
        best_match = matches[0][0]
        return folders[best_match]
    return None

# === HANDLE PC COMMANDS ===
def handle_pc_command(command):
    command = command.lower()
    if command == "update folders":
        build_folder_index()
        return "Folder index updated."

        # Auto-folder detection
    if command.startswith("open ") or command.startswith("launch "):
        target = command.split(" ", 1)[1]

        # Try folder match first
        folder_path = find_best_folder_match(target)
        if folder_path and os.path.isdir(folder_path):
            os.startfile(folder_path)
            return f"Opening folder: {folder_path}"

        # Fallback to app launching
        return open_app_by_name(target)

    # Auto-launch installed apps
    if command.startswith("open ") or command.startswith("launch "):
        app_name = command.split(" ", 1)[1]
        return open_app_by_name(app_name)

    if command == "update apps":
        build_app_index()
        return "App index updated."

    # Keep key system commands
    if "shutdown" in command:
        subprocess.call("shutdown /s /t 1")
        return "Shutting down the system."
    elif "restart" in command:
        subprocess.call("shutdown /r /t 1")
        return "Restarting the system."
    elif "lock" in command:
        os.system("rundll32.exe user32.dll,LockWorkStation")
        return "Locking the system."
    elif "mute" in command:
        pyautogui.press("volumemute")
        return "Muting volume."
    elif "increase volume" in command:
        pyautogui.press("volumeup")
        return "Increasing volume."
    elif "decrease volume" in command:
        pyautogui.press("volumedown")
        return "Decreasing volume."
    elif "time" in command:
        now = datetime.datetime.now()
        current_time = now.strftime("%I:%M %p")
        return f"The current time is {current_time}."

    return None

# OPTIONAL: In main() or init, ensure app index is built at least once
if not os.path.exists(APP_INDEX_FILE):
    build_app_index()

if not os.path.exists(FOLDER_INDEX_FILE):
    print("📁 Building folder index...")
    build_folder_index()


# DuckDuckGo search fallback
def trim_response(text):
    # Split by full stops
    sentences = text.split('.')
    # Take first 2 non-empty sentences
    short_sentences = [s.strip() for s in sentences if s.strip()]
    short_text = '. '.join(short_sentences[:2])
    return short_text + '.' if short_text else "Sorry, I couldn't find anything useful."

def search_duckduckgo(query):
    url = "https://api.duckduckgo.com/"
    params = {
        "q": query,
        "format": "json",
        "no_redirect": 1,
        "no_html": 1,
        "skip_disambig": 1
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    try:
        response = requests.get(url, params=params, headers=headers, timeout=5)  # timeout in seconds
        data = response.json()

        for key in ["Answer", "Definition", "Abstract"]:
            if data.get(key):
                return trim_response(data[key])

        for topic in data.get("RelatedTopics", []):
            if isinstance(topic, dict) and "Text" in topic:
                return trim_response(topic["Text"])

        return "Sorry, I couldn't find anything useful."
    except requests.exceptions.Timeout:
        return "DuckDuckGo search timed out. Check your internet connection."
    except Exception as e:
        return f"Search error: {str(e)}"

    
    
# Main function
def main():
    if not is_admin():
        print("⚠ Warning: Run this assistant as administrator to access all features (like Task Manager).")
    speak("Hello, how can I help you?")
    last_command = ""

    while True:
        input_method = input("Type '1' for text or '2' for voice: ")

        if input_method == '2':
            command = listen()
            is_voice = True
        else:
            command = input("You: ")
            is_voice = False

        if not command or command.lower() == last_command:
            continue

        last_command = command.lower()
        print("You:", command)

        memory = memory_response(command)
        if memory:
            print("ALEN:", memory)
            if is_voice:
                speak(memory)
            continue

        pc_reply = handle_pc_command(command)
        if pc_reply:
            print("ALEN:", pc_reply)
            if is_voice:
                speak(pc_reply)
            continue

        search_reply = search_duckduckgo(command)
        print("ALEN:", search_reply)
        if is_voice:
            speak(search_reply)

        if search_reply == "Sorry, I couldn't find anything useful.":
            user_answer = input("Can you please tell me what it means so I can remember? ")
            teach_memory(command, user_answer)
            print("Thanks! I’ll remember that.")
            if is_voice:
                speak("Thanks! I’ll remember that.")


if __name__ == "__main__":
    main()
