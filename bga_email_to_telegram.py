import imaplib, email, time, os, re, requests
from email.header import decode_header
from dotenv import load_dotenv

load_dotenv()

IMAP_HOST = os.getenv("IMAP_HOST", "imap.gmail.com")
IMAP_USER = os.getenv("IMAP_USER")
IMAP_PASS = os.getenv("IMAP_PASS")
IMAP_FOLDER = os.getenv("IMAP_FOLDER", "BGA-Turn")  # or label name in Gmail
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
MARK_SEEN = os.getenv("MARK_SEEN", "true").lower() == "true"

def _decode(s):
    if not s:
        return ""
    parts = decode_header(s)
    out = []
    for txt, enc in parts:
        if isinstance(txt, bytes):
            out.append(txt.decode(enc or "utf-8", errors="replace"))
        else:
            out.append(txt)
    return "".join(out)

def telegram_send(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text})
    r.raise_for_status()

def extract_game_info(subject, body):
    # Heuristics: adjust to your language/locale
    # Examples: "It's your turn in Azul" / "Your turn to play: 7 Wonders"
    game = None
    m = re.search(r"(?:turn.*in|play:\s*)(.+)", subject, re.I)
    if m:
        game = m.group(1).strip()
    # Try body fallback
    if not game:
        m = re.search(r"It's your turn(?: now)? in ([^\n\r]+)", body, re.I)
        if m:
            game = m.group(1).strip()
    return game

def main():
    print("Connecting to Gmail...")
    if not all([IMAP_USER, IMAP_PASS, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        raise SystemExit("Missing env vars. Check .env file.")

    with imaplib.IMAP4_SSL(IMAP_HOST) as M:
        M.login(IMAP_USER, IMAP_PASS)
        # Select label/folder. Gmail labels are selected with this syntax:
        typ, _ = M.select(f'"{IMAP_FOLDER}"', readonly=not MARK_SEEN)
        if typ != "OK":
            raise SystemExit(f"Could not select folder {IMAP_FOLDER}")

        # Search unseen first; fall back to recent
        typ, msgnums = M.search(None, 'UNSEEN')
        print("Search result:", msgnums)
        if typ != "OK":
            raise SystemExit("Search failed")
        ids = msgnums[0].split()

        if not ids:
            # Nothing new; exit quietly
            return

        for i in ids:
            typ, data = M.fetch(i, "(RFC822)")
            if typ != "OK":
                continue
            msg = email.message_from_bytes(data[0][1])
            subject = _decode(msg.get("Subject", ""))
            frm = _decode(msg.get("From", ""))
            # Build body text
            body_text = ""
            if msg.is_multipart():
                for part in msg.walk():
                    ctype = part.get_content_type()
                    disp = str(part.get("Content-Disposition", ""))
                    if ctype == "text/plain" and "attachment" not in disp:
                        body_text += part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="replace")
            else:
                body_text = msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8", errors="replace")

            game = extract_game_info(subject, body_text) or "a game"
            preview = subject if subject else (body_text[:120] + "...")
            text = f"🎲 BGA: It’s your turn in {game}!\n\n{preview}"
            try:
                telegram_send(text)
            except Exception as e:
                print("Telegram send failed:", e)

            if MARK_SEEN:
                M.store(i, "+FLAGS", "\\Seen")

        M.logout()

if __name__ == "__main__":
    main()
