import imaplib, os
from dotenv import load_dotenv

load_dotenv()
IMAP_HOST = os.getenv("IMAP_HOST", "imap.gmail.com")
IMAP_USER = os.getenv("IMAP_USER")
IMAP_PASS = os.getenv("IMAP_PASS")

with imaplib.IMAP4_SSL(IMAP_HOST) as M:
    M.login(IMAP_USER, IMAP_PASS)
    typ, boxes = M.list()
    for box in boxes:
        print(box.decode())
    M.logout()
