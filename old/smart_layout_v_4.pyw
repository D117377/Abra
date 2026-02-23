import pyperclip
import keyboard
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

DEFAULT_SETTINGS = {
    "hotkey_fix": "ctrl+alt+k",
    "hotkey_add": "ctrl+alt+a",
    "sheets_url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vTsX55LrgXf9NN4MWhgVbPSvRYsmZyIEgV1jHTt50Lp2EU7pnpLLg6U5ELQQHb9Qw4xGObRyQIexFFc/pub?gid=0&single=true&output=csv"
}

# --- ЛОГИРОВАНИЕ ---
def log(message):
    """Пишет сообщение в консоль и в файл с временем"""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    text = f"[{timestamp}] {message}"
    print(text)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(text + "\n")
    except Exception as e:
        print(f"Ошибка записи лога: {e}")

def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_SETTINGS, f, indent=4)
        return DEFAULT_SETTINGS
    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

log("--- ЗАПУСК ПРОГРАММЫ ---")
config = load_settings()
log("Настройки загружены.")
spell = SpellChecker(language='en')
log("Словарь проверки орфографии загружен.")

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
    log("\n=== НАЖАТ ХОТКЕЙ: НАЧИНАЮ РАБОТУ ===")
    
    # 1. Ждем
    log("Шаг 1: Пауза 0.4 сек (ждем отпускания клавиш)...")
    time.sleep(0.4)
    
    # 2. Очищаем
    log("Шаг 2: Очищаю буфер обмена...")
    pyperclip.copy("")
    
    # 3. Копируем
    log("Шаг 3: Отправляю сигнал Ctrl+C...")
    keyboard.send('ctrl+c')
    
    # 4. Цикл ожидания
    log("Шаг 4: Начинаю ждать текст в буфере (макс 1 сек)...")
    text = ""
    for i in range(20): # 20 попыток * 0.05 сек = 1 сек
        try:
            temp_text = pyperclip.paste()
            if temp_text:
                text = temp_text
                log(f"   -> Попытка {i+1}: Текст пойман! (Длина: {len(text)} симв.)")
                break
            else:
                # Раскомментируй строку ниже, если хочешь видеть каждую пустую попытку
                # log(f"   -> Попытка {i+1}: Пусто...") 
                time.sleep(0.05)
        except Exception as e:
            log(f"   -> Ошибка доступа к буферу: {e}")
            time.sleep(0.05)
    
    if not text: 
        log("ОШИБКА: Время вышло. Текст так и не появился в буфере.")
        log("=== ЗАВЕРШЕНИЕ С ОШИБКОЙ ===\n")
        return

    log(f"Шаг 5: Анализ текста: '{text[:20]}...'") # Показываем первые 20 символов
    whitelist = get_saved_terms()
    words_and_spaces = re.split(r'(\s+)', text)
    
    result = [fix_word(i, whitelist) if not i.isspace() else i for i in words_and_spaces]
    final_text = "".join(result)
    
    log(f"Шаг 6: Результат перевода: '{final_text[:20]}...'")
    
    pyperclip.copy(final_text)
    log("Шаг 7: Результат скопирован в буфер. Жду 0.2 сек...")
    
    time.sleep(0.2)
    log("Шаг 8: Отправляю Ctrl+V...")
    keyboard.send('ctrl+v')
    log("=== ГОТОВО ===\n")

# --- ИНТЕРФЕЙС ---
def sync_with_sheets():
    log("Запуск синхронизации...")
    url = config.get("sheets_url")
    if not url: 
        log("Нет URL для таблицы.")
        return
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            cloud = {l.strip().lower() for l in r.text.splitlines() if l.strip()}
            local = get_saved_terms()
            total = sorted(local.union(cloud))
            with open(TERMS_FILE, "w", encoding="utf-8") as f:
                for w in total:
                    f.write(w + "\n")
            log(f"Синхронизация успешна. Всего слов: {len(total)}")
        else:
            log(f"Ошибка сервера: {r.status_code}")
    except Exception as e: 
        log(f"Ошибка синхронизации: {e}")

def setup_tray():
    log("Запуск иконки в трее...")
    icon_path = "main_icon.ico"
    if os.path.exists(icon_path):
        img = Image.open(icon_path) 
    else:
        img = Image.new('RGB', (64, 64), (0, 120, 215))
    
    menu = pystray.Menu(
        item('Синхронизировать', lambda: sync_with_sheets()),
        item('Настройки', lambda: os.startfile(SETTINGS_FILE)),
        item('Открыть Лог', lambda: os.startfile(LOG_FILE) if os.path.exists(LOG_FILE) else None),
        item('О программе', lambda: messagebox.showinfo("ABRA", "Ctrl+Alt+K — исправить")),
        item('Выход', lambda icon: [log("Выход из программы"), icon.stop(), os._exit(0)])
    )
    pystray.Icon("abra", img, "ABRA", menu).run()

if __name__ == "__main__":
    try:
        # Регистрируем горячие клавиши
        keyboard.add_hotkey(config["hotkey_fix"], convert_smart)
        
        keyboard.add_hotkey(config["hotkey_add"], lambda: [
            log("Хоткей: Добавление слова"),
            keyboard.send('ctrl+c'), 
            time.sleep(0.1),
            log(f"Добавляю слово: {pyperclip.paste().strip().lower()}"),
            open(TERMS_FILE, "a", encoding="utf-8").write(pyperclip.paste().strip().lower() + "\n")
        ])
        
        sync_with_sheets()
        setup_tray()
    except Exception as e:
        log(f"КРИТИЧЕСКАЯ ОШИБКА ПРИ ЗАПУСКЕ: {e}")