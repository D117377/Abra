import time
import re
import os
import json
import threading
import ctypes
import webbrowser
import tkinter as tk
from tkinter import ttk
from datetime import datetime

# Импорты для трея и иконок
from pystray import MenuItem as item
import pystray
from PIL import Image
from pynput import keyboard as pk

# --- КОНСТАНТЫ ---
SETTINGS_FILE = "settings.json"
TERMS_FILE = "my_terms.txt"
LOG_FILE = "abra_log.txt"
ICON_FILE = "main_icon.ico"

# Коды клавиш
VK_C = 0x43
VK_V = 0x56
VK_INSERT = 0x2D
VK_CONTROL = 0x11
VK_SHIFT = 0x10
VK_ALT = 0x12

DEFAULT_SETTINGS = {
    "fix_char": "s",
    "fix_ctrl": False,
    "fix_alt": True,
    "fix_shift": True,
    
    "add_char": "a",
    "add_ctrl": False,
    "add_alt": True,
    "add_shift": True,

    "show_tooltip": True,
    "smart_punctuation": True,
    "sheets_url": "" 
}

KEY_MAP = {
    'q':'й', 'w':'ц', 'e':'у', 'r':'к', 't':'е', 'y':'н', 'u':'г', 'i':'ш', 'o':'щ', 'p':'з', '[':'х', ']':'ъ',
    'a':'ф', 's':'ы', 'd':'в', 'f':'а', 'g':'п', 'h':'р', 'j':'о', 'k':'л', 'l':'д', ';':'ж', "'":'э',
    'z':'я', 'x':'ч', 'c':'с', 'v':'м', 'b':'и', 'n':'т', 'm':'ь', ',':'б', '.':'ю', '/':'.', '`':'ё'
}

class AbraApp:
    def __init__(self):
        self.root = None
        self.tray_icon = None
        self.hotkey_listener = None
        self.config = {}
        self.last_sync_time = 0
        
        self.load_settings()
        
        from spellchecker import SpellChecker
        self.spell = SpellChecker(language='en')
        
        # Карты перевода
        eng_chars = "qwertyuiop[]asdfghjkl;'zxcvbnm,./`QWERTYUIOP{}ASDFGHJKL:\"ZXCVBNM<>?~@#$^&"
        rus_chars = "йцукенгшщзхъфывапролджэячсмитьбю.ёЙЦУКЕНГШЩЗХЪФЫВАПРОЛДЖЭЯЧСМИТЬБЮ,Ё№;:??"
        self.to_rus = str.maketrans(eng_chars, rus_chars)
        self.to_eng = str.maketrans(rus_chars, eng_chars)

    def log(self, message):
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] {message}")
        except: pass

    def load_settings(self):
        if not os.path.exists(SETTINGS_FILE):
            self.config = DEFAULT_SETTINGS.copy()
            self.save_settings()
        else:
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data.pop("use_mouse_x1", None)
                for key, val in DEFAULT_SETTINGS.items():
                    if key not in data: data[key] = val
                self.config = data
            except:
                self.config = DEFAULT_SETTINGS.copy()

    def save_settings(self):
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
            self.restart_hotkeys()
        except Exception as e:
            self.log(f"Ошибка сохранения: {e}")

    # --- СИСТЕМНЫЕ ФУНКЦИИ ---
    def force_release_modifiers(self):
        ctypes.windll.user32.keybd_event(VK_SHIFT, 0, 2, 0)
        ctypes.windll.user32.keybd_event(VK_CONTROL, 0, 2, 0)
        ctypes.windll.user32.keybd_event(VK_ALT, 0, 2, 0)

    def send_combo(self, modifier, key):
        ctypes.windll.user32.keybd_event(modifier, 0, 0, 0)
        ctypes.windll.user32.keybd_event(key, 0, 0, 0)
        ctypes.windll.user32.keybd_event(key, 0, 2, 0)
        ctypes.windll.user32.keybd_event(modifier, 0, 2, 0)

    def perform_system_copy(self):
        import pyperclip
        pyperclip.copy("")
        self.send_combo(VK_CONTROL, VK_C)
        for _ in range(4): 
            if pyperclip.paste(): return True
            time.sleep(0.05)
        self.send_combo(VK_CONTROL, VK_INSERT)
        for _ in range(4): 
            if pyperclip.paste(): return True
            time.sleep(0.05)
        return False

    def perform_system_paste(self):
        self.send_combo(VK_CONTROL, VK_V)

    # --- ЛОГИКА ---
    def get_saved_terms(self):
        if not os.path.exists(TERMS_FILE): return set()
        try:
            with open(TERMS_FILE, "r", encoding="utf-8") as f:
                return {line.strip().lower() for line in f if line.strip()}
        except: return set()

    def smart_punctuation_fix(self, text):
        text = text.replace("ююю", "...").replace("Ююю", "...")
        text = re.sub(r'\?(\s*[а-яa-z])', r',\1', text)
        text = re.sub(r'(?<!\b[оО])б(\s)', r',\1', text)
        text = re.sub(r'(^|\s)[jJ],(\s|$)', r'\1об\2', text, flags=re.IGNORECASE)
        return text

    def fix_text_logic(self, text):
        words = re.findall(r'\b\w+\b', text.lower())
        if not words: return text
        
        has_eng_chars = bool(re.search(r'[a-zA-Z]', text))
        has_rus_chars = bool(re.search(r'[а-яА-ЯёЁ]', text))
        
        whitelist = self.get_saved_terms()
        
        # Rus -> Eng
        if has_rus_chars and not has_eng_chars:
            candidate = text.translate(self.to_eng)
            cand_words = re.findall(r'\b\w+\b', candidate.lower())
            valid_eng_count = 0
            for w in cand_words:
                if len(w) > 1 and w in self.spell:
                    valid_eng_count += 1
            if valid_eng_count > 0 and (valid_eng_count / len(cand_words) >= 0.3):
                return candidate
            return text

        # Eng -> Rus
        if has_eng_chars:
            valid_orig_count = 0
            for w in words:
                clean = re.sub(r'[^\w]', '', w)
                if clean in whitelist: 
                    valid_orig_count += 1
                    continue
                if len(clean) > 1 and clean in self.spell:
                    valid_orig_count += 1
            if len(words) > 0 and (valid_orig_count / len(words) > 0.6):
                return text
            
            final = text.translate(self.to_rus)
            if self.config.get("smart_punctuation", True):
                final = self.smart_punctuation_fix(final)
            return final

        return text

    def show_notification(self, title, message):
        # Проверяем конфиг и наличие иконки
        if self.config.get("show_tooltip", True) and self.tray_icon:
            try:
                self.tray_icon.notify(message, title)
            except Exception as e:
                # Теперь мы видим ошибку в логе, если уведомление не сработало
                self.log(f"Ошибка уведомления: {e}")

    def work_cycle(self):
        import pyperclip
        import pyautogui
        pyautogui.FAILSAFE = False
        
        self.force_release_modifiers()
        
        if not self.perform_system_copy():
            self.show_notification("Ошибка", "Не удалось скопировать.")
            return
        
        text = pyperclip.paste()
        if not text.strip(): return

        try:
            final_text = self.fix_text_logic(text)
            if final_text == text: return

            pyperclip.copy(final_text)
            self.force_release_modifiers()
            time.sleep(0.1)
            self.perform_system_paste()
        except Exception as e:
            self.log(f"Error: {e}")

    def add_word_cycle(self):
        import pyperclip
        self.force_release_modifiers()
        pyperclip.copy("")
        self.send_combo(VK_CONTROL, VK_C)
        time.sleep(0.2)
        text = pyperclip.paste().strip().lower()
        clean = re.sub(r'[^\w]', '', text) 
        if len(clean) >= 3:
            with open(TERMS_FILE, "a", encoding="utf-8") as f: f.write(clean + "\n")
            self.show_notification("Исключение", f"Слово '{clean}' запомнил.")
        else:
            self.show_notification("Ой", "Слово слишком короткое.")

    # --- ХОТКЕИ ---
    def restart_hotkeys(self):
        if self.hotkey_listener: self.hotkey_listener.stop()
        try:
            def make_combo(char, use_ctrl, use_alt, use_shift):
                parts = []
                if use_ctrl: parts.append("<ctrl>")
                if use_alt: parts.append("<alt>")
                if use_shift: parts.append("<shift>")
                parts.append(char.lower())
                return "+".join(parts)

            fix_combo = make_combo(self.config["fix_char"], self.config["fix_ctrl"], self.config["fix_alt"], self.config["fix_shift"])
            add_combo = make_combo(self.config["add_char"], self.config["add_ctrl"], self.config["add_alt"], self.config["add_shift"])

            char_fix = self.config["fix_char"].lower()
            ru_fix_char = KEY_MAP.get(char_fix, char_fix)
            fix_combo_ru = make_combo(ru_fix_char, self.config["fix_ctrl"], self.config["fix_alt"], self.config["fix_shift"])

            hotkey_definitions = {
                fix_combo: lambda: threading.Thread(target=self.work_cycle, daemon=True).start(),
                fix_combo_ru: lambda: threading.Thread(target=self.work_cycle, daemon=True).start(),
                add_combo: lambda: threading.Thread(target=self.add_word_cycle, daemon=True).start(),
            }
            self.hotkey_listener = pk.GlobalHotKeys(hotkey_definitions)
            self.hotkey_listener.start()
        except Exception as e: self.log(f"Bind error: {e}")

    def sync_with_sheets(self):
        import requests
        if time.time() - self.last_sync_time < 3600: return
        url = self.config.get("sheets_url")
        if not url: return
        try:
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                cloud = {l.strip().lower() for l in r.text.splitlines() if l.strip()}
                local = self.get_saved_terms()
                with open(TERMS_FILE, "w", encoding="utf-8") as f:
                    for w in sorted(local.union(cloud)): f.write(w + "\n")
                self.last_sync_time = time.time()
                self.show_notification("Успех", "Словарь обновлен!")
        except: pass

    # --- GUI И ТРЕЙ ---
    def setup_tray(self):
        # Загрузка иконки
        if os.path.exists(ICON_FILE):
            img = Image.open(ICON_FILE)
        else:
            # Создаем синий квадрат если иконки нет
            img = Image.new('RGB', (64, 64), (0, 120, 215))
            
        menu = pystray.Menu(
            item('Настройки', lambda: self.open_settings_safe()),
            item('Выход', lambda icon: self.quit_app(icon))
        )
        self.tray_icon = pystray.Icon("abra", img, "ABRA", menu)
        self.tray_icon.run()

    def open_settings_safe(self):
        if self.root: self.root.after(0, self.create_settings_window)

    def create_settings_window(self):
        window = tk.Toplevel(self.root)
        window.title("Настройки ABRA 1.7")
        window.geometry("450x580")
        window.resizable(False, False)
        if os.path.exists(ICON_FILE):
            try: window.iconbitmap(ICON_FILE)
            except: pass
            
        def create_hotkey_block(parent, title, key_prefix):
            frame = ttk.LabelFrame(parent, text=title, padding=10)
            frame.pack(fill="x", padx=10, pady=5)
            v_ctrl = tk.BooleanVar(value=self.config.get(f"{key_prefix}_ctrl", True))
            v_alt = tk.BooleanVar(value=self.config.get(f"{key_prefix}_alt", True))
            v_shift = tk.BooleanVar(value=self.config.get(f"{key_prefix}_shift", False))
            
            f_checks = ttk.Frame(frame)
            f_checks.pack(anchor="w")
            ttk.Checkbutton(f_checks, text="Ctrl", variable=v_ctrl).pack(side="left", padx=5)
            ttk.Checkbutton(f_checks, text="Alt", variable=v_alt).pack(side="left", padx=5)
            ttk.Checkbutton(f_checks, text="Shift", variable=v_shift).pack(side="left", padx=5)
            
            f_char = ttk.Frame(frame)
            f_char.pack(anchor="w", pady=5)
            ttk.Label(f_char, text="Клавиша:").pack(side="left")
            entry = ttk.Entry(f_char, width=5)
            entry.insert(0, self.config.get(f"{key_prefix}_char", "k"))
            entry.pack(side="left", padx=5)
            return v_ctrl, v_alt, v_shift, entry

        chk_fix = create_hotkey_block(window, "1. Исправить текст", "fix")
        chk_add = create_hotkey_block(window, "2. Добавить исключение", "add")
        
        frame_opts = ttk.LabelFrame(window, text="Опции", padding=10)
        frame_opts.pack(fill="x", padx=10, pady=5)
        
        v_tooltip = tk.BooleanVar(value=self.config.get("show_tooltip", True))
        ttk.Checkbutton(frame_opts, text="Показывать уведомления", variable=v_tooltip).pack(anchor="w")
        
        v_smart = tk.BooleanVar(value=self.config.get("smart_punctuation", True))
        ttk.Checkbutton(frame_opts, text="Умная пунктуация", variable=v_smart).pack(anchor="w")
        
        frame_about = ttk.LabelFrame(window, text="Инфо", padding=10)
        frame_about.pack(fill="both", expand=True, padx=10, pady=5)
        ttk.Label(frame_about, text="Вопросы? Пишите: doobych@yandex.ru", justify="center").pack(pady=2)
        ttk.Button(frame_about, text="☕ Поддержать автора", command=lambda: webbrowser.open("https://pay.cloudtips.ru/p/dfa5bb67")).pack(fill="x", padx=50, pady=5)

        def save():
            self.config["fix_ctrl"] = chk_fix[0].get()
            self.config["fix_alt"] = chk_fix[1].get()
            self.config["fix_shift"] = chk_fix[2].get()
            self.config["fix_char"] = chk_fix[3].get().strip().lower()[0]
            self.config["add_ctrl"] = chk_add[0].get()
            self.config["add_alt"] = chk_add[1].get()
            self.config["add_shift"] = chk_add[2].get()
            self.config["add_char"] = chk_add[3].get().strip().lower()[0]
            self.config["show_tooltip"] = v_tooltip.get()
            self.config["smart_punctuation"] = v_smart.get()
            self.save_settings()
            window.destroy()

        frame_btns = ttk.Frame(window)
        frame_btns.pack(fill="x", padx=10, pady=10)
        ttk.Button(frame_btns, text="Словарь", command=lambda: os.startfile(TERMS_FILE) if os.path.exists(TERMS_FILE) else open(TERMS_FILE, 'w').close() or os.startfile(TERMS_FILE)).pack(side="left", padx=5)
        ttk.Button(frame_btns, text="Сохранить", command=save).pack(side="right", expand=True, fill="x", padx=5)

    def run(self):
        # 1. Запуск трея в отдельном потоке (но через метод класса)
        threading.Thread(target=self.setup_tray, daemon=True).start()
        
        # 2. Хоткеи
        self.restart_hotkeys()
        
        # 3. Синхронизация
        threading.Thread(target=self.sync_with_sheets).start()

        # 4. GUI Loop (должен быть в главном потоке)
        self.root = tk.Tk()
        self.root.withdraw()
        if os.path.exists(ICON_FILE): self.root.iconbitmap(ICON_FILE)
        self.root.mainloop()

    def quit_app(self, icon):
        icon.stop()
        if self.hotkey_listener: self.hotkey_listener.stop()
        if self.root: self.root.quit()
        os._exit(0)

if __name__ == "__main__":
    app = AbraApp()
    app.run()