import pyperclip
import pyautogui
import time
import re
import os
import json
import requests
import threading
from datetime import datetime
from spellchecker import SpellChecker
from PIL import Image
import pystray
from pystray import MenuItem as item
from tkinter import messagebox
from pynput import keyboard as pk # Новая библиотека-слушатель

# --- НАСТРОЙКИ ---
SETTINGS_FILE = "settings.json"
TERMS_FILE = "my_terms.txt"
LOG_FILE = "abra_log.txt"

# Отключаем защиту, чтобы мышь в углу не крашила скрипт
pyautogui.FAILSAFE = False 

DEFAULT_SETTINGS = {
    # В pynput формат хоткеев немного другой: <ctrl>+<alt>+k
    # Но мы будем использовать константы ниже
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

log("--- ЗАПУСК ВЕРСИИ PYNPUT ---")
config = load_settings()
spell = SpellChecker(language='en')

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
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

# --- ОСНОВНАЯ ЛОГИКА ---
def work_cycle():
    """Функция, которая выполняется при нажатии хоткея"""
    log("\n=== АКТИВАЦИЯ (Pynput) ===")
    
    # 1. Важно: принудительно "отпускаем" клавиши-модификаторы программно.
    # Если ты держишь Ctrl физически, скрипт может не сработать.
    pyautogui.keyUp('ctrl')
    pyautogui.keyUp('alt')
    pyautogui.keyUp('shift')
    
    # 2. Очищаем буфер
    pyperclip.copy("")
    
    # 3. Копируем (Ctrl+C)
    log("Жму Ctrl+C...")
    
    # Делаем это медленно и надежно
    pyautogui.keyDown('ctrl')
    time.sleep(0.05)
    pyautogui.press('c')
    time.sleep(0.05)
    pyautogui.keyUp('ctrl')
    
    # 4. Ждем текст
    text = ""
    for i in range(15): 
        try:
            text = pyperclip.paste()
            if text: break
        except: pass
        time.sleep(0.05)
    
    if not text:
        log("ОШИБКА: Буфер пуст. Не выделил текст или система блокирует?")
        return

    log(f"Текст получен: {text[:15]}...")
    
    whitelist = get_saved_terms()
    words_and_spaces = re.split(r'(\s+)', text)
    result = [fix_word(i, whitelist) if not i.isspace() else i for i in words_and_spaces]
    final_text = "".join(result)
    
    pyperclip.copy(final_text)
    time.sleep(0.1)
    
    log("Вставляю результат...")
    pyautogui.keyDown('ctrl')
    time.sleep(0.05)
    pyautogui.press('v')
    time.sleep(0.05)
    pyautogui.keyUp('ctrl')
    log("Готово.")

def add_word_cycle():
    """Логика добавления слова"""
    log("Добавление слова...")
    pyautogui.keyUp('ctrl')
    pyautogui.keyUp('alt')
    
    pyperclip.copy("")
    pyautogui.hotkey('ctrl', 'c')
    time.sleep(0.2)
    
    text = pyperclip.paste().strip().lower()
    if text:
        with open(TERMS_FILE, "a", encoding="utf-8") as f:
            f.write(text + "\n")
        log(f"Слово '{text}' сохранено.")
    else:
        log("Не удалось скопировать слово для сохранения.")

# --- ОБРАБОТЧИКИ ХОТКЕЕВ ---
# Pynput запускает это в отдельном потоке, поэтому нам не нужно блокировать основной код
def on_activate_fix():
    # Запускаем в отдельном потоке, чтобы слушатель клавиш не завис
    threading.Thread(target=work_cycle).start()

def on_activate_add():
    threading.Thread(target=add_word_cycle).start()

# --- ИНТЕРФЕЙС И ЗАПУСК ---
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
            log(f"Словарь обновлен. Всего слов: {len(local.union(cloud))}")
    except Exception as e: log(f"Ошибка сети: {e}")

def setup_tray():
    icon_path = "main_icon.ico"
    img = Image.open(icon_path) if os.path.exists(icon_path) else Image.new('RGB', (64, 64), (0, 120, 215))
    
    menu = pystray.Menu(
        item('Синхронизировать', lambda: sync_with_sheets()),
        item('Настройки', lambda: os.startfile(SETTINGS_FILE)),
        item('Лог', lambda: os.startfile(LOG_FILE) if os.path.exists(LOG_FILE) else None),
        item('Выход', lambda icon: [icon.stop(), os._exit(0)])
    )
    pystray.Icon("abra", img, "ABRA", menu).run()

if __name__ == "__main__":
    try:
        # ЗАПУСК СЛУШАТЕЛЯ КЛАВИШ
        # Формат: <модификатор>+<кнопка>
        # Важно: pynput чувствителен к регистру и раскладке.
        # Мы слушаем именно физические коды.
        hotkeys = pk.GlobalHotKeys({
            '<ctrl>+<alt>+k': on_activate_fix,
            '<ctrl>+<alt>+a': on_activate_add
        })
        hotkeys.start() # Запускаем в фоне
        log("Слушатель клавиш запущен (Pynput). Жду Ctrl+Alt+K...")
        
        sync_with_sheets()
        setup_tray() # Это блокирует основной поток, пока иконка висит
        
    except Exception as e:
        log(f"КРИТИЧЕСКАЯ ОШИБКА: {e}")