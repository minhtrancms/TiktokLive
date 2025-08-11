#!/usr/bin/env python3
"""
run.py - Xem TikTok LIVE (comment, gift, like, share, follow) tùy chọn
"""

import json
import sys
from datetime import datetime
from TikTokLive.client.client import TikTokLiveClient
from TikTokLive.events import ConnectEvent, CommentEvent, DisconnectEvent, GiftEvent, LikeEvent, ShareEvent, FollowEvent, ViewerCountUpdateEvent

# Màu terminal
RESET = "\033[0m"
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"

# Đọc file config
CONFIG_FILE = "config.json"

try:
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
        unique_id = config.get("room_unique_id", "").strip().lstrip("@")
except FileNotFoundError:
    print(f"Không tìm thấy {CONFIG_FILE}. Hãy tạo file này với room_unique_id.")
    sys.exit(1)

if not unique_id:
    print("Vui lòng điền room_unique_id trong config.json")
    sys.exit(1)

# Khởi tạo client
client = TikTokLiveClient(unique_id=unique_id)

# Hàm lấy thời gian
def now_str():
    return datetime.now().strftime("%H:%M:%S")

# Kết nối
@client.on(ConnectEvent)
async def on_connect(event: ConnectEvent):
    print(f"{GREEN}✅ [{now_str()}] Đã kết nối tới TikTok LIVE của @{unique_id}{RESET}")

# Viewer count (số người đang xem)
if config.get("show_viewer_count", True):
    @client.on(ViewerCountUpdateEvent)
    async def on_viewer_count(event: ViewerCountUpdateEvent):
        print(f"{YELLOW}[{now_str()}]{RESET} 👀 Đang có {GREEN}{event.viewerCount}{RESET} người xem")

seen_users = set()

if config.get("show_comment", True):
    @client.on(CommentEvent)
    async def on_comment(event: CommentEvent):
        user = getattr(event.user, "uniqueId", "unknown")
        nick = getattr(event.user, "nickname", "")
        if user not in seen_users:
            seen_users.add(user)
            print(f"{GREEN}[{now_str()}] 🆕 Người mới: {nick} (@{user}){RESET}")
        txt = getattr(event, "comment", "")
        print(f"{YELLOW}[{now_str()}]{RESET} 💬 {BLUE}{user}{RESET} ({CYAN}{nick}{RESET}): {txt}")


# Gift
if config.get("show_gift", True):
    @client.on(GiftEvent)
    async def on_gift(event: GiftEvent):
        nick = getattr(event.user, "nickname", "Ẩn danh")
        gift_name = getattr(event.gift, "name", "Quà")
        gift_count = event.gift.repeat_count if event.gift.repeat_count > 1 else 1
        print(f"{YELLOW}[{now_str()}]{RESET} 🎁 {BLUE}{nick}{RESET} tặng {GREEN}{gift_count}x {gift_name}{RESET}")

# Like
if config.get("show_like", True):
    @client.on(LikeEvent)
    async def on_like(event: LikeEvent):
        nick = getattr(event.user, "nickname", "Ẩn danh")
        print(f"{YELLOW}[{now_str()}]{RESET} ❤️ {BLUE}{nick}{RESET} đã thả {GREEN}{event.likeCount}{RESET} tim (Tổng: {event.totalLikeCount})")

# Share
if config.get("show_share", True):
    @client.on(ShareEvent)
    async def on_share(event: ShareEvent):
        nick = getattr(event.user, "nickname", "Ẩn danh")
        print(f"{YELLOW}[{now_str()}]{RESET} 🔗 {BLUE}{nick}{RESET} vừa chia sẻ live")

# Follow
if config.get("show_follow", True):
    @client.on(FollowEvent)
    async def on_follow(event: FollowEvent):
        nick = getattr(event.user, "nickname", "Ẩn danh")
        print(f"{YELLOW}[{now_str()}]{RESET} ⭐ {BLUE}{nick}{RESET} vừa follow")

# Ngắt kết nối
@client.on(DisconnectEvent)
async def on_disconnect(event: DisconnectEvent):
    print(f"{MAGENTA}❌ [{now_str()}] Mất kết nối{RESET}")

if __name__ == "__main__":
    try:
        print(f"▶ Bắt đầu lắng nghe LIVE của @{unique_id} ...")
        client.run()
    except KeyboardInterrupt:
        print("🛑 Dừng script")
