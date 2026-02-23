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

# --- НАСТРОЙКИ ---
SETTINGS_FILE = "settings.json"
TERMS_FILE = "my_terms.txt"
DEFAULT_SETTINGS = {
    "hotkey_fix": "ctrl+alt+k",  # Сменили на стабильную кнопку
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
    
    # Самая стабильная проверка: 
    # Если слова нет в исключениях И (оно короткое ИЛИ его нет в англ. словаре) -> ПЕРЕВОДИМ
    if clean not in whitelist and (len(clean) <= 2 or clean not in spell):
        return word.translate(to_rus)
    return word

def convert_smart():
    # Короткая пауза, чтобы система "заметила" выделение
    time.sleep(0.2)
    
    # Копируем
    keyboard.press_and_release('ctrl+c')
    time.sleep(0.1)
    
    text = pyperclip.paste()
    if not text: return

    whitelist = get_saved_terms()
    words_and_spaces = re.split(r'(\s+)', text)
    
    # Переводим по словам (та самая стабильная версия)
    result = [fix_word(i, whitelist) if not i.isspace() else i for i in words_and_spaces]
    
    pyperclip.copy("".join(result))
    time.sleep(0.1)
    keyboard.press_and_release('ctrl+v')

# --- ИНТЕРФЕЙС И СИНХРОНИЗАЦИЯ ---
def sync_with_sheets():
    url = config.get("sheets_url")
    if not url: return
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            cloud = {l.strip().lower() for l in r.text.splitlines() if l.strip()}
            with open(TERMS_FILE, "w", encoding="utf-8") as f:
                for w in sorted(get_saved_terms().union(cloud)):
                    f.write(w + "\n")
    except: pass

def setup_tray():
    icon_path = "main_icon.ico"
    img = Image.open(icon_path) if os.path.exists(icon_path) else Image.new('RGB', (64, 64), (0, 120, 215))
    
    menu = pystray.Menu(
        item('Синхронизировать', lambda: sync_with_sheets()),
        item('Настройки', lambda: os.startfile(SETTINGS_FILE)),
        item('О программе', lambda: messagebox.showinfo("ABRA", "Ctrl+Alt+K — исправить")),
        item('Выход', lambda icon: [icon.stop(), os._exit(0)])
    )
    pystray.Icon("abra", img, "ABRA", menu).run()

if __name__ == "__main__":
    # Регистрируем кнопки без лишних усложнений
    keyboard.add_hotkey(config["hotkey_fix"], convert_smart)
    keyboard.add_hotkey(config["hotkey_add"], lambda: [keyboard.press_and_release('ctrl+c'), time.sleep(0.1), 
                        open(TERMS_FILE, "a").write(pyperclip.paste().strip().lower() + "\n")])
    
    sync_with_sheets()
    setup_tray()