import pyperclip
import pyautogui
import time
import re
import os
import json
import requests
import threading
import ctypes
from datetime import datetime
from spellchecker import SpellChecker
from PIL import Image
import pystray
from pystray import MenuItem as item
import tkinter as tk
from tkinter import messagebox, ttk
import webbrowser
from pynput import keyboard as pk

# --- КОНСТАНТЫ ---
SETTINGS_FILE = "settings.json"
TERMS_FILE = "my_terms.txt"
LOG_FILE = "abra_log.txt"
ICON_FILE = "main_icon.ico"

pyautogui.FAILSAFE = False 

root = None  
hotkey_listener = None 
tray_icon = None 
config = {} 

KEY_MAP = {
    'q':'й', 'w':'ц', 'e':'у', 'r':'к', 't':'е', 'y':'н', 'u':'г', 'i':'ш', 'o':'щ', 'p':'з', '[':'х', ']':'ъ',
    'a':'ф', 's':'ы', 'd':'в', 'f':'а', 'g':'п', 'h':'р', 'j':'о', 'k':'л', 'l':'д', ';':'ж', "'":'э',
    'z':'я', 'x':'ч', 'c':'с', 'v':'м', 'b':'и', 'n':'т', 'm':'ь', ',':'б', '.':'ю', '/':'.'
}

DEFAULT_SETTINGS = {
    "hotkey_char": "k",       
    "hotkey_add_char": "a",   
    "show_tooltip": True,
    "smart_punctuation": True,
    "sheets_url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vTsX55LrgXf9NN4MWhgVbPSvRYsmZyIEgV1jHTt50Lp2EU7pnpLLg6U5ELQQHb9Qw4xGObRyQIexFFc/pub?gid=0&single=true&output=csv"
}

# --- ЛОГИРОВАНИЕ ---
def log(message):
    try:
        timestamp = datetime.now().strftime("%H:%M:%S")
        text = f"[{timestamp}] {message}"
        print(text)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(text + "\n")
    except: pass

# --- НАСТРОЙКИ ---
def load_settings():
    global config
    if not os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_SETTINGS, f, indent=4)
        config = DEFAULT_SETTINGS
    else:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "hotkey_fix" in data: 
                del data["hotkey_fix"]
                data["hotkey_char"] = "k"
            if "hotkey_add" in data: 
                del data["hotkey_add"]
                data["hotkey_add_char"] = "a"
            for key, val in DEFAULT_SETTINGS.items():
                if key not in data:
                    data[key] = val
            config = data
    return config

def save_settings():
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)
    log("Настройки сохранены.")
    restart_hotkeys()

# --- ЛОГИКА ---
spell = SpellChecker(language='en')
eng_chars = "qwertyuiop[]asdfghjkl;'zxcvbnm,./QWERTYUIOP{}ASDFGHJKL:\"ZXCVBNM<>?@#$^&"
rus_chars = "йцукенгшщзхъфывапролджэячсмитьбю.ЙЦУКЕНГШЩЗХЪФЫВАПРОЛДЖЭЯЧСМИТЬБЮ,№;:??"
to_rus = str.maketrans(eng_chars, rus_chars)

def get_saved_terms():
    if not os.path.exists(TERMS_FILE): return set()
    with open(TERMS_FILE, "r", encoding="utf-8") as f:
        return {line.strip().lower() for line in f if line.strip()}

def force_release_modifiers():
    """Жесткий сброс клавиш"""
    ctypes.windll.user32.keybd_event(0x10, 0, 2, 0) # Shift Up
    ctypes.windll.user32.keybd_event(0x11, 0, 2, 0) # Ctrl Up
    ctypes.windll.user32.keybd_event(0x12, 0, 2, 0) # Alt Up

def smart_punctuation_fix(text):
    text = text.replace("ююю", "...")
    text = text.replace("Ююю", "...")
    text = re.sub(r'\?(\s*[а-яa-z])', r',\1', text)
    text = re.sub(r'б(\s)', r',\1', text)
    return text

def fix_text_logic(text):
    words = [re.sub(r'[^\w]', '', w.lower()) for w in re.split(r'\s+', text) if w.strip()]
    valid_eng_count = 0
    gibberish_count = 0
    for w in words:
        if len(w) > 2 and w in spell:
            valid_eng_count += 1
        else:
            gibberish_count += 1
    force_rus = gibberish_count >= valid_eng_count
    
    log(f"АНАЛИЗ: Мусор: {gibberish_count} | Англ: {valid_eng_count} | РЕЖИМ: {'ПЕРЕВОД' if force_rus else 'ОСТАВИТЬ'}")

    whitelist = get_saved_terms()
    words_and_spaces = re.split(r'(\s+)', text)
    
    result = []
    for chunk in words_and_spaces:
        if chunk.isspace():
            result.append(chunk)
            continue
        clean = re.sub(r'[^\w]', '', chunk.lower())
        if clean in whitelist:
            result.append(chunk)
            continue
        if force_rus or (len(clean) <= 2 or clean not in spell):
            result.append(chunk.translate(to_rus))
        else:
            result.append(chunk)

    final = "".join(result)
    if config.get("smart_punctuation", True):
        final = smart_punctuation_fix(final)
    return final

def show_notification(title, message):
    if config.get("show_tooltip", True) and tray_icon:
        try: tray_icon.notify(message, title)
        except: pass

def perform_copy():
    pyperclip.copy("")
    # Метод 1: Ctrl+C (для обычных систем)
    pyautogui.hotkey('ctrl', 'c', interval=0.1)
    for _ in range(5): 
        if pyperclip.paste(): return True
        time.sleep(0.05)
    
    # Метод 2: Ctrl+Insert (для твоей системы)
    log("Ctrl+C не сработал. Пробую Ctrl+Insert...")
    pyautogui.hotkey('ctrl', 'insert', interval=0.1)
    for _ in range(5): 
        if pyperclip.paste(): return True
        time.sleep(0.05)
    return False

def perform_paste():
    """Надежная вставка: Shift+Insert, затем Ctrl+V"""
    log("Вставка через Shift+Insert...")
    pyautogui.hotkey('shift', 'insert', interval=0.1)
    
    # Небольшая пауза, и контрольный Ctrl+V, если первый метод не сработал
    # (Визуально это не будет заметно, если сработало первое)
    time.sleep(0.1)
    pyautogui.hotkey('ctrl', 'v', interval=0.1)

def work_cycle():
    log("\n=== СТАРТ ЦИКЛА (V16) ===")
    show_notification("АБРАКАДАБРА!", "Шаманю...")
    
    time.sleep(0.2)
    force_release_modifiers()
    
    old_clipboard = pyperclip.paste()
    
    if not perform_copy():
        log("КРИТИЧЕСКАЯ ОШИБКА: Не удалось скопировать.")
        show_notification("Ошибка", "Не могу скопировать текст!")
        return
    
    text = pyperclip.paste()
    log(f"СКОПИРОВАНО (len {len(text)}): '{text[:30]}...'")
    
    if not text.strip(): return

    try:
        final_text = fix_text_logic(text)
        log(f"ИТОГ: '{final_text[:30]}...'")
        
        pyperclip.copy(final_text)
        
        # Сброс перед вставкой
        force_release_modifiers()
        time.sleep(0.2)
        
        # НОВАЯ ВСТАВКА
        perform_paste()
        
        log("Команда вставки отправлена.")
    except Exception as e:
        log(f"ИСКЛЮЧЕНИЕ: {e}")

def add_word_cycle():
    force_release_modifiers()
    pyperclip.copy("")
    pyautogui.hotkey('ctrl', 'insert', interval=0.1) # Тоже меняем на Insert для надежности
    time.sleep(0.2)
    
    text = pyperclip.paste().strip().lower()
    clean_text = re.sub(r'[^\w]', '', text) 
    
    if clean_text:
        if len(clean_text) < 3:
            show_notification("Ой!", f"Слово '{clean_text}' слишком короткое.")
        else:
            with open(TERMS_FILE, "a", encoding="utf-8") as f:
                f.write(clean_text + "\n")
            log(f"Слово '{clean_text}' сохранено.")
            show_notification("Исключение", f"Слово '{clean_text}' сохранено.")

# --- УПРАВЛЕНИЕ ХОТКЕЯМИ ---
def restart_hotkeys():
    global hotkey_listener
    if hotkey_listener:
        hotkey_listener.stop()
    try:
        char_fix = config["hotkey_char"].lower()
        char_add = config["hotkey_add_char"].lower()
        ru_fix = KEY_MAP.get(char_fix, char_fix)
        ru_add = KEY_MAP.get(char_add, char_add)
        
        hotkey_map = {
            f"<ctrl>+<alt>+{char_fix}": lambda: threading.Thread(target=work_cycle).start(),
            f"<ctrl>+<alt>+{ru_fix}":   lambda: threading.Thread(target=work_cycle).start(),
            f"<ctrl>+<alt>+{char_add}": lambda: threading.Thread(target=add_word_cycle).start(),
            f"<ctrl>+<alt>+{ru_add}":   lambda: threading.Thread(target=add_word_cycle).start(),
        }
        hotkey_listener = pk.GlobalHotKeys(hotkey_map)
        hotkey_listener.start()
        log(f"Хоткеи активны: {char_fix}/{ru_fix}")
    except Exception as e:
        log(f"Ошибка бинда: {e}")

# --- GUI ---
class SettingsWindow:
    def __init__(self, master):
        self.window = tk.Toplevel(master)
        self.window.title("Настройки ABRA")
        self.window.geometry("450x650")
        self.window.resizable(False, False)
        if os.path.exists(ICON_FILE):
            try: self.window.iconbitmap(ICON_FILE)
            except: pass
        
        style = ttk.Style()
        style.configure("TLabel", font=("Arial", 10))
        
        frame_keys = ttk.LabelFrame(self.window, text="Горячие клавиши (Только буква)", padding=10)
        frame_keys.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(frame_keys, text="Исправить (Ctrl+Alt + ...):").pack(anchor="w")
        self.entry_fix = ttk.Entry(frame_keys, width=5)
        self.entry_fix.insert(0, config["hotkey_char"])
        self.entry_fix.pack(anchor="w", pady=5)

        ttk.Label(frame_keys, text="Добавить искл. (Ctrl+Alt + ...):").pack(anchor="w")
        self.entry_add = ttk.Entry(frame_keys, width=5)
        self.entry_add.insert(0, config["hotkey_add_char"])
        self.entry_add.pack(anchor="w", pady=5)
        
        frame_opts = ttk.LabelFrame(self.window, text="Опции", padding=10)
        frame_opts.pack(fill="x", padx=10, pady=5)
        self.var_tooltip = tk.BooleanVar(value=config.get("show_tooltip", True))
        ttk.Checkbutton(frame_opts, text="Уведомления", variable=self.var_tooltip).pack(anchor="w")
        self.var_smart = tk.BooleanVar(value=config.get("smart_punctuation", True))
        ttk.Checkbutton(frame_opts, text="Умная пунктуация (ююю -> ..., ? -> ,)", variable=self.var_smart).pack(anchor="w")

        frame_terms = ttk.LabelFrame(self.window, text="Словарь исключений", padding=10)
        frame_terms.pack(fill="x", padx=10, pady=5)
        ttk.Button(frame_terms, text="📝 Редактировать список (txt)", command=self.open_terms_file).pack(fill="x")

        frame_about = ttk.LabelFrame(self.window, text="Инфо", padding=10)
        frame_about.pack(fill="both", expand=True, padx=10, pady=5)
        ttk.Label(frame_about, text="Если программа полезна — буду рад поддержке!", justify="center").pack(pady=5)
        ttk.Button(frame_about, text="☕ Поддержать автора", command=self.open_donate).pack(fill="x", padx=50)

        frame_btns = ttk.Frame(self.window)
        frame_btns.pack(fill="x", padx=10, pady=10)
        ttk.Button(frame_btns, text="Синхронизация", command=self.sync_now).pack(side="left", expand=True)
        ttk.Button(frame_btns, text="Сохранить", command=self.save_and_close).pack(side="right", expand=True)

    def open_donate(self): webbrowser.open("https://pay.cloudtips.ru/p/dfa5bb67")
    def open_terms_file(self):
        if not os.path.exists(TERMS_FILE): open(TERMS_FILE, 'w').close()
        os.startfile(TERMS_FILE)
    def sync_now(self):
        threading.Thread(target=sync_with_sheets_logic).start()
        messagebox.showinfo("Инфо", "Синхронизация запущена.")
    def save_and_close(self):
        char = self.entry_fix.get().strip().lower()
        char_add = self.entry_add.get().strip().lower()
        if char: config["hotkey_char"] = char[0]
        if char_add: config["hotkey_add_char"] = char_add[0]
        config["show_tooltip"] = self.var_tooltip.get()
        config["smart_punctuation"] = self.var_smart.get()
        save_settings()
        self.window.destroy()

def open_settings_safe():
    if root: root.after(0, lambda: SettingsWindow(root))

def sync_with_sheets_logic():
    log("Синхронизация...")
    url = config.get("sheets_url")
    if not url: return
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            cloud = {l.strip().lower() for l in r.text.splitlines() if l.strip()}
            local = get_saved_terms()
            total = local.union(cloud)
            with open(TERMS_FILE, "w", encoding="utf-8") as f:
                for w in sorted(total): f.write(w + "\n")
            log(f"Синхронизация OK.")
            show_notification("Успех", "Словарь обновлен!")
    except Exception as e: log(f"Ошибка: {e}")

def setup_tray():
    global tray_icon
    img = Image.open(ICON_FILE) if os.path.exists(ICON_FILE) else Image.new('RGB', (64, 64), (0, 120, 215))
    menu = pystray.Menu(
        item('Настройки', lambda: open_settings_safe()),
        item('Выход', lambda icon: quit_app(icon))
    )
    tray_icon = pystray.Icon("abra", img, "ABRA", menu)
    tray_icon.run()

def quit_app(icon):
    icon.stop()
    if root: root.quit() 
    os._exit(0)

if __name__ == "__main__":
    try:
        log("--- ЗАПУСК (V16 SHIFT+INSERT) ---")
        load_settings()
        restart_hotkeys()
        root = tk.Tk()
        root.withdraw()
        if os.path.exists(ICON_FILE): root.iconbitmap(ICON_FILE)
        threading.Thread(target=setup_tray).start()
        threading.Thread(target=sync_with_sheets_logic).start()
        root.mainloop()
    except Exception as e:
        log(f"CRITICAL ERROR: {e}")