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

# Настройки по умолчанию
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

# --- ЛОГИКА СИНХРОНИЗАЦИИ ---

def sync_with_sheets():
    """Скачивает слова из Google Таблицы и добавляет их в локальный файл"""
    url = config.get("sheets_url")
    if not url or "google" not in url:
        print("Ссылка на таблицу не настроена.")
        return

    try:
        response = requests.get(url)
        if response.status_code == 200:
            # Читаем слова из таблицы, очищаем от лишних пробелов
            cloud_words = {line.strip().lower() for line in response.text.splitlines() if line.strip()}
            
            # Читаем текущие локальные слова
            local_words = get_saved_terms()
            
            # Объединяем их
            all_words = local_words.union(cloud_words)
            
            with open(TERMS_FILE, "w", encoding="utf-8") as f:
                for word in sorted(all_words):
                    f.write(word + "\n")
            print("Словарь успешно синхронизирован с облаком!")
    except Exception as e:
        print(f"Ошибка синхронизации: {e}")

# --- ОСТАЛЬНАЯ ЛОГИКА (БЕЗ ИЗМЕНЕНИЙ) ---

def get_saved_terms():
    if not os.path.exists(TERMS_FILE): return set()
    with open(TERMS_FILE, "r", encoding="utf-8") as f:
        return {line.strip().lower() for line in f if line.strip()}

eng_chars = "qwertyuiop[]asdfghjkl;'zxcvbnm,./QWERTYUIOP{}ASDFGHJKL:\"ZXCVBNM<>?@#$^&"
rus_chars = "йцукенгшщзхъфывапролджэячсмитьбю.ЙЦУКЕНГШЩЗХЪФЫВАПРОЛДЖЭЯЧСМИТЬБЮ,№;:??"
to_rus = str.maketrans(eng_chars, rus_chars)

def add_to_whitelist():
    time.sleep(0.1)
    keyboard.press_and_release('ctrl+c')
    time.sleep(0.1)
    new_word = pyperclip.paste().strip().lower()
    if new_word:
        saved_terms = get_saved_terms()
        if new_word not in saved_terms:
            with open(TERMS_FILE, "a", encoding="utf-8") as f:
                f.write(new_word + "\n")

def fix_word(word, whitelist, force_translate=False):
    # Очищаем слово от символов ТОЛЬКО для проверки в словаре
    clean = re.sub(r'[^\w]', '', word.lower())
    
    # 1. Если это число или твой проф. термин (Adobe/C4D) - НЕ ТРОГАЕМ
    if clean in whitelist or clean.isdigit():
        return word

    # 2. Если мы в режиме "Тотального перевода" (мусора больше, чем англ.)
    # или если слово слишком короткое/его нет в словаре - ПЕРЕВОДИМ
    # Теперь переводится всё слово целиком со всеми скобками [ ] и т.д.
    if force_translate or not clean or len(clean) <= 2 or clean not in spell:
        return word.translate(to_rus)
        
    return word

def convert_smart():
    # Умное ожидание: ждем, пока ты отпустишь ВСЕ клавиши-модификаторы
    # Это решает проблему с порядком нажатия Ctrl/Alt/Q
    while keyboard.is_pressed('ctrl') or keyboard.is_pressed('alt') or keyboard.is_pressed('shift'):
        time.sleep(0.05)
    
    # Небольшая страховочная пауза после отпускания
    time.sleep(0.1)
    
    pyperclip.copy("")
    keyboard.press_and_release('ctrl+c')
    
    # Ждем текст в буфере
    timeout = time.time() + 0.6
    while not pyperclip.paste() and time.time() < timeout:
        time.sleep(0.05)
    
    text = pyperclip.paste()
    if not text: 
        print("DEBUG: Текст не скопирован.")
        return

    whitelist = get_saved_terms()
    words_and_spaces = re.split(r'(\s+)', text)
    
    # Анализ контекста
    only_words = [re.sub(r'[^\w]', '', w.lower()) for w in words_and_spaces if not w.isspace() and w]
    gibberish_count = 0
    english_count = 0
    
    for w in only_words:
        if not w: continue
        if len(w) > 2 and w in spell:
            english_count += 1
        else:
            gibberish_count += 1
            
    is_mostly_gibberish = gibberish_count > english_count
    print(f"DEBUG: Мусор: {gibberish_count}, Английский: {english_count}. Тотальный: {is_mostly_gibberish}")

    result = []
    for item in words_and_spaces:
        if item.isspace():
            result.append(item)
        else:
            result.append(fix_word(item, whitelist, force_translate=is_mostly_gibberish))
            
    final_text = "".join(result)
    pyperclip.copy(final_text)
    
    time.sleep(0.1)
    keyboard.press_and_release('ctrl+v')
    
def show_about():
    """Окно с помощью для пользователя"""
    root = tk.Tk()
    root.withdraw()  # Прячем основное пустое окно
    root.attributes("-topmost", True) # Выводим поверх всех окон
    
    help_text = (
        "Абра исправляет текст, набранный в неверной раскладке.\n\n"
        "КАК РАБОТАЕТ:\n"
        "1. Выделите абракадабру.\n"
        "2. Нажмите сочетание клавиш (по умолчанию Ctrl+Alt+Q).\n"
        "3. Текст станет русским.\n\n"
        "КАК НАСТРОИТЬ:\n"
        "В меню трея выберите 'Открыть настройки'. Там можно изменить сочетания клавиш.\n"
        "А также синхронизировать словарь исключений\n"
        "Если Абра перевела слово, которое не нужно переводить — выделите его "
        "и нажмите Ctrl+Alt+A, чтобы добавить в исключения."
    )
    
    messagebox.showinfo("О программе", help_text)
    root.destroy()

def show_author():
    """Окно об авторе и ссылка на донат"""
    # Здесь открываем страницу донатов
    donation_url = "https://pay.cloudtips.ru/p/dfa5bb67"
    
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    
    author_info = (
        "Автор: Видеограф, монтажер и преподаватель.\n"
        "Создал этот инструмент, замучившись перепечатывать сообщения.\n\n"
        "Если Абра сэкономила вам время, я буду рад поддержке! "
        "Сейчас откроется страница с QR-кодом для доната."
    )
    
    if messagebox.askyesno("Об авторе", author_info + "\n\nПоблагодарить рублем?"):
        webbrowser.open(donation_url)
    root.destroy()

# --- ТРЕЙ И МЕНЮ ---

def quit_prog(icon):
    icon.stop()
    os._exit(0)

def setup_tray():
    icon = pystray.Icon("layout_fixer")
    icon_path = "main_icon.ico"
    
    # заглушка, чтобы программа не вылетела.
    if os.path.exists(icon_path):
        icon_image = Image.open(icon_path)
    else:
        icon_image = Image.new('RGB', (64, 64), (0, 120, 215))
    
    icon.icon = icon_image
    
    icon.menu = pystray.Menu(
        item('Синхронизировать с Google', lambda: sync_with_sheets()),
        item('Открыть настройки (JSON)', lambda: os.startfile(SETTINGS_FILE)),
        pystray.Menu.SEPARATOR,
        item('О программе', show_about),
        item('Автор и поддержка', show_author),
        pystray.Menu.SEPARATOR, # Добавит разделительную полоску
        item('Выход', quit_prog)
    )
    icon.title = "ABRA - исправление раскладки"
    icon.run()

# Регистрируем кнопки из конфига
keyboard.add_hotkey(config["hotkey_fix"], convert_smart)
keyboard.add_hotkey(config["hotkey_add"], add_to_whitelist)

if __name__ == "__main__":
    # При запуске сразу пробуем обновиться из облака
    sync_with_sheets()
    setup_tray()