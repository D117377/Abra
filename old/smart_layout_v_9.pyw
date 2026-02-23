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
import tkinter as tk
from tkinter import messagebox
import webbrowser
from pynput import keyboard as pk

# --- НАСТРОЙКИ ---
SETTINGS_FILE = "settings.json"
TERMS_FILE = "my_terms.txt"
LOG_FILE = "abra_log.txt"

# Глобальная переменная для иконки, чтобы вызывать уведомления из любой функции
tray_icon = None 

# Отключаем защиту PyAutoGUI
pyautogui.FAILSAFE = False 

DEFAULT_SETTINGS = {
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

log("--- ЗАПУСК ВЕРСИИ С ТУЛТИПОМ (v9) ---")
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

def analyze_context(text):
    words = [re.sub(r'[^\w]', '', w.lower()) for w in re.split(r'\s+', text) if w.strip()]
    valid_eng = 0
    gibberish = 0
    for w in words:
        if not w: continue
        if len(w) > 2 and w in spell:
            valid_eng += 1
        else:
            gibberish += 1
    is_mostly_rus = gibberish >= valid_eng
    log(f"Анализ: Англ={valid_eng}, Мусор={gibberish} -> Тотальный перевод: {is_mostly_rus}")
    return is_mostly_rus

def fix_word(word, whitelist, force_translate):
    clean = re.sub(r'[^\w]', '', word.lower())
    if clean in whitelist: return word
    if force_translate: return word.translate(to_rus)
    if not clean or len(clean) <= 2 or clean not in spell:
        return word.translate(to_rus)
    return word

def perform_copy():
    pyautogui.hotkey('ctrl', 'c', interval=0.15)
    for _ in range(10):
        if pyperclip.paste(): return True
        time.sleep(0.05)
    return False

def show_notification(title, message):
    """Показывает всплывающее уведомление над треем"""
    if tray_icon:
        try:
            tray_icon.notify(message, title)
        except Exception as e:
            log(f"Ошибка уведомления: {e}")

def work_cycle():
    log("\n=== АКТИВАЦИЯ ===")
    
    # 0. Показываем "АБРАКАДАБРА!" сразу, чтобы ты видел, что процесс пошел
    show_notification("АБРАКАДАБРА!", "Колдую над текстом...")
    
    # 1. Сброс клавиш
    time.sleep(0.3)
    pyautogui.keyUp('ctrl')
    pyautogui.keyUp('alt')
    pyautogui.keyUp('shift')
    
    pyperclip.copy("")
    
    # 2. Копирование
    log("Копирую...")
    if not perform_copy():
        log("Не вышло. Пробую альтернативу...")
        pyautogui.hotkey('ctrl', 'insert', interval=0.15)
        time.sleep(0.5)
    
    text = pyperclip.paste()
    if not text:
        log("ОШИБКА: Буфер пуст.")
        return

    # 3. Обработка
    should_translate_all = analyze_context(text)
    whitelist = get_saved_terms()
    words_and_spaces = re.split(r'(\s+)', text)
    result = [fix_word(i, whitelist, should_translate_all) if not i.isspace() else i for i in words_and_spaces]
    final_text = "".join(result)
    
    pyperclip.copy(final_text)
    
    # 4. Вставка
    log("Вставляю...")
    pyautogui.hotkey('ctrl', 'v', interval=0.1)
    log("Готово.")

def add_word_cycle():
    log("Добавление слова...")
    pyautogui.keyUp('ctrl')
    pyautogui.keyUp('alt')
    pyperclip.copy("")
    
    pyautogui.hotkey('ctrl', 'c', interval=0.15)
    time.sleep(0.3)
    
    text = pyperclip.paste().strip().lower()
    if text:
        clean_text = re.sub(r'[^\w]', '', text) 
        if clean_text:
            with open(TERMS_FILE, "a", encoding="utf-8") as f:
                f.write(clean_text + "\n")
            log(f"Слово '{clean_text}' сохранено.")
            show_notification("АБРАКАДАБРА", f"Слово '{clean_text}' добавлено в исключения!")
    else:
        log("Не удалось скопировать.")

def on_activate_fix():
    threading.Thread(target=work_cycle).start()

def on_activate_add():
    threading.Thread(target=add_word_cycle).start()

# --- МЕНЮ И ОКНА ---
def show_about():
    help_text = (
        "ABRA — Переключатель раскладки\n\n"
        "КАК ПОЛЬЗОВАТЬСЯ:\n"
        "1. Выделите текст.\n"
        "2. Нажмите Ctrl+Alt+K.\n"
        "3. Текст станет русским.\n\n"
        "ИСКЛЮЧЕНИЯ:\n"
        "Если нужно сохранить английское слово (например, 'Render'), "
        "выделите его и нажмите Ctrl+Alt+A."
    )
    threading.Thread(target=lambda: messagebox.showinfo("О программе", help_text)).start()

def show_author():
    donation_url = "https://pay.cloudtips.ru/p/dfa5bb67"
    info = (
        "Автор: Видеограф и монтажер.\n"
        "Написал этот инструмент, чтобы сэкономить время.\n" \
        "Если программа не работает - пишите на doobygh@yandex.ru \n\n"
        "Если программа помогла, буду рад донату!"
    )
    def open_url():
        if messagebox.askyesno("Поддержать автора", info + "\n\nПерейти к донату?"):
            webbrowser.open(donation_url)
    threading.Thread(target=open_url).start()

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
            log(f"Синхронизация OK.")
            show_notification("АБРАКАДАБРА", "Словарь успешно обновлен!")
    except Exception as e: log(f"Ошибка: {e}")

def setup_tray():
    global tray_icon # Используем глобальную переменную
    icon_path = "main_icon.ico"
    img = Image.open(icon_path) if os.path.exists(icon_path) else Image.new('RGB', (64, 64), (0, 120, 215))
    
    menu = pystray.Menu(
        item('Синхронизировать', lambda: sync_with_sheets()),
        item('Настройки', lambda: os.startfile(SETTINGS_FILE)),
        item('Лог', lambda: os.startfile(LOG_FILE) if os.path.exists(LOG_FILE) else None),
        pystray.Menu.SEPARATOR,
        item('О программе', lambda: show_about()),
        item('Автор (Донат)', lambda: show_author()),
        pystray.Menu.SEPARATOR,
        item('Выход', lambda icon: [icon.stop(), os._exit(0)])
    )
    
    tray_icon = pystray.Icon("abra", img, "ABRA", menu)
    tray_icon.run()

if __name__ == "__main__":
    try:
        root = tk.Tk()
        root.withdraw()
        
        hotkeys = pk.GlobalHotKeys({
            '<ctrl>+<alt>+k': on_activate_fix,
            '<ctrl>+<alt>+a': on_activate_add
        })
        hotkeys.start()
        log("Слушатель запущен. Жду Ctrl+Alt+K...")
        
        threading.Thread(target=sync_with_sheets).start()
        setup_tray()
    except Exception as e:
        log(f"CRITICAL ERROR: {e}")