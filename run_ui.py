#!/usr/bin/env python3
"""
run_ui.py - TikTok LIVE Viewer (UI, Start/Stop, robust attribute access, thread-safe UI updates)
"""
import json
import threading
import tkinter as tk
from tkinter import ttk
from datetime import datetime
from typing import Any

from TikTokLive.client.client import TikTokLiveClient
from TikTokLive.events import (
    ConnectEvent, CommentEvent, DisconnectEvent,
    GiftEvent, LikeEvent, ShareEvent, FollowEvent
)

CONFIG_FILE = "config.json"


def load_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "room_unique_id": "",
            "show_comment": True,
            "show_gift": True,
            "show_like": True,
            "show_share": True,
            "show_follow": True,
            "show_viewer_count": True
        }


def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4, ensure_ascii=False)


def now_str():
    return datetime.now().strftime("%H:%M:%S")


def safe_get(obj: Any, *names, default=None):
    """
    Try to get attribute from obj using multiple candidate names.
    Works with both attribute access (getattr) and mapping access (obj[name]) if obj is dict-like.
    """
    if obj is None:
        return default
    for name in names:
        # try attribute access
        try:
            val = getattr(obj, name)
            if val is not None:
                return val
        except Exception:
            pass
        # try dict-style access
        try:
            if isinstance(obj, dict) and name in obj:
                return obj[name]
        except Exception:
            pass
        # try lower/upper variants
        try:
            alt = name.lower()
            val = getattr(obj, alt)
            if val is not None:
                return val
        except Exception:
            pass
        try:
            alt2 = ''.join(name.split('_'))
            val = getattr(obj, alt2, None)
            if val is not None:
                return val
        except Exception:
            pass
    return default


class TikTokUI:
    def __init__(self, root):
        self.root = root
        self.root.title("TikTok LIVE Viewer - Manager")
        self.client = None
        self.running = False

        self.config = load_config()

        # ====== Style ======
        style = ttk.Style()
        style.configure("TLabel", font=("Arial", 12))
        style.configure("TEntry", font=("Arial", 12))
        style.configure("TCheckbutton", font=("Arial", 11))
        style.configure("TButton", font=("Arial", 11, "bold"))

        # ====== Room ID Entry ======
        frame_top = ttk.Frame(root, padding=10)
        frame_top.grid(row=0, column=0, columnspan=3, sticky="we")

        ttk.Label(frame_top, text="Room Unique ID:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.room_entry = ttk.Entry(frame_top, width=30)
        self.room_entry.grid(row=0, column=1, sticky="we", padx=5, pady=5)
        self.room_entry.insert(0, self.config.get("room_unique_id", ""))
        frame_top.columnconfigure(1, weight=1)

        # ====== Options ======
        self.vars = {}
        options = [
            ("Show Comments", "show_comment"),
            ("Show Gifts", "show_gift"),
            ("Show Likes", "show_like"),
            ("Show Shares", "show_share"),
            ("Show Follows", "show_follow"),
            ("Count Viewer", "show_viewer_count")
        ]

        frame_opts = ttk.LabelFrame(root, text="Options", padding=10)
        frame_opts.grid(row=1, column=0, columnspan=3, sticky="we", padx=10, pady=5)

        for i, (label, key) in enumerate(options):
            var = tk.BooleanVar(value=self.config.get(key, True))
            chk = ttk.Checkbutton(frame_opts, text=label, variable=var)
            chk.grid(row=i // 2, column=i % 2, sticky="w", padx=5, pady=2)
            self.vars[key] = var

        # ====== Buttons ======
        btn_frame = ttk.Frame(root, padding=10)
        btn_frame.grid(row=2, column=0, columnspan=3)

        self.start_btn = ttk.Button(btn_frame, text="▶ Start", command=self.start_listening)
        self.start_btn.grid(row=0, column=0, padx=5)

        self.stop_btn = ttk.Button(btn_frame, text="■ Stop", command=self.stop_listening, state="disabled")
        self.stop_btn.grid(row=0, column=1, padx=5)

        # Label trạng thái loading kết nối
        self.status_label = ttk.Label(btn_frame, text="", foreground="green", font=("Arial", 11, "italic"))
        self.status_label.grid(row=0, column=2, padx=10)

        # ====== Log Box ======
        log_frame = ttk.Frame(root)
        log_frame.grid(row=3, column=0, columnspan=3, sticky="nsew", padx=10, pady=5)

        self.log_box = tk.Text(log_frame, wrap="word", height=20, bg="black", fg="white", font=("Consolas", 10))
        self.log_box.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_box.yview)
        scrollbar.pack(side="right", fill="y")
        self.log_box.configure(yscrollcommand=scrollbar.set)

        # ====== Tag colors ======
        self.log_box.tag_configure("comment", foreground="lightgreen")
        self.log_box.tag_configure("gift", foreground="orange")
        self.log_box.tag_configure("like", foreground="pink")
        self.log_box.tag_configure("share", foreground="cyan")
        self.log_box.tag_configure("follow", foreground="yellow")
        self.log_box.tag_configure("system", foreground="gray")

        # ====== Resize rules ======
        root.columnconfigure(1, weight=1)
        root.rowconfigure(3, weight=1)


    def _append_log(self, text, tag=None):
        """Append directly to Text widget (must be called from main thread)."""
        timestamp = now_str()
        self.log_box.insert(tk.END, f"[{timestamp}] {text}\n", tag)
        self.log_box.see(tk.END)

    def log(self, text, tag=None):
        """Thread-safe log: schedule on main thread if called from another thread."""
        if threading.current_thread() is threading.main_thread():
            self._append_log(text, tag)
        else:
            # schedule on main thread ASAP
            try:
                self.root.after(0, lambda: self._append_log(text, tag))
            except Exception:
                # fallback: ignore scheduling errors
                pass

    def start_listening(self):
        if self.running:
            return

        cfg = {
            "room_unique_id": self.room_entry.get().strip().lstrip("@"),
            **{k: v.get() for k, v in self.vars.items()}
        }
        save_config(cfg)
        self.config = cfg

        if not cfg["room_unique_id"]:
            self.log("⚠️ Vui lòng nhập Room Unique ID!", "system")
            return

        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.status_label.config(text="⏳ Đang kết nối...")
        self.running = True

        threading.Thread(target=self.run_client, daemon=True).start()

    def stop_listening(self):
        if self.client:
            try:
                self.client.stop()
            except Exception:
                pass
        self.running = False
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.status_label.config(text="")  # Xóa trạng thái
        self.log("🛑 Đã dừng lắng nghe", "system")

    def run_client(self):
        unique_id = self.config["room_unique_id"]
        try:
            self.client = TikTokLiveClient(unique_id=unique_id)
        except Exception as e:
            self.log(f"❌ Không thể tạo client: {e}", "system")
            self.stop_listening()
            return

        # CONNECT
        @self.client.on(ConnectEvent)
        async def on_connect(evt: ConnectEvent):
            self.log(f"✅ Kết nối tới @{unique_id}", "system")
            # Khi kết nối thành công, xóa status loading
            def clear_status():
                self.status_label.config(text="")  
            self.root.after(0, clear_status)

        # COMMENT
        if self.config.get("show_comment", True):
            @self.client.on(CommentEvent)
            async def on_comment(evt: CommentEvent):
                try:
                    uid = safe_get(evt.user, "uniqueId", "unique_id", "userId", "user_id", default=None)
                    nick = safe_get(evt.user, "nickname", "nickName", "nick", default="Ẩn danh")
                    txt = safe_get(evt, "comment", "message", "text", default="")
                    name_to_show = uid if uid else nick
                    self.log(f"💬 {name_to_show} ({nick}): {txt}", "comment")
                except Exception as e:
                    # Catch & log parse errors — do not crash emitter
                    self.log(f"⚠️ Lỗi xử lý comment: {e}", "system")

        # GIFT
        if self.config.get("show_gift", True):
            @self.client.on(GiftEvent)
            async def on_gift(evt: GiftEvent):
                try:
                    nick = safe_get(evt.user, "nickname", "nickName", default="Ẩn danh")
                    gift_name = safe_get(evt.gift, "name", "giftName", "gift_name", default="Quà")
                    gift_count = safe_get(evt.gift, "repeat_count", "repeatCount", "repeatcount", default=None)
                    if gift_count is None:
                        # some payloads may put count at root or as int
                        gift_count = safe_get(evt, "repeatCount", "repeat_count", default=1) or 1
                    self.log(f"🎁 {nick} tặng {gift_count}x {gift_name}", "gift")
                except Exception as e:
                    self.log(f"⚠️ Lỗi xử lý gift: {e}", "system")

        # LIKE
        if self.config.get("show_like", True):
            @self.client.on(LikeEvent)
            async def on_like(evt: LikeEvent):
                try:
                    nick = safe_get(evt.user, "nickname", "nickName", default="Ẩn danh")
                    like_count = safe_get(evt, "likeCount", "like_count", default=None)
                    total_like = safe_get(evt, "totalLikeCount", "total_like_count", default=None)
                    like_count = like_count if like_count is not None else ""
                    total_like = total_like if total_like is not None else ""
                    self.log(f"❤️ {nick} thả {like_count}tim")
                except Exception as e:
                    self.log(f"⚠️ Lỗi xử lý like: {e}", "system")

        # SHARE
        if self.config.get("show_share", True):
            @self.client.on(ShareEvent)
            async def on_share(evt: ShareEvent):
                try:
                    nick = safe_get(evt.user, "nickname", "nickName", default="Ẩn danh")
                    self.log(f"🔗 {nick} đã chia sẻ livestream", "share")
                except Exception as e:
                    self.log(f"⚠️ Lỗi xử lý share: {e}", "system")

        # FOLLOW
        if self.config.get("show_follow", True):
            @self.client.on(FollowEvent)
            async def on_follow(evt: FollowEvent):
                try:
                    nick = safe_get(evt.user, "nickname", "nickName", default="Ẩn danh")
                    self.log(f"⭐ {nick} đã follow", "follow")
                except Exception as e:
                    self.log(f"⚠️ Lỗi xử lý follow: {e}", "system")

        # DISCONNECT
        @self.client.on(DisconnectEvent)
        async def on_disconnect(evt: DisconnectEvent):
            self.log("❌ Mất kết nối", "system")
            self.stop_listening()

        try:
            self.client.run()
        except Exception as e:
            self.log(f"❌ Client error: {e}", "system")
            self.stop_listening()


if __name__ == "__main__":
    root = tk.Tk()
    app = TikTokUI(root)
    root.mainloop()
