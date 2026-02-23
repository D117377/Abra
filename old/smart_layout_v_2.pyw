import pyperclip
import keyboard
import time
import re
import os
import json
import requests
from spellchecker import SpellChecker
from PIL import Image
import pystray
from pystray import MenuItem as item
import tkinter as tk
from tkinter import messagebox
import webbrowser

# --- КОНФИГУРАЦИЯ ---
SETTINGS_FILE = "settings.json"
TERMS_FILE = "my_terms.txt"

DEFAULT_SETTINGS = {
    "hotkey_fix": "ctrl+alt+q",
    "hotkey_add": "ctrl+alt+a",
    "sheets_url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vTsX55LrgXf9NN4MWhgVbPSvRYsmZyIEgV1jHTt50Lp2EU7pnpLLg6U5ELQQHb9Qw4xGObRyQIexFFc/pub?gid=0&single=true&output=csv"
}

def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_SETTINGS, f, indent=4)
        return DEFAULT_SETTINGS
    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

config = load_settings()
spell = SpellChecker(language='en')

# --- ЛОГИКА ---

def get_saved_terms():
    if not os.path.exists(TERMS_FILE): return set()
    with open(TERMS_FILE, "r", encoding="utf-8") as f:
        return {line.strip().lower() for line in f if line.strip()}

eng_chars = "qwertyuiop[]asdfghjkl;'zxcvbnm,./QWERTYUIOP{}ASDFGHJKL:\"ZXCVBNM<>?@#$^&"
rus_chars = "йцукенгшщзхъфывапролджэячсмитьбю.ЙЦУКЕНГШЩЗХЪФЫВАПРОЛДЖЭЯЧСМИТЬБЮ,№;:??"
to_rus = str.maketrans(eng_chars, rus_chars)

def fix_word(word, whitelist, force_translate=False):
    clean = re.sub(r'[^\w]', '', word.lower())
    if clean in whitelist or clean.isdigit(): return word
    if force_translate or not clean or len(clean) <= 2 or clean not in spell:
        return word.translate(to_rus)
    return word

def convert_smart():
    # 1. Ждем долю секунды, чтобы буфер "успокоился"
    time.sleep(0.2)
    
    # Очищаем буфер обмена
    pyperclip.copy("")
    
    # 2. Имитируем Ctrl+C максимально надежно
    keyboard.press('ctrl')
    keyboard.press('c')
    time.sleep(0.1)
    keyboard.release('c')
    keyboard.release('ctrl')
    
    # 3. Ждем появления текста
    text = ""
    for _ in range(10): # 10 попыток по 0.05 сек
        text = pyperclip.paste()
        if text: break
        time.sleep(0.05)
    
    if not text:
        print("DEBUG: Текст не скопирован. Попробуйте выделить еще раз.")
        return

    whitelist = get_saved_terms()
    words_and_spaces = re.split(r'(\s+)', text)
    
    # Анализ контекста
    only_words = [re.sub(r'[^\w]', '', w.lower()) for w in words_and_spaces if not w.isspace() and w]
    gib_count = sum(1 for w in only_words if len(w) <= 2 or w not in spell)
    eng_count = len(only_words) - gib_count
    
    is_mostly_gib = gib_count >= eng_count
    
    result = [fix_word(i, whitelist, is_mostly_gib) if not i.isspace() else i for i in words_and_spaces]
    
    pyperclip.copy("".join(result))
    time.sleep(0.1)
    
    # 4. Вставляем обратно
    keyboard.press('ctrl')
    keyboard.press('v')
    time.sleep(0.1)
    keyboard.release('v')
    keyboard.release('ctrl')

# --- ОСТАЛЬНОЕ ---

def sync_with_sheets():
    url = config.get("sheets_url")
    if not url: return
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            cloud = {l.strip().lower() for l in r.text.splitlines() if l.strip()}
            local = get_saved_terms()
            with open(TERMS_FILE, "w", encoding="utf-8") as f:
                for w in sorted(local.union(cloud)): f.write(w + "\n")
            print("Словарь обновлен!")
    except: print("Ошибка связи с таблицей")

def setup_tray():
    icon_path = "main_icon.ico"
    img = Image.open(icon_path) if os.path.exists(icon_path) else Image.new('RGB', (64, 64), (0, 120, 215))
    
    menu = pystray.Menu(
        item('Синхронизировать', lambda: sync_with_sheets()),
        item('Настройки', lambda: os.startfile(SETTINGS_FILE)),
        item('О программе', lambda: messagebox.showinfo("ABRA", "Выделите текст и жмите " + config["hotkey_fix"])),
        item('Выход', lambda icon: [icon.stop(), os._exit(0)])
    )
    pystray.Icon("abra", img, "ABRA", menu).run()

if __name__ == "__main__":
    # РЕГИСТРАЦИЯ С SUPPRESS=TRUE (блокирует влияние на систему)
    try:
        keyboard.add_hotkey(config["hotkey_fix"], convert_smart, suppress=True)
        keyboard.add_hotkey(config["hotkey_add"], lambda: [time.sleep(0.2), keyboard.press_and_release('ctrl+c'), time.sleep(0.1), 
                            open(TERMS_FILE, "a").write(pyperclip.paste().strip().lower() + "\n")], suppress=True)
    except Exception as e:
        print(f"Ошибка бинда клавиш: {e}")
        
    sync_with_sheets()
    setup_tray()