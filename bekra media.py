import customtkinter as ctk
import threading
import os
import sys
import subprocess
from tkinter import filedialog, messagebox
import time
import shutil

# --- AYARLAR ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

# IPC Socket Yolu (MPV'yi kontrol etmek için) - İSİM GÜNCELLENDİ
IPC_PIPE = r'\\.\pipe\saydut_mpv_socket'

# --- GLOBAL DEĞİŞKENLER ---
YT_DLP_AVAILABLE = True
MPV_AVAILABLE = False

# yt-dlp kontrolü
try:
    import yt_dlp
except ImportError:
    yt_dlp = None
    YT_DLP_AVAILABLE = False

# MPV kontrolü
if shutil.which("mpv"):
    MPV_AVAILABLE = True

class SaydutMediaHub(ctk.CTk):
    def __init__(self):
        super().__init__()

        # PENCERE BAŞLIĞI GÜNCELLENDİ
        self.title("Saydut Media Hub v3.1 - Final Stable")
        self.geometry("1000x700")
        self.resizable(False, False)

        # Oynatma işlemi için process tutucu
        self.current_process = None

        # Başlangıç Kontrolleri
        self.after(100, self.check_dependencies)

        # Tabview
        self.tabview = ctk.CTkTabview(self, width=960, height=660)
        self.tabview.pack(padx=20, pady=20)

        self.tab_youtube = self.tabview.add("YouTube Stüdyo")
        self.tab_radio = self.tabview.add("Canlı Radyo")
        self.tab_player = self.tabview.add("Medya Oynatıcı")

        # Arayüzü oluştur
        self.setup_youtube_studio()
        self.setup_radio()
        self.setup_player()

    # ========================================================
    # BAĞIMLILIK KONTROLLERİ
    # ========================================================
    def check_dependencies(self):
        # 1. yt-dlp Kontrolü
        if not YT_DLP_AVAILABLE:
            if messagebox.askyesno("Eksik Kütüphane", "YouTube arama özelliği için 'yt-dlp' gerekli. Kurulsun mu?"):
                self.install_pip_lib("yt-dlp")
            return

        # 2. MPV Player Kontrolü
        if not MPV_AVAILABLE:
            msg = (
                "Sisteminizde 'MPV Player' bulunamadı veya algılanamadı.\n\n"
                "Bu program videoları oynatmak için MPV kullanır.\n"
                "Otomatik olarak indirilip kurulsun mu?"
            )
            if messagebox.askyesno("MPV Eksik", msg):
                self.install_mpv()
            else:
                messagebox.showwarning("Uyarı", "MPV olmadan oynatma yapılamaz.")

    def install_pip_lib(self, lib_name):
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", lib_name])
            messagebox.showinfo("Başarılı", f"{lib_name} kuruldu! Program yeniden başlatılıyor.")
            os.execl(sys.executable, sys.executable, *sys.argv)
        except Exception as e:
            messagebox.showerror("Hata", f"Kurulum başarısız: {e}")

    def install_mpv(self):
        try:
            messagebox.showinfo("Kurulum", "MPV kurulumu için komut penceresi açılacak.\nLütfen bitene kadar bekleyin.")
            # Winget ile MPV kurulumu
            cmd = 'start /wait cmd /c "winget install -e --id io.mpv.mpv --source winget && echo. && echo KURULUM TAMAMLANDI! && echo Pencereyi kapatabilirsiniz... && pause"'
            os.system(cmd)
            messagebox.showinfo("Yeniden Başlat", 
                              "MPV kuruldu! Lütfen programı kapatıp tekrar açın.\n"
                              "Eğer hala hata alırsanız bilgisayarı yeniden başlatın.")
            self.destroy()
        except Exception as e:
            messagebox.showerror("Hata", f"Kurulum hatası: {e}")

    # ========================================================
    # MPV OYNATMA MOTORU (IPC DESTEKLİ)
    # ========================================================
    def play_media(self, url_or_file, is_video=True, title="Medya"):
        """Verilen URL veya dosyayı MPV ile oynatır."""
        
        # Önceki oynatmayı durdur
        self.stop_media()

        # Komut Hazırlığı
        # --input-ipc-server: Programın MPV ile konuşmasını sağlar (Durdur/Duraklat için)
        # --ytdl-raw-options: Youtube Web Client sorununu çözer
        cmd = [
            "mpv", 
            url_or_file,
            f"--input-ipc-server={IPC_PIPE}",
            "--ytdl-raw-options=extractor-args=youtube:player_client=android"
        ]
        
        if not is_video:
            # Radyo/Ses: Pencere yok, sadece ses
            cmd.append("--no-video")
            cmd.append("--force-window=no")
        else:
            # Video: Pencere aç, başlık ayarla
            cmd.append("--force-window=immediate")
            cmd.append(f"--title={title}")
            # Youtube için video oynatıyorsak en iyi kaliteyi zorla
            if "youtube.com" in url_or_file or "youtu.be" in url_or_file:
                cmd.append("--ytdl-format=bestvideo+bestaudio/best")
        
        try:
            # subprocess başlat
            if os.name == 'nt':
                self.current_process = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                self.current_process = subprocess.Popen(cmd)
            return True
        except Exception as e:
            messagebox.showerror("Oynatma Hatası", f"MPV başlatılamadı:\n{e}\n\nMPV'nin kurulu olduğundan emin olun.")
            return False

    def send_ipc_command(self, command):
        """Çalan MPV örneğine komut gönderir."""
        if not self.current_process: return
        try:
            # Windows Named Pipe üzerinden komut gönder
            with open(IPC_PIPE, 'w') as f:
                f.write(command + '\n')
        except:
            pass # Pipe açık değilse veya MPV kapandıysa hata verme

    def toggle_pause(self):
        """Oynatmayı duraklatır/devam ettirir."""
        self.send_ipc_command("cycle pause")

    def stop_media(self):
        """Çalan medyayı tamamen kapatır."""
        # Önce nazikçe kapatmayı dene
        self.send_ipc_command("quit")
        
        if self.current_process:
            try:
                self.current_process.terminate()
                # Biraz bekle, kapanmazsa zorla kapat
                try:
                    self.current_process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    self.current_process.kill()
            except:
                pass
            self.current_process = None

    # ========================================================
    # MODÜL 1: YOUTUBE STÜDYO
    # ========================================================
    def setup_youtube_studio(self):
        frame = self.tab_youtube
        
        # Arama
        search_frame = ctk.CTkFrame(frame, fg_color="transparent")
        search_frame.pack(pady=10, fill="x", padx=20)
        
        self.yt_search_entry = ctk.CTkEntry(search_frame, placeholder_text="YouTube'da Ara veya Link Yapıştır...", height=40, font=("Roboto", 14))
        self.yt_search_entry.bind('<Return>', lambda event: self.search_youtube_thread())
        self.yt_search_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        btn_search = ctk.CTkButton(search_frame, text="ARA 🔍", width=100, height=40, command=self.search_youtube_thread, font=("Roboto Bold", 12))
        btn_search.pack(side="right")

        # İçerik
        content_frame = ctk.CTkFrame(frame, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.results_scroll = ctk.CTkScrollableFrame(content_frame, width=500, label_text="Arama Sonuçları")
        self.results_scroll.pack(side="left", fill="both", expand=True, padx=(0, 10))

        self.action_frame = ctk.CTkFrame(content_frame, width=300)
        self.action_frame.pack(side="right", fill="y", padx=(10, 0))

        ctk.CTkLabel(self.action_frame, text="Oynatıcı", font=("Roboto Medium", 18)).pack(pady=20)
        self.lbl_selected_video = ctk.CTkLabel(self.action_frame, text="Bir video seçin...", wraplength=280, text_color="gray")
        self.lbl_selected_video.pack(pady=10, padx=10)

        # Butonlar
        self.btn_play_video = ctk.CTkButton(self.action_frame, text="▶ Video Oynat", state="disabled", fg_color="green", height=40, command=lambda: self.process_youtube_action("video"))
        self.btn_play_video.pack(pady=10, padx=20, fill="x")

        self.btn_play_audio = ctk.CTkButton(self.action_frame, text="🎵 Sadece Ses Dinle", state="disabled", fg_color="#1f538d", height=40, command=lambda: self.process_youtube_action("audio"))
        self.btn_play_audio.pack(pady=10, padx=20, fill="x")

        ctk.CTkLabel(self.action_frame, text="-------------").pack(pady=10)
        
        self.btn_yt_pause = ctk.CTkButton(self.action_frame, text="⏸ Duraklat / Devam", state="disabled", fg_color="orange", command=self.toggle_pause)
        self.btn_yt_pause.pack(pady=5, padx=20, fill="x")

        self.btn_yt_stop = ctk.CTkButton(self.action_frame, text="⏹ DURDUR", state="disabled", fg_color="red", command=self.stop_media_ui)
        self.btn_yt_stop.pack(pady=5, padx=20, fill="x")

        self.yt_status = ctk.CTkLabel(frame, text="Hazır", text_color="gray")
        self.yt_status.pack(pady=5)

        self.current_video_data = None

    def search_youtube_thread(self):
        term = self.yt_search_entry.get()
        if not term: return
        self.yt_status.configure(text="Aranıyor...", text_color="white")
        for widget in self.results_scroll.winfo_children(): widget.destroy()
        threading.Thread(target=self.search_logic, args=(term,), daemon=True).start()

    def search_logic(self, term):
        if not YT_DLP_AVAILABLE: return
        try:
            # Arama Ayarları (Android Client)
            base_opts = {
                'quiet': True,
                'extract_flat': 'in_playlist',
                'ignoreerrors': True,
                'extractor_args': {'youtube': {'player_client': ['android', 'ios']}}
            }
            
            if "youtube.com" in term or "youtu.be" in term:
                with yt_dlp.YoutubeDL(base_opts) as ydl:
                    info = ydl.extract_info(term, download=False)
                    results = [info]
            else:
                with yt_dlp.YoutubeDL(base_opts) as ydl:
                    # ytsearch15: öneki ile arama
                    info = ydl.extract_info(f"ytsearch15:{term}", download=False)
                    results = list(info['entries']) if 'entries' in info else []
            
            self.after(0, lambda: self.display_results(results))
        except Exception as e:
            self.yt_status.configure(text=f"Hata: {str(e)[:50]}...", text_color="red")

    def display_results(self, results):
        self.yt_status.configure(text=f"{len(results)} sonuç bulundu.", text_color="green")
        if not results: self.yt_status.configure(text="Sonuç yok.", text_color="yellow")
        
        for vid in results:
            title = vid.get('title', 'Başlık Yok')
            dur = vid.get('duration')
            dur_str = f"{int(dur)//60}:{int(dur)%60:02d}" if dur else "??:??"
            
            btn = ctk.CTkButton(self.results_scroll, text=f"{dur_str} | {title[:45]}...", 
                                height=40, anchor="w", fg_color="transparent", border_width=1, border_color="gray", 
                                command=lambda v=vid: self.select_video(v))
            btn.pack(fill="x", pady=2, padx=2)

    def select_video(self, video_data):
        self.current_video_data = video_data
        self.lbl_selected_video.configure(text=video_data.get('title', 'Video'), text_color="white")
        self.btn_play_video.configure(state="normal")
        self.btn_play_audio.configure(state="normal")
        self.btn_yt_stop.configure(state="normal")
        self.btn_yt_pause.configure(state="normal")

    def process_youtube_action(self, mode):
        if not self.current_video_data: return
        
        # ID varsa linki oluştur, yoksa url'i al
        if 'id' in self.current_video_data:
            url = f"https://www.youtube.com/watch?v={self.current_video_data['id']}"
        else:
            url = self.current_video_data.get('url')
            
        title = self.current_video_data.get('title', 'YouTube Video')
        is_video = (mode == "video")
        
        self.yt_status.configure(text=f"Oynatılıyor: {title}", text_color="green")
        
        # Linki direkt MPV'ye gönderiyoruz (Çözümlemeyi MPV yapar)
        self.play_media(url, is_video, title)

    def stop_media_ui(self):
        self.stop_media()
        self.yt_status.configure(text="Durduruldu.", text_color="yellow")

    # ========================================================
    # MODÜL 2: CANLI RADYO
    # ========================================================
    def setup_radio(self):
        frame = self.tab_radio
        ctk.CTkLabel(frame, text="Canlı Radyo İstasyonları", font=("Roboto Medium", 24)).pack(pady=20)
        
        self.radios = {
            "KRAL Pop": "http://46.20.3.201:80/;", 
            "Power Türk": "https://live.powerapp.com.tr/powerturk/abr/playlist.m3u8",
            "Alem FM": "https://turkmedya.radyotvonline.com/turkmedya/alemfm.stream/playlist.m3u8", 
            "Joy FM": "http://provisioning.streamtheworld.com/pls/JOY_FMAAC.pls",
            "Power FM": "http://icast.powergroup.com.tr/PowerTurk/mpeg/128/home", 
            "Slow Türk": "https://radyo.duhnet.tv/slowturk",
            "Pal FM": "http://shoutcast.radyogrup.com:1030/;", 
            "Powerturk (Yedek)": "http://mpegpowerturk.listenpowerapp.com/powerturk/mpeg/icecast.audio"
        }
        
        self.radio_var = ctk.StringVar(value="Bir İstasyon Seçin")
        ctk.CTkComboBox(frame, values=list(self.radios.keys()), variable=self.radio_var, width=300).pack(pady=10)
        
        btn_f = ctk.CTkFrame(frame, fg_color="transparent"); btn_f.pack(pady=20)
        ctk.CTkButton(btn_f, text="▶ OYNAT", width=120, height=40, command=self.play_radio_station, fg_color="green").pack(side="left", padx=10)
        ctk.CTkButton(btn_f, text="⏸ DURAKLAT", width=120, height=40, command=self.toggle_pause, fg_color="orange").pack(side="left", padx=10)
        ctk.CTkButton(btn_f, text="⏹ DURDUR", width=120, height=40, command=self.stop_media, fg_color="red").pack(side="left", padx=10)
        
        self.lbl_radio_status = ctk.CTkLabel(frame, text="Radyo Bekleniyor...", font=("Roboto", 14)); self.lbl_radio_status.pack(pady=20)

    def play_radio_station(self):
        name = self.radio_var.get()
        url = self.radios.get(name)
        if url:
            self.lbl_radio_status.configure(text=f"Bağlanıyor: {name}...", text_color="orange")
            if self.play_media(url, is_video=False):
                self.lbl_radio_status.configure(text=f"Çalıyor: {name} 🎵", text_color="#4CAF50")

    # ========================================================
    # MODÜL 3: YEREL OYNATICI
    # ========================================================
    def setup_player(self):
        frame = self.tab_player
        ctk.CTkLabel(frame, text="Yerel Medya Oynatıcı", font=("Roboto Medium", 24)).pack(pady=20)
        
        ctk.CTkButton(frame, text="Dosya Seç (Video/Ses)", command=self.open_local_file, width=250, height=50, font=("Roboto", 14)).pack(pady=20)
        self.lbl_local_file = ctk.CTkLabel(frame, text="Dosya seçilmedi", text_color="gray"); self.lbl_local_file.pack(pady=10)
        
        btn_f = ctk.CTkFrame(frame, fg_color="transparent"); btn_f.pack(pady=20)
        ctk.CTkButton(btn_f, text="▶ Oynat", width=100, command=self.resume_local_play, fg_color="green").pack(side="left", padx=5)
        ctk.CTkButton(btn_f, text="⏸ Duraklat", width=100, command=self.toggle_pause, fg_color="orange").pack(side="left", padx=5)
        ctk.CTkButton(btn_f, text="⏹ Durdur", width=100, command=self.stop_media, fg_color="red").pack(side="left", padx=5)

    def open_local_file(self):
        fp = filedialog.askopenfilename(filetypes=[("Medya", "*.mp4 *.mkv *.avi *.mp3 *.wav *.flac")])
        if fp:
            filename = os.path.basename(fp)
            is_vid = filename.lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.webm'))
            self.lbl_local_file.configure(text=f"Oynatılıyor: {filename}", text_color="green")
            self.play_media(fp, is_video=is_vid, title=filename)
    
    def resume_local_play(self):
        self.send_ipc_command("play") # Varsa devam ettir

if __name__ == "__main__":
    app = SaydutMediaHub()
    app.mainloop()