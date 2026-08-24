# J.A.R.V.I.S. - Telegram Bot + Windows GUI
# Token GUI üzerinden girilir. Token dosyaya zorunlu olarak yazılmaz.
# Gereken ana paket: python-telegram-bot
# Görsel analiz opsiyoneldir; YOLO kurulamazsa bot yine çalışır.

import sys
import os
import subprocess
import threading
import asyncio
import time
import random
import datetime
import urllib.parse
import tkinter as tk
import io
import json
import socket
import urllib.request
import math
from pathlib import Path
from tkinter import messagebox

# Telegram doğrudan Bot API ile çalışır.
# requests GUI açıldıktan sonra gerektiğinde kontrol edilir.
REQUESTS_OK = False


APP_TITLE = "J.A.R.V.I.S. - Telegram Assistant"
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_token.txt")
OPENAI_API_KEY_RUNTIME = ""


def install_package(package, import_name):
    try:
        __import__(import_name)
        return True
    except ImportError:
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", package],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            __import__(import_name)
            return True
        except Exception:
            return False


# İsteğe bağlı paketler.
WIKIPEDIA_OK = False
PIL_OK = False
YOLO_OK = False
PSUTIL_OK = False
try:
    import psutil
    PSUTIL_OK = True
except Exception:
    PSUTIL_OK = False

try:
    YOLO_OK = False
except Exception:
    YOLO_OK = False


# -------------------- GELİŞMİŞ YAPAY ZEKA --------------------
AI_HISTORY=[]
AI_LOCK=threading.Lock()

def open_chatgpt_login():
    """İstenirse tarayıcıda ChatGPT'yi açar; normal soru akışında kullanılmaz."""
    import webbrowser
    webbrowser.open("https://chatgpt.com/")


def _openai_hard_answer(user_text):
    """Zor/uzun soruları OpenAI Responses API ile yanıtlar.

    OpenAI API anahtarı uygulama açılışında alınır. API erişilemezse yerel JARVIS
    cevabına geri dönülür; tarayıcıda ChatGPT açılmaz.
    """
    if not OPENAI_API_KEY_RUNTIME:
        return None
    try:
        import requests
        system = (
            "Sen J.A.R.V.I.S.'sin. Türkçe konuş. Kısa ama yeterli, doğal ve saygılı cevap ver. "
            "Kullanıcı sana günlük hayat, teknik konular, genel bilgi veya zor sorular sorabilir. "
            "Kullanıcıya gerektiğinde 'efendim' diye hitap et. Emin olmadığın bilgiyi uydurma."
        )
        payload = {
            "model": "gpt-5.6-luna",
            "input": [
                {"role": "developer", "content": system},
                {"role": "user", "content": user_text}
            ],
            "max_output_tokens": 900
        }
        r = requests.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY_RUNTIME}", "Content-Type": "application/json"},
            json=payload,
            timeout=45
        )
        if not r.ok:
            return None
        data = r.json()
        text = data.get("output_text")
        if text:
            return text.strip()
        # Güvenli fallback for response shapes where output_text is absent.
        chunks=[]
        for item in data.get("output", []) or []:
            for content in item.get("content", []) or []:
                if content.get("type") in ("output_text", "text") and content.get("text"):
                    chunks.append(content["text"])
        return "\n".join(chunks).strip() if chunks else None
    except Exception as e:
        print("OpenAI API:", e)
        return None


def _needs_hard_ai(text):
    m = text.lower().strip()
    hard_markers = (
        "neden", "nasıl", "nasil", "açıkla", "acikla", "karşılaştır", "karsilastir",
        "özetle", "ozetle", "kod yaz", "programla", "hesapla", "analiz", "felsefe",
        "matematik", "fizik", "kimya", "tarih", "ne düşünüyorsun", "ne dusunuyorsun",
        "detaylı", "detayli", "nedir", "kimdir", "ne demek", "anlat"
    )
    return len(m) >= 45 or any(x in m for x in hard_markers)


def ai_answer(user_text):
    """Önce yerel JARVIS komutları; zor sorularda OpenAI API."""
    local = jarvis.cevap(user_text)
    fallback = "Bunu şu anda sınırlı bilgi motorumla değerlendirebiliyorum. Daha belirli bir komut deneyebilirsiniz."
    local_is_error = bool(local) and ("modülü kurulu değil" in local or "alınamadı" in local or "bulunamadı" in local)
    # Yerel cevap gerçek bir komutsa doğrudan kullan. Bilgi modülü eksikse zor soruyu API'ye bırak.
    if local and not local_is_error and fallback not in local and "sınırlı bilgi motorum" not in local:
        return local
    if _needs_hard_ai(user_text) or local_is_error:
        remote = _openai_hard_answer(user_text)
        if remote:
            return remote
    return local or fallback

def wake_on_lan(mac,broadcast='255.255.255.255'):
    mac=''.join(c for c in mac if c.isalnum())
    if len(mac)!=12: raise ValueError('MAC adresi hatalı.')
    packet=bytes.fromhex('FF'*6+mac*16)
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as s:
        s.setsockopt(socket.SOL_SOCKET,socket.SO_BROADCAST,1)
        s.sendto(packet,(broadcast,9))

# -------------------- JARVIS BEYNİ --------------------

class JarvisBeyin:
    def __init__(self):
        self.selamlar = [
            "Merhaba efendim. Size nasıl yardımcı olabilirim?",
            "Hoş geldiniz efendim. J.A.R.V.I.S. hazır.",
            "Selam efendim. Sistemler çalışıyor.",
        ]
        self.nasilsin = [
            "Tüm sistemler normal çalışıyor efendim.",
            "Gayet iyiyim efendim. Emrinizdeyim.",
        ]
        self.espriler = [
            "Bilgisayar neden doktora gitmez? Çünkü zaten virüsü vardır. 😄",
            "Python neden sessizdir? Çünkü yılan gibi konuşmadan çalışır. 🐍",
            "RAM restorana giderse ne ister? Daha fazla bellek! 😄",
        ]

    def cevap(self, mesaj):
        m = mesaj.lower().strip()

        if m in {"merhaba", "selam", "hey", "sa", "selamlar"} or m.startswith(("merhaba ", "selam ", "hey ")):
            return random.choice(self.selamlar)

        if any(x in m for x in ["nasılsın", "nasilsin", "naber", "ne haber"]):
            return random.choice(self.nasilsin)

        if any(x in m for x in ["teşekkür", "tesekkur", "sağol", "sagol", "eyvallah"]):
            return "Rica ederim efendim. Her zaman."

        if any(x in m for x in ["güle güle", "bay bay", "bye", "hoşça kal", "hosca kal"]):
            return "Görüşmek üzere efendim."

        if any(x in m for x in ["sen kim", "kimsin", "adın ne"]):
            return "Ben J.A.R.V.I.S., Türkçe Telegram yapay zeka asistanınızım."

        if any(x in m for x in ["espri", "şaka", "saka", "fıkra", "fikra"]):
            return random.choice(self.espriler)

        if "saat" in m or "kaç" in m:
            now = datetime.datetime.now()
            return f"⏰ Saat {now:%H:%M}, efendim.\n📅 Tarih: {now:%d.%m.%Y}"

        if any(x in m for x in ["tarih", "bugün", "bugun"]):
            now = datetime.datetime.now()
            return f"📅 Bugün: {now:%d.%m.%Y}"

        if m.startswith(("hesapla ", "kaç eder ", "kac eder ")):
            return self.hesapla(m)

        if m.startswith(("ara ", "google ")):
            q = m.split(" ", 1)[1].strip()
            url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(q)
            return f"🔎 Arama:\n{url}"

        if m.startswith(("youtube ", "müzik ", "muzik ")):
            q = m.split(" ", 1)[1].strip()
            url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(q)
            return f"🎵 YouTube:\n{url}"

        if any(x in m for x in ["nedir", "kimdir", "ne demek", "bilgi ver", "anlat"]):
            return self.wikipedia(m)

        if m in ["/yardim", "yardım", "yardim", "komutlar"]:
            return self.yardim()

        # Günlük hayatta sık kullanılan JARVIS ifadeleri.
        daily = {
            "ne yapıyorsun": "Sistemleri izliyorum efendim. Emrinizdeyim.",
            "ne yapiyorsun": "Sistemleri izliyorum efendim. Emrinizdeyim.",
            "hazır mısın": "Her zaman hazırım efendim.",
            "hazir misin": "Her zaman hazırım efendim.",
            "uyuyor musun": "Hayır efendim, J.A.R.V.I.S. çevrimiçi.",
            "uyuyor musun?": "Hayır efendim, J.A.R.V.I.S. çevrimiçi.",
            "beni duyuyor musun": "Sizi duyuyorum efendim.",
            "beni duyuyor musun?": "Sizi duyuyorum efendim.",
            "sesimi duyuyor musun": "Evet efendim, sesinizi duyuyorum.",
            "yardım eder misin": "Elbette efendim. Ne yapmamı istersiniz?",
            "yardim eder misin": "Elbette efendim. Ne yapmamı istersiniz?",
            "iyi geceler": "İyi geceler efendim. Sistemleri izlemeye devam edeceğim.",
            "günaydın": "Günaydın efendim. J.A.R.V.I.S. hazır.",
            "gunaydin": "Günaydın efendim. J.A.R.V.I.S. hazır.",
            "iyi akşamlar": "İyi akşamlar efendim.",
            "iyi aksamlar": "İyi akşamlar efendim.",
            "tamam": "Anlaşıldı efendim.",
            "ok": "Anlaşıldı efendim.",
            "peki": "Peki efendim.",
            "evet": "Emredersiniz efendim.",
            "hayır": "Anlaşıldı efendim.",
            "seni kim yaptı": "Ben J.A.R.V.I.S.'im; bu bilgisayardaki sistem ve otomasyonlar için tasarlandım.",
            "sistem çalışıyor mu": "Evet efendim. J.A.R.V.I.S. çalışıyor ve sistem sensörlerini izliyor.",
            "telegram bağlı mı": "Telegram durumunu ana ekrandaki bağlantı göstergesinden kontrol edebilirsiniz efendim.",
        }
        if m in daily:
            return daily[m]

        return (
            f"Efendim, '{mesaj}' mesajınızı aldım. "
            "Bunu şu anda sınırlı bilgi motorumla değerlendirebiliyorum. "
            "Daha belirli bir komut deneyebilirsiniz."
        )

    def hesapla(self, ifade):
        try:
            temiz = (
                ifade.replace("hesapla", "")
                .replace("kaç eder", "")
                .replace("kac eder", "")
                .replace("x", "*")
                .replace("÷", "/")
                .strip()
                .replace(" ", "")
            )
            if not temiz or not all(c in "0123456789+-*/()." for c in temiz):
                return "❌ Geçersiz işlem. Örnek: hesapla 5+3*2"

            sonuc = eval(temiz, {"__builtins__": {}}, {})
            return f"🧮 Sonuç: {sonuc}"
        except Exception:
            return "❌ Hesaplama yapılamadı."

    def wikipedia(self, metin):
        if not WIKIPEDIA_OK:
            return "❌ Wikipedia modülü kurulu değil."

        try:
            sorgu = metin
            for kelime in ["nedir", "kimdir", "ne demek", "bilgi ver", "anlat"]:
                sorgu = sorgu.replace(kelime, "")
            sorgu = sorgu.strip()

            if not sorgu:
                return "Örnek: Atatürk kimdir?"

            import wikipedia
            wikipedia.set_lang("tr")
            return "📚 " + wikipedia.summary(sorgu, sentences=2)
        except Exception:
            return "❌ Bu konu hakkında Wikipedia'dan bilgi alınamadı."

    def yardim(self):
        return (
            "🤖 J.A.R.V.I.S. KOMUTLARI\n\n"
            "💬 Normal mesaj gönder\n"
            "🧮 hesapla 5+3*2\n"
            "🔎 ara Unreal Engine\n"
            "🎵 youtube oyun müziği\n"
            "📚 Atatürk kimdir\n"
            "⏰ saat kaç\n"
            "📅 bugün\n"
            "📸 Fotoğraf gönder\n"
            "🖥️ /ekran → bilgisayar ekran görüntüsü\n"
        )


jarvis = JarvisBeyin()
bot_running = False
bot_thread = None
stop_requested = False
gui_chat = None
gui_token = None
last_chat_id = None

automation_timers = []
automation_lock = threading.Lock()


def computer_status():
    import platform
    import shutil
    return (
        f"💻 Bilgisayar: {platform.node()}\n"
        f"🪟 Sistem: {platform.system()} {platform.release()}\n"
        f"🐍 Python: {platform.python_version()}\n"
        f"💾 Disk boş alanı: {shutil.disk_usage(os.getcwd()).free // (1024**3)} GB"
    )


def open_program(target):
    import subprocess
    import webbrowser

    shortcuts = {
        "chrome": "https://www.google.com",
        "google": "https://www.google.com",
        "youtube": "https://www.youtube.com",
        "notepad": "notepad.exe",
        "not defteri": "notepad.exe",
        "hesap makinesi": "calc.exe",
        "calculator": "calc.exe",
        "dosya": "explorer.exe",
        "dosya yöneticisi": "explorer.exe",
    }

    key = target.lower().strip()
    value = shortcuts.get(key)

    if value is None:
        return False, "Bu uygulama tanımlı değil."

    if value.startswith("http"):
        webbrowser.open(value)
    else:
        subprocess.Popen(value, shell=True)

    return True, f"✅ {target} açıldı."


def lock_computer():
    import subprocess
    subprocess.Popen("rundll32.exe user32.dll,LockWorkStation", shell=True)


def shutdown_computer():
    import subprocess
    subprocess.Popen("shutdown /s /t 10", shell=True)


def restart_computer():
    import subprocess
    subprocess.Popen("shutdown /r /t 10", shell=True)


def schedule_reminder(token, chat_id, minutes, message):
    def worker():
        time.sleep(max(1, minutes) * 60)
        if not stop_requested:
            send_text(token, chat_id, "⏰ HATIRLATMA\n" + message)

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    automation_timers.append((minutes, message))




def gui_add_chat(prefix, message):
    global gui_chat
    if gui_chat is None:
        return
    try:
        gui_chat.after(0, lambda: gui_chat.insert("end", f"{prefix}: {message}\n\n"))
        gui_chat.after(0, lambda: gui_chat.see("end"))
    except Exception:
        pass




# -------------------- FOTOĞRAF ANALİZİ --------------------

yolo_model = None

def get_yolo():
    global yolo_model
    if not YOLO_OK:
        return None
    if yolo_model is None:
        try:
            yolo_model = YOLO("yolov8n.pt")
        except Exception:
            return None
    return yolo_model


# -------------------- JARVIS CANLI GÖRÜNTÜ --------------------

JARVIS_LIVE_VIEW_ACTIVE = False
JARVIS_LIVE_SERVER = None
JARVIS_LIVE_THREAD = None
JARVIS_LIVE_PORT = 8765


class _JarvisLiveHandler(__import__("http.server").server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            html = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>JARVIS Canlı Görüntü</title>
<style>
html,body{margin:0;background:#050505;color:#00eaff;font-family:Consolas,monospace}
header{padding:10px;text-align:center}
img{display:block;margin:auto;max-width:100vw;max-height:90vh}
</style>
</head>
<body>
<header>🔴 J.A.R.V.I.S. CANLI GÖRÜNTÜ</header>
<img src="/stream" alt="JARVIS canlı görüntü">
</body>
</html>"""
            data = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        if self.path == "/stream":
            import io
            from PIL import ImageGrab

            self.send_response(200)
            self.send_header(
                "Content-Type",
                "multipart/x-mixed-replace; boundary=frame"
            )
            self.send_header("Cache-Control", "no-cache, no-store")
            self.end_headers()

            try:
                while JARVIS_LIVE_VIEW_ACTIVE:
                    image = ImageGrab.grab()
                    buf = io.BytesIO()
                    image.save(buf, "JPEG", quality=65, optimize=True)
                    frame = buf.getvalue()

                    self.wfile.write(b"--frame\r\n")
                    self.wfile.write(b"Content-Type: image/jpeg\r\n")
                    self.wfile.write(
                        f"Content-Length: {len(frame)}\r\n\r\n".encode()
                    )
                    self.wfile.write(frame)
                    self.wfile.write(b"\r\n")
                    self.wfile.flush()
                    time.sleep(0.12)
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception as e:
                print("JARVIS canlı yayın:", e)
            return

        self.send_error(404)

    def log_message(self, *_args):
        pass


def _jarvis_live_server_worker():
    from http.server import ThreadingHTTPServer

    global JARVIS_LIVE_SERVER

    class ReusableServer(ThreadingHTTPServer):
        allow_reuse_address = True

    JARVIS_LIVE_SERVER = ReusableServer(
        ("0.0.0.0", JARVIS_LIVE_PORT),
        _JarvisLiveHandler
    )
    JARVIS_LIVE_SERVER.serve_forever()


def _jarvis_get_lan_ip():
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"


def jarvis_fake_bios(parent=None):
    """DEL ile açılan JARVIS sahte BIOS ekranı."""
    import tkinter as tk
    win = tk.Toplevel(parent) if parent is not None else tk.Tk()
    win.title("J.A.R.V.I.S. BIOS")
    win.geometry("900x600")
    win.configure(bg="black")
    win.resizable(False, False)
    info = (
        "J.A.R.V.I.S. SYSTEM BIOS v3.7\n"
        "----------------------------------------\n\n"
        "SYSTEM STATUS       : ONLINE\n"
        "PROCESSOR           : READY\n"
        "MEMORY              : OK\n"
        "STORAGE             : OK\n"
        "NETWORK             : CONNECTED\n"
        "TELEGRAM            : READY\n"
        "AI CORE             : READY\n"
        "LIVE VIEW           : READY\n\n"
        "----------------------------------------\n"
        "ESC  - EXIT BIOS\n"
    )
    tk.Label(
        win, text=info, justify="left", anchor="nw",
        bg="black", fg="#00ff66", font=("Consolas", 14)
    ).pack(fill="both", expand=True, padx=35, pady=35)
    win.bind("<Escape>", lambda e: win.destroy())
    win.focus_force()
    return win


def jarvis_startup_screen(parent=None, duration=2500):
    """JARVIS açılış/yüklenme ekranı; DEL BIOS'u açar."""
    import tkinter as tk
    win = tk.Toplevel(parent) if parent is not None else tk.Tk()
    win.title("J.A.R.V.I.S.")
    win.geometry("900x550")
    win.configure(bg="black")
    win.resizable(False, False)

    tk.Label(
        win, text="J.A.R.V.I.S.", bg="black", fg="#00eaff",
        font=("Consolas", 36, "bold")
    ).pack(pady=(90, 10))

    status = tk.Label(
        win, text="SYSTEM INITIALIZING...", bg="black",
        fg="#00ff66", font=("Consolas", 14)
    )
    status.pack(pady=10)

    tk.Label(
        win, text="PRESS DEL TO ENTER BIOS", bg="black",
        fg="#00aaff", font=("Consolas", 12)
    ).pack(pady=20)

    bar = tk.Canvas(win, width=600, height=16,
                    bg="#111111", highlightthickness=0)
    bar.pack(pady=25)
    fill = bar.create_rectangle(0, 0, 0, 16, fill="#00eaff", outline="")

    steps = [
        "CHECKING SYSTEM...",
        "LOADING JARVIS CORE...",
        "CONNECTING TELEGRAM...",
        "LOADING AI SYSTEM...",
        "STARTING JARVIS..."
    ]

    def update(i=0):
        if i >= len(steps):
            win.destroy()
            return
        status.config(text=steps[i])
        bar.coords(fill, 0, 0, 600 * (i + 1) / len(steps), 16)
        win.after(max(1, duration // len(steps)), lambda: update(i + 1))

    win.bind("<Delete>", lambda e: jarvis_fake_bios(win))
    win.focus_force()
    update()
    return win



def start_jarvis_live_view(token, chat_id):
    global JARVIS_LIVE_VIEW_ACTIVE, JARVIS_LIVE_THREAD

    if JARVIS_LIVE_VIEW_ACTIVE:
        return "🔴 Canlı görüntü zaten açık."

    JARVIS_LIVE_VIEW_ACTIVE = True

    if JARVIS_LIVE_SERVER is None:
        JARVIS_LIVE_THREAD = threading.Thread(
            target=_jarvis_live_server_worker,
            daemon=True
        )
        JARVIS_LIVE_THREAD.start()
        time.sleep(0.7)

    lan_ip = _jarvis_get_lan_ip()
    lan_url = f"http://{lan_ip}:{JARVIS_LIVE_PORT}/"
    local_url = f"http://127.0.0.1:{JARVIS_LIVE_PORT}/"

    # Open the page automatically on the JARVIS computer.
    try:
        import webbrowser
        webbrowser.open(local_url, new=2)
    except Exception:
        pass

    send_text(
        token,
        chat_id,
        "🔴 JARVIS CANLI GÖRÜNTÜ BAŞLADI.\n\n"
        f"💻 Bu bilgisayarda: {local_url}\n"
        f"📱 Aynı Wi-Fi'daki telefonda: {lan_url}\n\n"
        "⏹️ Durdurmak için 15 yaz."
    )
    return None


def stop_jarvis_live_view():
    global JARVIS_LIVE_VIEW_ACTIVE, JARVIS_LIVE_SERVER

    JARVIS_LIVE_VIEW_ACTIVE = False

    try:
        if JARVIS_LIVE_SERVER is not None:
            JARVIS_LIVE_SERVER.shutdown()
            JARVIS_LIVE_SERVER.server_close()
            JARVIS_LIVE_SERVER = None
    except Exception:
        pass

    return "⏹️ CANLI GÖRÜNTÜ DURDURULDU."



async def foto_handler(update, context):
    if not update.message or not update.message.photo:
        return

    msg = await update.message.reply_text("🔍 Fotoğraf analiz ediliyor...")

    model = get_yolo()
    if model is None:
        await msg.edit_text(
            "📸 Fotoğrafı aldım efendim.\n"
            "Görsel analiz modülü bu bilgisayarda hazır değil. "
            "Metin özellikleri çalışmaya devam ediyor."
        )
        return

    try:
        photo = await update.message.photo[-1].get_file()
        data = await photo.download_as_bytearray()

        image = Image.open(io.BytesIO(data)).convert("RGB")
        results = model(image, verbose=False)

        names = {}
        for box in results[0].boxes:
            cls = int(box.cls)
            conf = float(box.conf) * 100
            name = model.names[cls]
            names[name] = max(names.get(name, 0), conf)

        if not names:
            await msg.edit_text("😕 Fotoğrafta tanıyabildiğim bir nesne bulamadım.")
            return

        lines = ["📸 Tespit edilen nesneler:"]
        for name, conf in sorted(names.items(), key=lambda x: -x[1])[:10]:
            lines.append(f"• {name} — %{conf:.1f}")

        await msg.edit_text("\n".join(lines))
    except Exception as e:
        await msg.edit_text(f"❌ Fotoğraf analiz hatası: {e}")


async def ekran_handler(update, context):
    """Bilgisayar ekran görüntüsünü Telegram'a gönderir."""
    if not update.message:
        return

    try:
        from PIL import ImageGrab

        screenshot_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "jarvis_ekran.png"
        )

        image = ImageGrab.grab()
        image.save(screenshot_path, "PNG")

        with open(screenshot_path, "rb") as photo:
            await update.message.reply_photo(
                photo=photo,
                caption="🖥️ J.A.R.V.I.S. ekran görüntüsü."
            )

        try:
            os.remove(screenshot_path)
        except Exception:
            pass

    except Exception as e:
        await update.message.reply_text(f"❌ Ekran görüntüsü alınamadı: {e}")


# -------------------- GERÇEK WEBCAM --------------------
WEBCAM_LOCK = threading.Lock()
WEBCAM_LAST_FRAME = None
WEBCAM_ACTIVE = False


def capture_webcam_photo(path=None, camera_index=0):
    """Gerçek bilgisayar kamerasından tek kare alır ve PNG olarak kaydeder."""
    try:
        import cv2
    except ImportError:
        raise RuntimeError("Kamera için opencv-python kurulmalı.")
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_camera.png")
    cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW if os.name == "nt" else 0)
    if not cap.isOpened():
        cap.release()
        raise RuntimeError("Kamera açılamadı. Kamera kullanım iznini ve USB bağlantısını kontrol et.")
    try:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        ok, frame = cap.read()
        if not ok:
            raise RuntimeError("Kameradan görüntü alınamadı.")
        cv2.imwrite(path, frame, [cv2.IMWRITE_PNG_COMPRESSION, 3])
        return path
    finally:
        cap.release()


def send_camera_photo(token, chat_id):
    """Telegram'a gerçek webcam fotoğrafı gönderir."""
    try:
        import requests
        path = capture_webcam_photo()
        with open(path, "rb") as f:
            telegram_request(
                token, "sendPhoto",
                {"chat_id": chat_id, "caption": "📷 J.A.R.V.I.S. gerçek kamera görüntüsü."},
                {"photo": ("jarvis_camera.png", f, "image/png")},
                timeout=60
            )
        try: os.remove(path)
        except Exception: pass
        gui_add_chat("📷 Kamera", "Gerçek kamera fotoğrafı Telegram'a gönderildi.")
    except Exception as e:
        send_text(token, chat_id, f"❌ Kamera fotoğrafı alınamadı: {e}")


# -------------------- TELEGRAM --------------------
# Doğrudan Telegram Bot API kullanır. Ek Telegram kütüphanesi gerekmez.

TELEGRAM_API = "https://api.telegram.org/bot{}"
telegram_session = None


def telegram_request(token, method, data=None, files=None, timeout=30):
    global telegram_session
    import requests

    if telegram_session is None:
        telegram_session = requests.Session()

    token = token.strip()
    if not token:
        raise RuntimeError("Token boş.")

    response = telegram_session.post(
        TELEGRAM_API.format(token) + "/" + method,
        data=data or {},
        files=files,
        timeout=timeout
    )

    try:
        result = response.json()
    except Exception:
        raise RuntimeError(f"Telegram cevap vermedi. HTTP {response.status_code}")

    if not result.get("ok"):
        raise RuntimeError(result.get("description", "Telegram API hatası"))

    return result.get("result")


def send_text(token, chat_id, text):
    message = str(text)[:4000]
    telegram_request(
        token, "sendMessage",
        {"chat_id": chat_id, "text": message},
        timeout=20
    )
    gui_add_chat("🤖 J.A.R.V.I.S.", message)


def send_screen(token, chat_id):
    try:
        from PIL import ImageGrab
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_ekran.png")
        ImageGrab.grab().save(path, "PNG")

        with open(path, "rb") as f:
            telegram_request(
                token, "sendPhoto",
                {"chat_id": chat_id, "caption": "🖥️ J.A.R.V.I.S. ekran görüntüsü."},
                {"photo": ("jarvis_ekran.png", f, "image/png")},
                timeout=60
            )

        try:
            os.remove(path)
        except Exception:
            pass
    except Exception as e:
        send_text(token, chat_id, f"❌ Ekran görüntüsü alınamadı: {e}")


def get_weather(city):
    import requests
    try:
        url = "https://wttr.in/" + urllib.parse.quote(city) + "?format=j1"
        r = requests.get(url, timeout=10, headers={"User-Agent": "JARVIS/1.0"})
        r.raise_for_status()
        data = r.json()
        cur = data["current_condition"][0]
        desc = cur.get("lang_tr", [{"value": ""}])[0].get("value") or cur.get("weatherDesc", [{"value": ""}])[0].get("value")
        return (f"🌤️ {city}: {desc}\n"
                f"🌡️ Sıcaklık: {cur.get('temp_C','?')}°C\n"
                f"💧 Nem: %{cur.get('humidity','?')}\n"
                f"💨 Rüzgar: {cur.get('windspeedKmph','?')} km/s")
    except Exception as e:
        return f"❌ Hava durumu alınamadı: {e}"


def list_apps():
    return ("📱/💻 Erişilebilir uygulamalar\n"
            "• Chrome / Google\n• YouTube\n• Not Defteri\n"
            "• Hesap Makinesi\n• Dosya Yöneticisi")


def open_app_command(name):
    aliases = {
        "chrome": "chrome", "google": "chrome", "youtube": "youtube",
        "notepad": "notepad", "not defteri": "notepad",
        "hesap makinesi": "hesap makinesi", "calculator": "calculator",
        "dosya": "dosya yöneticisi", "dosya yöneticisi": "dosya yöneticisi"
    }
    key = name.lower().strip()
    target = aliases.get(key)
    if not target:
        return False, "❌ Uygulama bulunamadı. /uygulamalar yaz."
    return open_program(target)


def transcribe_voice(token,file_id):
    """Telegram voice -> Türkçe metin. faster-whisper kuruluysa çalışır."""
    try:
        import tempfile
        import requests
        info=telegram_request(token,'getFile',{'file_id':file_id},timeout=20)
        path=info.get('result',{}).get('file_path')
        if not path: return None,'Telegram ses dosyasını bulamadı.'
        raw=requests.get(f'https://api.telegram.org/file/bot{token}/{path}',timeout=30).content
        ext=Path(path).suffix or '.ogg'
        fd=tempfile.NamedTemporaryFile(delete=False,suffix=ext); fd.write(raw); fd.close()
        try:
            from faster_whisper import WhisperModel
            model=WhisperModel(os.environ.get('JARVIS_WHISPER_MODEL','small'),device='cpu',compute_type='int8')
            segs,_=model.transcribe(fd.name,language='tr')
            return ' '.join(s.text.strip() for s in segs).strip(),None
        finally:
            try: os.remove(fd.name)
            except Exception: pass
    except ImportError:
        # faster-whisper yoksa OpenAI ses transkripsiyonuna geç.
        try:
            if not OPENAI_API_KEY_RUNTIME:
                return None,'Sesli sohbet için faster-whisper kurulmalı veya OpenAI API anahtarı gerekli.'
            import requests
            with open(fd.name, 'rb') as audio_file:
                rr = requests.post(
                    'https://api.openai.com/v1/audio/transcriptions',
                    headers={'Authorization': f'Bearer {OPENAI_API_KEY_RUNTIME}'},
                    files={'file': audio_file},
                    data={'model': 'gpt-4o-mini-transcribe', 'language': 'tr'},
                    timeout=60
                )
            if rr.ok:
                return rr.json().get('text','').strip(), None
            return None, 'OpenAI ses transkripsiyonu başarısız oldu.'
        except Exception as e:
            return None,str(e)
    except Exception as e:
        return None,str(e)

def handle_telegram_message(token, message):
    global last_chat_id

    chat_id = message.get("chat", {}).get("id")
    if chat_id is None:
        return

    last_chat_id = chat_id

    voice_obj=message.get("voice")
    if voice_obj:
        transcript,err=transcribe_voice(token,voice_obj.get("file_id"))
        if transcript:
            gui_add_chat("🎙️ Telegram", transcript)
            answer=ai_answer(transcript)
            send_text(token,chat_id,answer)
        else:
            send_text(token,chat_id,"🎙️ Sesli mesaj alınamadı: "+str(err))
        return

    text_msg = message.get("text", "").strip()

    if text_msg:
        gui_add_chat("📩 Telegram", text_msg)

    if text_msg == "1":
        gui_add_chat("🖥️ Sistem", "Ekran görüntüsü Telegram'a gönderiliyor...")
        send_screen(token, chat_id)
        return

    if text_msg == "/start":
        name = message.get("from", {}).get("first_name", "Efendim")
        send_text(token, chat_id,
                  f"🤖 J.A.R.V.I.S. AKTİF\n\nMerhaba {name}.\n"
                  f"Telegram bağlantısı başarıyla kuruldu.\n\n/yardim")
    elif text_msg == "/yardim":
        send_text(
            token, chat_id,
            jarvis.yardim() + "\n\n"
            "🤖 OTOMASYONLAR\n"
            "1 → Ekran görüntüsü\n"
            "2 → Bilgisayarı kilitle\n"
            "3 → Yeniden başlat\n"
            "4 → Kapat\n"
            "5 → Panoyu göster\n"
            "6 → PC durumunu göster\n"
            "7 → Klasörü aç\n"
            "8 → Not Defteri aç\n"
            "9 → Tarayıcı aç\n"
            "10 → Dosya yöneticisi\n"
            "13 → YouTube aç\n"
            "14 → Canlı ekran görüntüsü başlat\n"
            "15 → Canlı ekran görüntüsünü durdur\n"
            "16 → GERÇEK KAMERA fotoğrafını Telegram'a gönder\n"
            "11 dakika mesaj → Hatırlatma kur\n"
            "12 → Hatırlatmaları göster\n"
            "/durum → PC durumu\n"
            "/saat → Tarih ve saat\n"
            "/programlar → Program listesi\n"
            "/uygulamalar → Uygulamalar\n"
            "/ac chrome → Uygulama aç\n"
            "/hava Istanbul → Hava durumu\n\n"
            "💬 Örnek: 11 10 10 dakika sonra oyunu kontrol et"
        )
    elif text_msg == "/ekran":
        send_screen(token, chat_id)

    elif text_msg.startswith("/hava") or text_msg.lower().startswith("hava durumu"):
        parts = text_msg.split(" ", 1)
        city = parts[1].strip() if len(parts) > 1 and parts[1].strip() else "Istanbul"
        send_text(token, chat_id, get_weather(city))

    elif text_msg == "/uygulamalar":
        send_text(token, chat_id, list_apps())

    elif text_msg.startswith("/ac "):
        ok, result = open_app_command(text_msg[4:].strip())
        send_text(token, chat_id, result)

    elif text_msg.startswith("/uyandir") or text_msg.startswith("/uyandır"):
        parts=text_msg.split(maxsplit=1)
        mac=parts[1].strip() if len(parts)>1 else os.environ.get("JARVIS_PC_MAC","")
        if not mac:
            send_text(token,chat_id,"⚡ JARVIS_PC_MAC ayarlı değil. PC'nin MAC adresini ayarla.")
        else:
            try:
                wake_on_lan(mac,os.environ.get("JARVIS_WOL_BROADCAST","255.255.255.255"))
                send_text(token,chat_id,"⚡ Bilgisayarı uyandırma paketi gönderildi.")
            except Exception as e: send_text(token,chat_id,"❌ Uyandırma hatası: "+str(e))

    elif text_msg == "/durum":
        send_text(token, chat_id, computer_status())

    elif text_msg == "/saat":
        send_text(token, chat_id, "🕐 " + time.strftime("%d.%m.%Y %H:%M:%S"))

    elif text_msg == "/programlar":
        send_text(
            token, chat_id,
            "📋 Tanımlı programlar:\n"
            "• Chrome / Google\n"
            "• YouTube\n"
            "• Not Defteri\n"
            "• Hesap Makinesi\n"
            "• Dosya Yöneticisi"
        )

    elif text_msg == "2" or text_msg.lower() in ("bilgisayarı kilitle", "bilgisayari kilitle"):
        send_text(token, chat_id, "🔒 Bilgisayar 2 saniye içinde kilitleniyor.")
        threading.Timer(2, lock_computer).start()

    elif text_msg == "3" or text_msg.lower() in ("bilgisayarı yeniden başlat", "bilgisayari yeniden baslat"):
        send_text(token, chat_id, "🔄 Bilgisayar 10 saniye içinde yeniden başlatılacak.")
        restart_computer()

    elif text_msg == "4" or text_msg.lower() in ("bilgisayarı kapat", "bilgisayari kapat"):
        send_text(token, chat_id, "⏻ Bilgisayar 10 saniye içinde kapanacak.")
        shutdown_computer()

    elif text_msg == "5":
        try:
            clipboard = root.clipboard_get() if "root" in globals() else ""
            send_text(token, chat_id, "📋 Pano:\n" + str(clipboard)[:3500])
        except Exception as e:
            send_text(token, chat_id, f"❌ Pano okunamadı: {e}")

    elif text_msg == "6":
        send_text(token, chat_id, computer_status())

    elif text_msg == "7":
        import os
        os.startfile(os.path.expanduser("~"))
        send_text(token, chat_id, "📂 Dosya klasörü açıldı.")

    elif text_msg == "8":
        ok, result = open_program("notepad")
        send_text(token, chat_id, result)

    elif text_msg == "9":
        import webbrowser
        webbrowser.open("https://www.google.com")
        send_text(token, chat_id, "🌐 Tarayıcı açıldı.")

    elif text_msg == "10":
        import os
        os.startfile(os.path.expanduser("~"))
        send_text(token, chat_id, "📁 Dosya yöneticisi açıldı.")

    elif text_msg.startswith("11 "):
        parts = text_msg.split(" ", 2)
        if len(parts) == 3:
            try:
                minutes = int(parts[1])
                schedule_reminder(token, chat_id, minutes, parts[2])
                send_text(token, chat_id, f"⏰ {minutes} dakika sonrası için hatırlatma kuruldu.")
            except ValueError:
                send_text(token, chat_id, "❌ Kullanım: 11 10 Hatırlatma mesajı")

    elif text_msg == "12":
        if automation_timers:
            lines = ["⏰ Aktif hatırlatmalar:"]
            for minutes, msg in automation_timers[-10:]:
                lines.append(f"• {minutes} dk — {msg}")
            send_text(token, chat_id, "\n".join(lines))
        else:
            send_text(token, chat_id, "⏰ Aktif hatırlatma yok.")

    elif text_msg.lower() in ("chrome aç", "chrome ac", "google aç", "google ac"):
        ok, result = open_program("chrome")
        send_text(token, chat_id, result)

    elif text_msg.lower() in ("youtube aç", "youtube ac"):
        ok, result = open_program("youtube")
        send_text(token, chat_id, result)

    elif text_msg.lower() in ("not defteri aç", "not defteri ac"):
        ok, result = open_program("notepad")
        send_text(token, chat_id, result)

    elif text_msg.lower() in ("hesap makinesini aç", "hesap makinesini ac"):
        ok, result = open_program("hesap makinesi")
        send_text(token, chat_id, result)

    elif text_msg == "16" or text_msg.lower() in ("kamera", "/kamera", "fotoğraf çek", "fotograf cek", "kamera fotoğrafı", "kamera fotografi"):
        send_text(token, chat_id, "📷 Gerçek kamera açılıyor...")
        send_camera_photo(token, chat_id)
        return

    elif text_msg == "14":
        result = start_jarvis_live_view(token, chat_id)
        if result:
            send_text(token, chat_id, result)
        return

    elif text_msg == "15":
        send_text(token, chat_id, stop_jarvis_live_view())
        return

    elif text_msg == "13":
        import webbrowser
        webbrowser.open("https://www.youtube.com")
        send_text(token, chat_id, "▶️ YouTube açıldı.")

    elif text_msg:
        answer=ai_answer(text_msg)
        send_text(token,chat_id,answer)
    elif message.get("photo"):
        send_text(token, chat_id, "📸 Fotoğraf alındı.")


def telegram_worker(token, status_callback):
    global bot_running, stop_requested, REQUESTS_OK, gui_token, telegram_session

    try:
        if not REQUESTS_OK:
            status_callback("🟡 Telegram modülü hazırlanıyor...")
            if not install_package("requests", "requests"):
                raise RuntimeError("requests kurulamadı. İnternet bağlantısını kontrol et.")
            REQUESTS_OK = True

        token = token.strip()
        if ":" not in token:
            raise RuntimeError("Token hatalı. BotFather tokenını tekrar kopyala.")

        status_callback("🟡 Telegram'a bağlanılıyor...")

        # Token doğrulama
        me = telegram_request(token, "getMe", timeout=20)
        username = me.get("username", "")

        if not username:
            raise RuntimeError("Bot kullanıcı adı alınamadı.")

        # Webhook'u kaldır
        telegram_request(
            token,
            "deleteWebhook",
            {"drop_pending_updates": False},
            timeout=20
        )

        bot_running = True
        stop_requested = False
        global gui_token
        gui_token = token
        offset = 0

        status_callback(f"🟢 TELEGRAM BAĞLANDI: @{username}")

        # Telegram açıldığında kullanıcıya otomasyonları hatırlat.
        try:
            send_text(
                token,
                last_chat_id,
                "🔔 J.A.R.V.I.S. otomasyonları hazır. /yardim yazarsan tüm komutları gösterebilirim."
            ) if last_chat_id is not None else None
        except Exception:
            pass

        while not stop_requested:
            try:
                updates = telegram_request(
                    token,
                    "getUpdates",
                    {
                        "offset": offset,
                        "timeout": 20,
                        "allowed_updates": '["message"]'
                    },
                    timeout=30
                ) or []

                for update in updates:
                    offset = update.get("update_id", offset) + 1
                    message = update.get("message")

                    if message:
                        try:
                            handle_telegram_message(token, message)
                        except Exception as e:
                            print("Mesaj hatası:", e)

            except Exception as e:
                if stop_requested:
                    break
                status_callback(f"🟠 Telegram yeniden bağlanıyor: {e}")
                time.sleep(3)

        bot_running = False
        gui_token = None
        status_callback("⚪ Telegram durduruldu.")

    except Exception as e:
        bot_running = False
        gui_token = None
        status_callback(f"🔴 TELEGRAM HATASI: {e}")


# -------------------- WINDOWS ARAYÜZÜ --------------------



class JarvisGUI:
    """J.A.R.V.I.S. control-center GUI inspired by the supplied three-monitor HUD reference.
    The interface uses only JARVIS/system terminology and preserves the existing backend.
    """
    def __init__(self, root):
        self.root=root
        self.root.title(APP_TITLE + " • FX Control Center")
        self.root.geometry("1600x900+80+40")
        self.root.minsize(1180,720)
        try:
            self.root.state("normal")
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
        except Exception:
            pass
        self.root.configure(bg="#020914")
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.cyan="#43dcff"; self.cyan2="#087eb2"; self.text="#d9f4ff"; self.muted="#6d9caf"
        self.panel="#06172a"; self.panel2="#082044"; self.line="#0e5a86"; self.green="#40f0b0"
        self.orange="#ffbd55"; self.red="#ff5e70"; self.blue="#0c7da7"
        self.commands=0; self.started_at=time.time(); self.camera_running=False; self.camera_capture=None; self.connecting=False
        self._phase=0
        self._build(); self.update_clock(); self.update_pc_dashboard(); self.update_weather_display(); self._animate_core()
        saved=self.load_token()
        if saved:
            self.token_var.set(saved); self.set_status("Telegram token hazır. BAĞLAN düğmesine bas.", self.orange)

    def _panel(self,parent,title,subtitle=""):
        f=tk.Frame(parent,bg=self.panel,highlightbackground=self.line,highlightthickness=1)
        h=tk.Frame(f,bg="#09234a",height=34); h.pack(fill="x"); h.pack_propagate(False)
        tk.Label(h,text=title,font=("Segoe UI",12,"bold"),fg=self.cyan,bg="#09234a").pack(side="left",padx=12)
        if subtitle:
            tk.Label(h,text=subtitle,font=("Consolas",8,"bold"),fg="#68b7dc",bg="#09234a").pack(side="right",padx=10)
        return f

    def _build(self):
        # Header
        top=tk.Frame(self.root,bg="#020b17",height=58,highlightbackground="#0c3455",highlightthickness=1)
        top.pack(fill="x"); top.pack_propagate(False)
        tk.Label(top,text="J.A.R.V.I.S",font=("Segoe UI",24,"bold"),fg="#eafaff",bg="#020b17").pack(side="left",padx=18)
        self.online_label=tk.Label(top,text="● ONLINE",font=("Consolas",9,"bold"),fg=self.green,bg="#06271f",padx=8,pady=4); self.online_label.pack(side="left")
        self.clock_label=tk.Label(top,text="◷ --:--:--  |  ---",font=("Consolas",11,"bold"),fg=self.text,bg="#071a2d",padx=12,pady=6); self.clock_label.place(relx=.5,rely=.5,anchor="center")
        right=tk.Frame(top,bg="#020b17"); right.pack(side="right",padx=12)
        self.weather_top=tk.Label(right,text="♨ --.-°C",font=("Segoe UI",9),fg="#bfe7f5",bg="#071a2d",padx=9,pady=6); self.weather_top.pack(side="left",padx=3)
        self.telegram_state=tk.Label(right,text="TELEGRAM: AYRIK",font=("Consolas",8,"bold"),fg=self.orange,bg="#2b200c",padx=8,pady=6); self.telegram_state.pack(side="left",padx=3)
        self.connect_btn=tk.Button(right,text="BAĞLAN",command=self.start_bot,font=("Segoe UI",8,"bold"),fg="white",bg="#0b7ca5",activebackground="#10a4d2",relief="flat",padx=10,pady=6); self.connect_btn.pack(side="left",padx=2)
        self.disconnect_btn=tk.Button(right,text="ÇIKIŞ",command=self.stop_bot,font=("Segoe UI",8,"bold"),fg="white",bg="#723344",activebackground="#9b4055",relief="flat",padx=10,pady=6,state="disabled"); self.disconnect_btn.pack(side="left",padx=2)
        tk.Button(right,text="⚙",command=self.settings_dialog,font=("Segoe UI",12),fg="#b9e8f5",bg="#071a2d",activebackground="#123452",relief="flat",bd=0,width=3).pack(side="left",padx=3)

        body=tk.Frame(self.root,bg="#020914"); body.pack(fill="both",expand=True,padx=10,pady=9)
        body.grid_columnconfigure((0,1,2),weight=1,uniform="screen")
        body.grid_rowconfigure(0,weight=7); body.grid_rowconfigure(1,weight=3)

        # Three large monitor panels, matching the supplied layout but with JARVIS content.
        left=self._panel(body,"JARVIS CORE","MUT • CORE / DATA"); left.grid(row=0,column=0,sticky="nsew",padx=(0,5))
        center=self._panel(body,"JARVIS PROCESSING","MUT • AI / EQU"); center.grid(row=0,column=1,sticky="nsew",padx=5)
        rightp=self._panel(body,"SYSTEM MONITOR","MUT • SYSTEM / EQU"); rightp.grid(row=0,column=2,sticky="nsew",padx=(5,0))

        # Left: core visualization + system figures
        lc=tk.Canvas(left,bg="#041a3c",highlightthickness=0); lc.pack(fill="both",expand=True,padx=4,pady=4); self.core_monitor=lc
        self.core_metrics=[tk.StringVar(value="--") for _ in range(6)]
        # Center: processing visualization
        cc=tk.Canvas(center,bg="#041a3c",highlightthickness=0); cc.pack(fill="both",expand=True,padx=4,pady=4); self.process_canvas=cc
        # Right: live camera / system monitor area
        rc=tk.Frame(rightp,bg="#041a3c"); rc.pack(fill="both",expand=True,padx=4,pady=4)
        self.cam_box=tk.Frame(rc,bg="#02162e",highlightbackground="#126195",highlightthickness=1); self.cam_box.pack(fill="both",expand=True,padx=8,pady=(8,4))
        self.cam_icon=tk.Label(self.cam_box,text="J.A.R.V.I.S",font=("Segoe UI",22,"bold"),fg="#35d8ff",bg="#02162e"); self.cam_icon.place(relx=.5,rely=.43,anchor="center")
        self.cam_text=tk.Label(self.cam_box,text="SYSTEM VISUALIZER • CAMERA OFF",font=("Consolas",9),fg="#4e91ae",bg="#02162e"); self.cam_text.place(relx=.5,rely=.61,anchor="center")
        self.cam_note=tk.Label(rc,text="Gerçek kamera için CAMERA / 16",font=("Consolas",8),fg="#5f9eb8",bg="#041a3c"); self.cam_note.pack(pady=(2,5))
        tk.Button(rc,text="⏻ CAMERA",command=self.toggle_camera,font=("Segoe UI",8,"bold"),fg=self.text,bg="#0b3150",activebackground="#125b80",relief="flat",padx=8,pady=5).pack(side="bottom",pady=5)

        # Bottom control center: same broad horizontal composition as the reference.
        bottom=tk.Frame(body,bg=self.panel,highlightbackground=self.line,highlightthickness=1); bottom.grid(row=1,column=0,columnspan=3,sticky="nsew",pady=(8,0))
        bh=tk.Frame(bottom,bg="#09234a",height=32); bh.pack(fill="x"); bh.pack_propagate(False)
        tk.Label(bh,text="CONTROL PANEL • J.A.R.V.I.S",font=("Segoe UI",11,"bold"),fg=self.text,bg="#09234a").pack(anchor="center")
        content=tk.Frame(bottom,bg="#06172a"); content.pack(fill="both",expand=True,padx=6,pady=6)
        content.grid_columnconfigure(0,weight=2); content.grid_columnconfigure(1,weight=3); content.grid_columnconfigure(2,weight=2); content.grid_rowconfigure(0,weight=1)

        # Data left
        data=tk.Frame(content,bg="#06172a"); data.grid(row=0,column=0,sticky="nsew",padx=8)
        tk.Label(data,text="CONTROL CENTER",font=("Segoe UI",12,"bold"),fg=self.cyan,bg="#06172a").pack(pady=(5,2))
        tk.Label(data,text="J.A.R.V.I.S  •  FILES & DATA",font=("Consolas",9),fg="#6aa8c2",bg="#06172a").pack()
        grid=tk.Frame(data,bg="#06172a"); grid.pack(fill="both",expand=True,pady=5)
        self.cpu_cell=tk.Label(grid,text="--",font=("Consolas",14,"bold"),fg=self.text,bg="#071d38",width=8); self.cpu_cell.grid(row=0,column=0,padx=3,pady=3,sticky="nsew")
        self.mem_cell=tk.Label(grid,text="--",font=("Consolas",14,"bold"),fg=self.text,bg="#071d38",width=8); self.mem_cell.grid(row=0,column=1,padx=3,pady=3,sticky="nsew")
        self.disk_cell=tk.Label(grid,text="--",font=("Consolas",12,"bold"),fg=self.text,bg="#071d38",width=11); self.disk_cell.grid(row=1,column=0,columnspan=2,padx=3,pady=3,sticky="nsew")
        self.cpu_pct=tk.Label(data,text="CPU --%",font=("Consolas",9),fg="#6eaec6",bg="#06172a"); self.cpu_pct.pack(side="left",padx=5)
        self.ram_gb=tk.Label(data,text="RAM --",font=("Consolas",9),fg="#6eaec6",bg="#06172a"); self.ram_gb.pack(side="left",padx=5)
        self.cpu_bar=self._bar(data,5); self.cpu_bar.pack(fill="x",pady=2)
        self.ram_bar=self._bar(data,5); self.ram_bar.pack(fill="x",pady=2)
        self.loadbar=self._bar(data,5); self.loadbar.pack(fill="x",pady=2); self._fill_bar(self.loadbar,25)
        self.load_label=tk.Label(data,text="SYSTEM LOAD 25%",font=("Consolas",8),fg="#6b9fb6",bg="#06172a"); self.load_label.pack()

        # Center controls and JARVIS status
        mid=tk.Frame(content,bg="#06172a"); mid.grid(row=0,column=1,sticky="nsew",padx=10)
        self.control_canvas=tk.Canvas(mid,bg="#06172a",highlightthickness=0); self.control_canvas.pack(fill="both",expand=True)
        self.control_canvas.bind("<Configure>",lambda e:self._draw_control())
        buttons=tk.Frame(mid,bg="#06172a"); buttons.pack(side="bottom",pady=4)
        for text,cmd in [("▣ CAMERA",self.toggle_camera),("🎙 VOICE",self.listen_microphone),("⌨ CHAT",self.focus_chat)]:
            tk.Button(buttons,text=text,command=cmd,font=("Segoe UI",9,"bold"),fg="#d9f5ff",bg="#0a3150",activebackground="#115c7c",relief="flat",padx=12,pady=6).pack(side="left",padx=5)
        self.status_label=tk.Label(mid,text="J.A.R.V.I.S READY • ALL SYSTEMS NOMINAL",font=("Consolas",9,"bold"),fg=self.green,bg="#06172a"); self.status_label.pack(side="bottom",pady=(2,5))

        # Conversation/data right
        chatf=tk.Frame(content,bg="#06172a"); chatf.grid(row=0,column=2,sticky="nsew",padx=8)
        ch=tk.Frame(chatf,bg="#06172a"); ch.pack(fill="x")
        tk.Label(ch,text="J.A.R.V.I.S CHAT",font=("Segoe UI",10,"bold"),fg=self.cyan,bg="#06172a").pack(side="left")
        tk.Button(ch,text="CLEAR",command=self.clear_chat,font=("Segoe UI",7,"bold"),fg=self.text,bg="#0b3150",relief="flat",padx=7,pady=4).pack(side="right",padx=2)
        tk.Button(ch,text="EXPORT",command=self.extract_chat,font=("Segoe UI",7,"bold"),fg=self.text,bg="#0b3150",relief="flat",padx=7,pady=4).pack(side="right",padx=2)
        self.chat_box=tk.Text(chatf,font=("Segoe UI",9),fg=self.text,bg="#04142a",insertbackground=self.cyan,relief="flat",wrap="word",bd=0,padx=8,pady=6,height=8); self.chat_box.pack(fill="both",expand=True,pady=4)
        self.chat_box.insert("end","J.A.R.V.I.S hazır.\nTelegram: BAĞLAN ile bağlan.\nKamera: CAMERA veya Telegram 16.\n\n","normal")
        self.chat_box.configure(state="disabled")
        composer=tk.Frame(chatf,bg="#071d38",highlightbackground="#126195",highlightthickness=1,height=34); composer.pack(fill="x"); composer.pack_propagate(False)
        self.chat_message=tk.StringVar(); self.message_entry=tk.Entry(composer,textvariable=self.chat_message,font=("Segoe UI",9),fg=self.text,bg="#071d38",insertbackground="white",relief="flat",bd=0); self.message_entry.pack(side="left",fill="both",expand=True,padx=7); self.message_entry.bind("<Return>",lambda e:self.send_gui_message())
        tk.Button(composer,text="➤",command=self.send_gui_message,font=("Segoe UI",10,"bold"),fg="white",bg=self.blue,relief="flat",bd=0,width=4).pack(side="right",fill="y")
        self.token_var=tk.StringVar(); self.token_entry=None
        global gui_chat; gui_chat=self.chat_box

    def _bar(self,parent,height=5):
        c=tk.Canvas(parent,height=height,bg="#0d2940",highlightthickness=0); c._fill=0; return c
    def _fill_bar(self,c,pct):
        c.delete("all"); w=max(1,c.winfo_width()); h=max(2,int(c.winfo_height())); c.create_rectangle(0,0,w*max(0,min(100,pct))/100,h,fill="#16bde7",outline="")
    def _draw_core(self):
        c=getattr(self,"core_monitor",None)
        if c is None:return
        c.delete("all"); w=max(300,c.winfo_width()); h=max(240,c.winfo_height()); cx=w*.5; cy=h*.49; r=min(w,h)*.27
        # orbital JARVIS core
        for rr,col in [(r*1.42,"#0d5b87"),(r*1.18,"#126a99"),(r*.96,"#1b7eab")]: c.create_oval(cx-rr,cy-rr,cx+rr,cy+rr,outline=col,width=2)
        c.create_oval(cx-r*.72,cy-r*.72,cx+r*.72,cy+r*.72,outline="#2b7fa7",width=12)
        c.create_oval(cx-r*.50,cy-r*.50,cx+r*.50,cy+r*.50,fill="#0b385a",outline="#4bd9ff",width=2)
        c.create_text(cx,cy,text="J.A.R.V.I.S",fill="#e9fbff",font=("Segoe UI",18,"bold"))
        c.create_text(cx,cy+27,text="CORE ONLINE",fill="#41f0b0",font=("Consolas",9,"bold"))
        c.create_text(18,22,text="CORE STATUS",anchor="w",fill="#66c9eb",font=("Consolas",9,"bold"))
        metrics=[("AI CORE","ONLINE"),("VOICE","READY"),("CAMERA","READY"),("TELEGRAM","LINKED" if bot_running else "OFFLINE"),("AUTOMATION","ACTIVE"),("SECURITY","NOMINAL")]
        y=48
        for i,(a,b) in enumerate(metrics):
            c.create_text(18,y,text=a,anchor="w",fill="#5d9bb7",font=("Consolas",8)); c.create_text(w-18,y,text=b,anchor="e",fill="#cceef7" if b!="OFFLINE" else "#ffbd55",font=("Consolas",8,"bold")); y+=20
    def _draw_process(self):
        c=self.process_canvas; c.delete("all"); w=max(300,c.winfo_width()); h=max(240,c.winfo_height()); mid=h*.55
        c.create_text(18,22,text="JARVIS PROCESSING",anchor="w",fill="#66c9eb",font=("Consolas",9,"bold"))
        # futuristic data grid + animated waveform
        for x in range(20,int(w),28): c.create_line(x,42,x,h-30,fill="#07345b")
        for y in range(50,int(h-25),24): c.create_line(10,y,w-10,y,fill="#07345b")
        import math
        pts=[]
        phase=self._phase/7
        for x in range(18,int(w-18),5):
            yy=mid+math.sin(x*.055+phase)*24+math.sin(x*.13-phase)*10
            pts.extend((x,yy))
        if len(pts)>3:c.create_line(*pts,fill="#28d5ff",width=3,smooth=True)
        c.create_text(w*.5,h*.22,text="AI / DATA STREAM",fill="#d8f7ff",font=("Segoe UI",20,"bold"))
        c.create_text(w*.5,h*.34,text="J.A.R.V.I.S  •  ANALYSIS  •  CONTROL",fill="#62c6e8",font=("Consolas",9,"bold"))
        for i,t in enumerate(["INPUT","ANALYSIS","RESPONSE","AUTOMATION"]):
            x=w*.15+i*w*.23; c.create_rectangle(x-42,h*.78,x+42,h*.86,outline="#0e638e",fill="#082341"); c.create_text(x,h*.82,text=t,fill="#9fe9ff",font=("Consolas",7,"bold"))
    def _draw_control(self):
        c=self.control_canvas; c.delete("all"); w=max(350,c.winfo_width()); h=max(120,c.winfo_height()); cx=w*.5; cy=h*.45
        for rr in (28,42,56): c.create_oval(cx-rr,cy-rr,cx+rr,cy+rr,outline="#0e5d84")
        c.create_oval(cx-18,cy-18,cx+18,cy+18,fill="#0d5273",outline="#42dcff")
        c.create_text(cx,cy,text="J",fill="#e8fbff",font=("Segoe UI",16,"bold"))
        c.create_text(cx,cy+72,text="CONTROL CENTER",fill="#dff9ff",font=("Segoe UI",13,"bold"))
        c.create_text(cx,cy+92,text="FILES • DATA • VOICE • TELEGRAM • AUTOMATION",fill="#56b8d8",font=("Consolas",8,"bold"))
        for side in (0,1):
            sx=65 if side==0 else w-65
            for j in range(7):
                yy=32+j*12; c.create_oval(sx-3,yy-3,sx+3,yy+3,fill="#18c8ef",outline="")
                c.create_line(sx+10 if side==0 else sx-10,yy,sx+70 if side==0 else sx-70,yy,fill="#0a4165")
    def _animate_core(self):
        try:
            self._phase+=1; self._draw_core(); self._draw_process(); self._draw_control(); self.root.after(90,self._animate_core)
        except Exception: pass


    def update_clock(self):
        n = datetime.datetime.now()
        self.clock_label.config(text=n.strftime('◷ %I:%M:%S %p  |  %b %d, %Y'))
        sec = int(time.time() - self.started_at)
        h = sec // 3600
        m = sec % 3600 // 60
        s = sec % 60
        val = f'{h:02d}:{m:02d}:{s:02d}'
        self.root.after(1000, self.update_clock)

    def update_pc_dashboard(self):
        try:
            if PSUTIL_OK:
                cpu = psutil.cpu_percent(interval=None)
                ram = psutil.virtual_memory()
                disk = psutil.disk_usage(os.getcwd())
                self.cpu_pct.config(text=f'{cpu:.0f}%')
                self._fill_bar(self.cpu_bar, cpu)
                self.ram_gb.config(text=f'{ram.used / 1024 ** 3:.1f} GB')
                self._fill_bar(self.ram_bar, ram.percent)
                self.cpu_cell.config(text=f'{cpu:.0f}%')
                self.mem_cell.config(text=f'{ram.percent:.0f}%')
                self.disk_cell.config(text=f'{disk.used / 1024 ** 3:.0f}/{disk.total / 1024 ** 3:.0f} GB')
                load = min(100, round(cpu * 0.55 + ram.percent * 0.25 + disk.percent * 0.2))
                self._fill_bar(self.loadbar, load)
                self.load_label.config(text=f"{('Low' if load < 35 else 'Moderate' if load < 70 else 'High')}   {load}%")
            else:
                self.cpu_pct.config(text='--')
                self.ram_gb.config(text='--')
        except Exception as e:
            self._log('[WARN] Sistem sensörü: ' + str(e))
        self.root.after(3000, self.update_pc_dashboard)

    def update_weather_display(self):

        def worker():
            try:
                r = get_weather('Istanbul')
            except Exception:
                r = 'Weather unavailable'
            self.root.after(0, lambda: self.weather_top.config(text='♨ ' + r.replace('\n', ' ')[:38]))
        threading.Thread(target=worker, daemon=True).start()
        self.root.after(600000, self.update_weather_display)

    def _log(self, msg):
        try:
            self.chat_box.configure(state='normal')
            self.chat_box.insert('end', msg + '\n')
            self.chat_box.see('end')
            self.chat_box.configure(state='disabled')
        except Exception:
            pass

    def clear_chat(self):
        self.chat_box.configure(state='normal')
        self.chat_box.delete('1.0', 'end')
        self.chat_box.configure(state='disabled')

    def extract_chat(self):
        try:
            text = self.chat_box.get('1.0', 'end-1c')
            p = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'jarvis-conversation.txt')
            with open(p, 'w', encoding='utf-8') as f:
                f.write(text)
            self._log('[CHAT] Konuşma dışa aktarıldı: ' + p)
        except Exception as e:
            messagebox.showerror('Conversation', str(e))

    def focus_chat(self):
        self.message_entry.focus_set()

    def listen_microphone(self):
        """Mikrofondan Türkçe konuşmayı dinle, JARVIS cevaplasın ve sesli okusun."""
        threading.Thread(target=self._voice_chat_worker, daemon=True).start()

    def _voice_chat_worker(self):
        try:
            self.root.after(0, lambda: self.set_status('🎙️ Dinliyorum...', self.cyan))
            try:
                import speech_recognition as sr
            except ImportError:
                if not install_package('SpeechRecognition', 'speech_recognition'):
                    raise RuntimeError('SpeechRecognition kurulamadı.')
                import speech_recognition as sr
            try:
                import pyaudio
            except ImportError:
                if not install_package('PyAudio', 'pyaudio'):
                    raise RuntimeError('PyAudio kurulamadı. Windows mikrofon sürücüsünü kontrol edin.')
            r = sr.Recognizer()
            with sr.Microphone() as source:
                self.root.after(0, lambda: self._log('[MIC] Konuşabilirsiniz...'))
                r.adjust_for_ambient_noise(source, duration=0.5)
                audio = r.listen(source, timeout=8, phrase_time_limit=18)
            try:
                text = r.recognize_google(audio, language='tr-TR')
            except Exception:
                raise RuntimeError('Konuşma anlaşılamadı. Mikrofonu ve internet bağlantısını kontrol edin.')
            self.root.after(0, lambda: self._show_user_message('🎙️ Siz', text))
            answer = ai_answer(text)
            self.root.after(0, lambda: self._show_user_message('🤖 J.A.R.V.I.S.', answer))
            self._speak(answer)
            self.root.after(0, lambda: self.set_status('🟢 Sesli sohbet hazır.', self.green))
        except Exception as e:
            self.root.after(0, lambda: self._log('[MIC] ' + str(e)))
            self.root.after(0, lambda: self.set_status('🔴 Mikrofon hatası', self.red))

    def _speak(self, text):
        """Windows'un yerleşik System.Speech motoruyla Türkçe seslendirmeyi dener."""
        try:
            safe = str(text).replace('"', "'").replace('`', '')[:2500]
            ps = f'Add-Type -AssemblyName System.Speech; $s=New-Object System.Speech.Synthesis.SpeechSynthesizer; $v=$s.GetInstalledVoices() | ForEach-Object {{$_.VoiceInfo}} | Where-Object {{$_.Culture.Name -match "^tr"}} | Select-Object -First 1; if($v){{$s.SelectVoice($v.Name)}}; $s.Speak("{safe}")'
            subprocess.Popen(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', ps], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            self._log('[TTS] ' + str(e))

    def _show_user_message(self, prefix, message):
        self._log(f'{prefix}: {message}')

    def toggle_camera(self):
        """Gerçek webcam'i aç/kapat ve canlı görüntüyü arayüzde göster."""
        if self.camera_running:
            self.stop_real_camera()
            return
        try:
            import cv2
            from PIL import Image, ImageTk
            self._cv2 = cv2
            self._Image = Image
            self._ImageTk = ImageTk
        except ImportError:
            self._log('[CAMERA] opencv-python ve Pillow gerekli. Kuruluyor...')
            ok = install_package('opencv-python', 'cv2')
            if not ok:
                self.cam_note.config(text='Kamera için opencv-python kurulamadı.')
                return
            try:
                from PIL import Image, ImageTk
                import cv2
                self._cv2, self._Image, self._ImageTk = (cv2, Image, ImageTk)
            except Exception as e:
                self.cam_note.config(text='Kamera modülü hazırlanamadı: ' + str(e))
                return
        try:
            self.camera_capture = self._cv2.VideoCapture(0, self._cv2.CAP_DSHOW if os.name == 'nt' else 0)
            if not self.camera_capture.isOpened():
                self.camera_capture.release()
                self.camera_capture = None
                raise RuntimeError('Kamera açılamadı. Başka uygulama kamerayı kullanıyor olabilir.')
            self.camera_capture.set(self._cv2.CAP_PROP_FRAME_WIDTH, 1920)
            self.camera_capture.set(self._cv2.CAP_PROP_FRAME_HEIGHT, 1080)
            self.camera_running = True
            self.cam_icon.place_forget()
            self.cam_text.place_forget()
            self.cam_note.config(text='Camera is active • 1080p capture')
            self._camera_update()
            self._log('[CAMERA] Gerçek kamera bağlandı.')
        except Exception as e:
            self.camera_capture = None
            self.cam_note.config(text='Kamera bağlanamadı: ' + str(e))
            self._log('[CAMERA] ' + str(e))

    def _camera_update(self):
        if not self.camera_running or not getattr(self, 'camera_capture', None):
            return
        try:
            ok, frame = self.camera_capture.read()
            if ok:
                frame = self._cv2.cvtColor(frame, self._cv2.COLOR_BGR2RGB)
                image = self._Image.fromarray(frame)
                box_w = max(120, self.cam_box.winfo_width() - 4)
                box_h = max(90, self.cam_box.winfo_height() - 4)
                image.thumbnail((box_w, box_h), self._Image.Resampling.LANCZOS)
                photo = self._ImageTk.PhotoImage(image=image)
                self.cam_box.config(bg='#02070b')
                self.cam_icon.config(image=photo, text='', bg='#02070b')
                self.cam_icon.image = photo
                self.cam_icon.place(relx=0.5, rely=0.5, anchor='center')
            self.root.after(30, self._camera_update)
        except Exception as e:
            self._log('[CAMERA] Kare okuma hatası: ' + str(e))
            self.stop_real_camera()

    def stop_real_camera(self):
        self.camera_running = False
        cap = getattr(self, 'camera_capture', None)
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass
        self.camera_capture = None
        self.cam_icon.config(image='', text='▣', bg='#061019')
        self.cam_icon.image = None
        self.cam_icon.place(relx=0.5, rely=0.4, anchor='center')
        self.cam_text.config(text='Camera Off', fg='#477989', bg='#061019')
        self.cam_text.place(relx=0.5, rely=0.65, anchor='center')
        self.cam_note.config(text='Camera is inactive. Click the power button to start.')
        self._log('[CAMERA] Kamera bağlantısı kesildi.')

    def settings_dialog(self):
        win = tk.Toplevel(self.root)
        win.title('J.A.R.V.I.S. • Telegram Settings')
        win.geometry('600x360')
        win.configure(bg='#050a0f')
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()
        tk.Label(win, text='J.A.R.V.I.S.', font=('Segoe UI', 22, 'bold'), fg=self.cyan, bg='#050a0f').pack(pady=(20, 5))
        tk.Label(win, text='Telegram Bot Token', font=('Segoe UI', 11, 'bold'), fg=self.text, bg='#050a0f').pack(anchor='w', padx=40)
        var = tk.StringVar(value=self.token_var.get())
        ent = tk.Entry(win, textvariable=var, show='•', font=('Consolas', 12), fg='white', bg='#0a2029', insertbackground='white', relief='flat')
        ent.pack(fill='x', padx=40, pady=10, ipady=9)
        self.settings_entry = ent

        def save():
            token = var.get().strip()
            self.token_var.set(token)
            self.save_token(token)
            self.set_status('Token kaydedildi.', self.green)
            win.destroy()
        row = tk.Frame(win, bg='#050a0f')
        row.pack(fill='x', padx=40, pady=12)
        tk.Button(row, text='KAYDET', command=save, font=('Segoe UI', 10, 'bold'), fg='white', bg='#24506e', relief='flat', padx=18, pady=9).pack(side='left')
        tk.Button(row, text='BAĞLAN', command=lambda: (save(), self.start_bot()), font=('Segoe UI', 10, 'bold'), fg='white', bg='#087ea4', relief='flat', padx=18, pady=9).pack(side='left', padx=8)
        tk.Button(row, text='BAĞLANTIDAN ÇIK', command=lambda: (save(), self.stop_bot()), font=('Segoe UI', 10, 'bold'), fg='white', bg='#733442', relief='flat', padx=18, pady=9).pack(side='left')
        tk.Label(win, text='Token yalnızca bu bilgisayardaki jarvis_token.txt dosyasına kaydedilir.', font=('Segoe UI', 9), fg=self.muted, bg='#050a0f').pack(pady=8)
        ent.focus_set()

    def send_gui_message(self):
        global gui_token, last_chat_id
        m = self.chat_message.get().strip()
        if not m:
            return
        self._log('👤 You: ' + m)
        self.chat_message.set('')
        self.commands += 1
        self.command_label.config(text=str(self.commands))
        if bot_running and gui_token and (last_chat_id is not None):
            try:
                send_text(gui_token, last_chat_id, m)
                return
            except Exception as e:
                self._log('[TELEGRAM] Gönderme hatası: ' + str(e))

        def worker():
            answer = ai_answer(m)
            self.root.after(0, lambda: self._log('🤖 J.A.R.V.I.S.: ' + answer))
        threading.Thread(target=worker, daemon=True).start()

    def load_token(self):
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return f.read().strip()
        except Exception:
            pass
        return ''

    def save_token(self, token):
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                f.write(token)
        except Exception as e:
            self._log('[TOKEN] Kaydetme hatası: ' + str(e))

    def set_status(self, text, color=None):

        def ui():
            try:
                self.status_label.config(text=text, fg=color or self.green)
                up = text.upper()
                if 'BAĞLANDI' in up:
                    self.telegram_state.config(text='TELEGRAM: BAĞLI', fg=self.green, bg='#092218')
                    self.online_label.config(text='● ONLINE', fg=self.green)
                    self.connect_btn.config(state='disabled')
                    self.disconnect_btn.config(state='normal')
                elif 'HATA' in up:
                    self.telegram_state.config(text='TELEGRAM: HATA', fg=self.red, bg='#2a0d14')
                    self.connect_btn.config(state='normal')
                    self.disconnect_btn.config(state='disabled')
                elif 'DURDUR' in up or 'AYRI' in up:
                    self.telegram_state.config(text='TELEGRAM: AYRIK', fg=self.orange, bg='#2a1d0a')
                    self.connect_btn.config(state='normal')
                    self.disconnect_btn.config(state='disabled')
                elif 'BAĞLANILIYOR' in up or 'HAZIRLANIYOR' in up or 'YENİDEN' in up:
                    self.telegram_state.config(text='TELEGRAM: BAĞLANIYOR', fg=self.orange, bg='#2a1d0a')
                    self.connect_btn.config(state='disabled')
                    self.disconnect_btn.config(state='normal')
                self._log('[SYSTEM] ' + text)
            except Exception:
                pass
        self.root.after(0, ui)

    def start_bot(self):
        global bot_thread, stop_requested, bot_running
        token = self.token_var.get().strip()
        if not token:
            self.settings_dialog()
            return
        if bot_running or self.connecting:
            self.set_status('Telegram zaten bağlı/bağlanıyor.', self.orange)
            return
        self.save_token(token)
        stop_requested = False
        self.connecting = True
        self.set_status("🟡 Telegram'a bağlanılıyor...", self.orange)
        self.connect_btn.config(state='disabled')
        self.disconnect_btn.config(state='normal')
        bot_thread = threading.Thread(target=telegram_worker, args=(token, self.set_status), daemon=True)
        bot_thread.start()
        self.root.after(500, self._watch_bot_thread)

    def _watch_bot_thread(self):
        global bot_running
        self.connecting = bool(bot_thread and bot_thread.is_alive() and (not bot_running))
        if bot_running:
            self.connecting = False
            self.connect_btn.config(state='disabled')
            self.disconnect_btn.config(state='normal')
        elif bot_thread and bot_thread.is_alive():
            self.root.after(500, self._watch_bot_thread)
        else:
            self.connecting = False
            self.connect_btn.config(state='normal')
            self.disconnect_btn.config(state='disabled')

    def stop_bot(self):
        global stop_requested, bot_running, gui_token
        stop_requested = True
        gui_token = None
        self.connecting = False
        self.connect_btn.config(state='normal')
        self.disconnect_btn.config(state='disabled')
        self.set_status('⚪ Telegram bağlantısı kesiliyor...', self.orange)

    def close(self):
        global stop_requested, gui_token
        stop_requested = True
        gui_token = None
        try:
            self.stop_real_camera()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass
def require_gemini_api_key():
    """JARVIS açılırken OpenAI API anahtarını zorunlu olarak ister."""
    global OPENAI_API_KEY_RUNTIME

    result = {"key": ""}

    win = tk.Tk()
    win.title("J.A.R.V.I.S. • ChatGPT / OpenAI API Key")
    win.geometry("620x250")
    win.resizable(False, False)
    win.configure(bg="#02070b")
    win.attributes("-topmost", True)

    tk.Label(
        win, text="J.A.R.V.I.S.",
        font=("Segoe UI", 22, "bold"),
        fg="#00d9ff", bg="#02070b"
    ).pack(pady=(22, 2))

    tk.Label(
        win, text="OPENAI API KEY GEREKLİ",
        font=("Consolas", 11, "bold"),
        fg="#00ff88", bg="#02070b"
    ).pack()

    tk.Label(
        win,
        text="Devam etmek için OpenAI API anahtarını girin.\nAnahtar girilmeden JARVIS başlatılmaz.",
        font=("Segoe UI", 9),
        fg="#c8d6df", bg="#02070b",
        justify="center"
    ).pack(pady=(10, 12))

    frame = tk.Frame(win, bg="#06131a", highlightbackground="#0a566b", highlightthickness=1)
    frame.pack(fill="x", padx=35, pady=4)

    var = tk.StringVar()
    entry = tk.Entry(
        frame, textvariable=var, show="•",
        font=("Consolas", 10),
        fg="white", bg="#0a2029",
        insertbackground="white", relief="flat"
    )
    entry.pack(side="left", fill="x", expand=True, padx=8, pady=8, ipady=5)

    show_var = tk.BooleanVar(value=False)
    tk.Checkbutton(
        frame, text="Göster", variable=show_var,
        command=lambda: entry.config(show="" if show_var.get() else "•"),
        font=("Segoe UI", 8), fg="#c8d6df", bg="#06131a",
        activebackground="#06131a", activeforeground="white",
        selectcolor="#0b202b"
    ).pack(side="right", padx=6)

    def paste():
        try:
            var.set(win.clipboard_get().strip())
            entry.focus_set()
        except tk.TclError:
            messagebox.showwarning("Yapıştır", "Panoda yapıştırılacak bir metin bulunamadı.", parent=win)

    def continue_app():
        key = var.get().strip()
        if not key:
            messagebox.showerror(
                "ChatGPT / OpenAI API Key Eksik",
                "API anahtarını girmeden JARVIS çalıştırılamaz.",
                parent=win
            )
            entry.focus_set()
            return
        if len(key) < 20:
            messagebox.showerror(
                "Geçersiz API Key",
                "Girilen anahtar çok kısa görünüyor. OpenAI API anahtarını eksiksiz gir.",
                parent=win
            )
            entry.focus_set()
            return
        result["key"] = key
        win.destroy()

    buttons = tk.Frame(win, bg="#02070b")
    buttons.pack(fill="x", padx=35, pady=14)
    tk.Button(
        buttons, text="YAPIŞTIR", command=paste,
        font=("Consolas", 9, "bold"), fg="white", bg="#24506e",
        activebackground="#306f94", relief="flat", padx=16, pady=7
    ).pack(side="left")
    tk.Button(
        buttons, text="OPENAI'Yİ BAŞLAT", command=continue_app,
        font=("Consolas", 9, "bold"), fg="white", bg="#087ea4",
        activebackground="#0aa6d4", relief="flat", padx=16, pady=7
    ).pack(side="right")

    entry.focus_set()
    win.protocol("WM_DELETE_WINDOW", lambda: win.destroy())
    win.bind("<Return>", lambda e: continue_app())
    win.mainloop()

    if not result["key"]:
        return False

    OPENAI_API_KEY_RUNTIME = result["key"]
    return True


def install_startup():
    """Windows Startup klasörüne JARVIS kısayolu ekler."""
    try:
        startup_dir=Path(os.environ['APPDATA'])/r'Microsoft\Windows\Start Menu\Programs\Startup'
        startup_dir.mkdir(parents=True,exist_ok=True)
        link=startup_dir/'JARVIS.lnk'
        ps = '$w=New-Object -ComObject WScript.Shell; $s=$w.CreateShortcut("%s"); $s.TargetPath="%s"; $s.Arguments="%s"; $s.WorkingDirectory="%s"; $s.Save()' % (link, sys.executable, str(Path(__file__).resolve()), str(Path(__file__).resolve().parent))
        subprocess.run(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-Command',ps],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10)
        return True
    except Exception as e:
        print('Startup:',e); return False

def startup_voice():
    """JARVIS açılışında mümkün olan en doğal Windows sesini kullanır."""
    try:
        ps = r"""
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.Volume = 90
$s.Rate = -1

$voices = $s.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo }

$preferred = $voices | Where-Object {
    $_.Name -match 'Natural|Online|Microsoft.*(Zira|Aria|Jenny|Guy|Ryan|Sonia|Hazel|David)'
} | Select-Object -First 1

if ($preferred) {
    $s.SelectVoice($preferred.Name)
} else {
    $tr = $voices | Where-Object {
        $_.Culture.Name -match '^tr' -or $_.Culture.Name -match 'tr-TR'
    } | Select-Object -First 1

    if ($tr) {
        $s.SelectVoice($tr.Name)
    }
}

$s.Speak("J.A.R.V.I.S. hazır. Hoş geldiniz Ege.")
"""
        subprocess.Popen(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception:
        pass

def main():
    global PSUTIL_OK, WIKIPEDIA_OK
    try:
        # Canlı sistem kartları ve bilgi cevapları için gerekli yardımcı paketler.
        if not PSUTIL_OK:
            try:
                PSUTIL_OK = install_package("psutil", "psutil")
            except Exception:
                PSUTIL_OK = False
        if not WIKIPEDIA_OK:
            try:
                WIKIPEDIA_OK = install_package("wikipedia", "wikipedia")
            except Exception:
                WIKIPEDIA_OK = False

        # OpenAI API anahtarı zorunlu: anahtar girilmeden JARVIS açılmaz.
        if not require_gemini_api_key():
            print("ChatGPT / OpenAI API Key girilmedi. JARVIS başlatılmadı.")
            return

        install_startup()
        startup_voice()
        root = tk.Tk()
        root.deiconify()
        root.lift()
        JarvisGUI(root)
        root.mainloop()
    except Exception as e:
        print("\nJ.A.R.V.I.S. başlatılamadı:")
        print(f"{type(e).__name__}: {e}")
        try:
            input("\nKapatmak için ENTER...")
        except Exception:
            pass


if __name__ == "__main__":
    main()
