import pyperclip
import keyboard
import pyautogui  # <-- Новая библиотека для нажатий
import time
import re
import os
import json
import requests
from datetime import datetime
from spellchecker import SpellChecker
from PIL import Image
import pystray
from pystray import MenuItem as item
import tkinter as tk
from tkinter import messagebox
import webbrowser

# --- НАСТРОЙКИ ---
SETTINGS_FILE = "settings.json"
TERMS_FILE = "my_terms.txt"
LOG_FILE = "abra_log.txt"

# Отключаем защиту pyautogui (чтобы мышь в углу не крашила скрипт)
pyautogui.FAILSAFE = False 

DEFAULT_SETTINGS = {
    "hotkey_fix": "ctrl+alt+k", 
    "hotkey_add": "ctrl+alt+a",
    "sheets_url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vTsX55LrgXf9NN4MWhgVbPSvRYsmZyIEgV1jHTt50Lp2EU7pnpLLg6U5ELQQHb9Qw4xGObRyQIexFFc/pub?gid=0&single=true&output=csv"
}

# --- ЛОГИРОВАНИЕ ---
def log(message):
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    text = f"[{timestamp}] {message}"
    print(text)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(text + "\n")
    except: pass

def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_SETTINGS, f, indent=4)
        return DEFAULT_SETTINGS
    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

log("--- ЗАПУСК ВЕРСИИ PYAUTOGUI ---")
config = load_settings()
spell = SpellChecker(language='en')

# --- ЛОГИКА ---
eng_chars = "qwertyuiop[]asdfghjkl;'zxcvbnm,./QWERTYUIOP{}ASDFGHJKL:\"ZXCVBNM<>?@#$^&"
rus_chars = "йцукенгшщзхъфывапролджэячсмитьбю.ЙЦУКЕНГШЩЗХЪФЫВАПРОЛДЖЭЯЧСМИТЬБЮ,№;:??"
to_rus = str.maketrans(eng_chars, rus_chars)

def get_saved_terms():
    if not os.path.exists(TERMS_FILE): return set()
    with open(TERMS_FILE, "r", encoding="utf-8") as f:
        return {line.strip().lower() for line in f if line.strip()}

def fix_word(word, whitelist):
    clean = re.sub(r'[^\w]', '', word.lower())
    if not clean: return word
    if clean not in whitelist and (len(clean) <= 2 or clean not in spell):
        return word.translate(to_rus)
    return word

def convert_smart():
    log("\n=== РАБОТАЕМ (PYAUTOGUI) ===")
    
    # 1. Ждем отпускания клавиш
    time.sleep(0.4)
    
    # 2. Очищаем буфер
    pyperclip.copy("")
    
    # 3. Копируем через PyAutoGUI (это должно решить проблему громкости)
    log("Нажимаю Ctrl+C через PyAutoGUI...")
    try:
        # Мы явно говорим: зажми ctrl, нажми c, отпусти всё
        pyautogui.hotkey('ctrl', 'c') 
    except Exception as e:
        log(f"ОШИБКА PyAutoGUI: {e}")
        return
    
    # 4. Ждем текст
    text = ""
    for i in range(20): 
        text = pyperclip.paste()
        if text:
            log(f"Текст пойман на попытке {i+1}")
            break
        time.sleep(0.05)
    
    if not text: 
        log("ОШИБКА: Буфер пуст. Громкость всё еще скачет?")
        return

    whitelist = get_saved_terms()
    words_and_spaces = re.split(r'(\s+)', text)
    result = [fix_word(i, whitelist) if not i.isspace() else i for i in words_and_spaces]
    final_text = "".join(result)
    
    pyperclip.copy(final_text)
    
    log("Вставляю результат...")
    time.sleep(0.2)
    pyautogui.hotkey('ctrl', 'v')
    log("Готово.")

# --- ИНТЕРФЕЙС ---
def sync_with_sheets():
    log("Синхронизация...")
    url = config.get("sheets_url")
    if not url: return
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            cloud = {l.strip().lower() for l in r.text.splitlines() if l.strip()}
            local = get_saved_terms()
            with open(TERMS_FILE, "w", encoding="utf-8") as f:
                for w in sorted(local.union(cloud)): f.write(w + "\n")
            log("Словарь обновлен.")
    except Exception as e: log(f"Ошибка сети: {e}")

def setup_tray():
    icon_path = "main_icon.ico"
    if os.path.exists(icon_path):
        img = Image.open(icon_path) 
    else:
        img = Image.new('RGB', (64, 64), (0, 120, 215))
    
    menu = pystray.Menu(
        item('Синхронизировать', lambda: sync_with_sheets()),
        item('Настройки', lambda: os.startfile(SETTINGS_FILE)),
        item('Лог', lambda: os.startfile(LOG_FILE) if os.path.exists(LOG_FILE) else None),
        item('Выход', lambda icon: [icon.stop(), os._exit(0)])
    )
    pystray.Icon("abra", img, "ABRA", menu).run()

if __name__ == "__main__":
    try:
        # Для горячих клавиш оставляем keyboard, так как он лучше слушает
        # Но добавим suppress=False (по умолчанию), чтобы не блокировать ввод
        keyboard.add_hotkey(config["hotkey_fix"], convert_smart)
        
        keyboard.add_hotkey(config["hotkey_add"], lambda: [
            pyautogui.hotkey('ctrl', 'c'),
            time.sleep(0.1),
            open(TERMS_FILE, "a", encoding="utf-8").write(pyperclip.paste().strip().lower() + "\n"),
            log("Слово добавлено")
        ])
        
        sync_with_sheets()
        setup_tray()
    except Exception as e:
        log(f"CRITICAL ERROR: {e}")