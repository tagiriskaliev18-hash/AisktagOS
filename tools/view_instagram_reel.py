import re
import subprocess
import sys

def extract_reel_id(url: str) -> str | None:
    """Получить ID Reels из любой ссылки Instagram.
    Поддерживаемые форматы:
        https://www.instagram.com/reel/CKa1X2bJk2e/
        https://instagram.com/p/CKa1X2bJk2e/
    """
    m = re.search(r'/reel/([^/]+)/?|/p/([^/]+)/?', url)
    if not m:
        return None
    return m.group(1) or m.group(2)

def open_in_browser(reel_id: str):
    """Открыть Reel в браузере (Windows)."""
    target_url = f"https://www.instagram.com/reel/{reel_id}/"
    # Используем cmd /c start для совместимости с PowerShell/Command Prompt.
    subprocess.run(["cmd", "/c", "start", "", target_url], check=False)

def main():
    if len(sys.argv) != 2:
        print("Usage: view_instagram_reel.py <instagram-reel-url>")
        sys.exit(1)
    url = sys.argv[1]
    reel_id = extract_reel_id(url)
    if not reel_id:
        print("❌ Не удалось распознать Reel‑ID. Проверьте URL.")
        sys.exit(1)
    open_in_browser(reel_id)
    print(f"✅ Открываю Reel: https://www.instagram.com/reel/{reel_id}/")

if __name__ == "__main__":
    main()
