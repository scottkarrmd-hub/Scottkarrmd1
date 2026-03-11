"""
Gmail to Google Drive Exporter
================================
Fetches emails from every Gmail label (scottkarrmd@gmail.com),
extracts links, and saves everything into organised Google Drive folders.

Folder layout created in Drive:
  Gmail Export/
    <Label Name>/
      emails/
        <subject>_<msg_id>.txt   <- plain-text email dump
      links_summary.txt           <- all URLs found in that label's emails

Requirements:
  pip install -r requirements.txt

First-run setup:
  1. Go to https://console.cloud.google.com/
  2. Create a project, enable "Gmail API" and "Google Drive API"
  3. Create OAuth 2.0 Desktop credentials, download as credentials.json
  4. Place credentials.json in the same directory as this script
  5. Run: python gmail_to_drive.py
  6. A browser window will open – log in as scottkarrmd@gmail.com and grant access
  7. token.json is saved for future runs (no browser needed)

Options:
  --labels          Comma-separated list of label names to export (default: all user labels)
  --max-per-label   Max emails per label (default: 100)
  --skip-system     Skip system labels like INBOX, SENT, SPAM (default: True)
  --drive-root      Name of the root folder in Drive (default: "Gmail Export")
"""

import argparse
import base64
import json
import os
import re
import sys
import textwrap
from datetime import datetime
from email import message_from_bytes
from pathlib import Path

# ---------------------------------------------------------------------------
# Google API helpers
# ---------------------------------------------------------------------------

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/drive.file",
]

CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"


def get_google_service():
    """Authenticate once, cache token; return (gmail_service, drive_service)."""
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        print(
            "Missing dependencies. Run:  pip install -r requirements.txt",
            file=sys.stderr,
        )
        sys.exit(1)

    creds = None

    if Path(TOKEN_FILE).exists():
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not Path(CREDENTIALS_FILE).exists():
                print(
                    f"ERROR: {CREDENTIALS_FILE} not found.\n"
                    "Download OAuth 2.0 Desktop credentials from "
                    "https://console.cloud.google.com/ and save as credentials.json",
                    file=sys.stderr,
                )
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    gmail = build("gmail", "v1", credentials=creds)
    drive = build("drive", "v3", credentials=creds)
    return gmail, drive


# ---------------------------------------------------------------------------
# Gmail helpers
# ---------------------------------------------------------------------------

def list_labels(gmail_service, skip_system=True):
    """Return list of label dicts. Filter system labels if requested."""
    result = gmail_service.users().labels().list(userId="me").execute()
    labels = result.get("labels", [])
    if skip_system:
        labels = [l for l in labels if l.get("type") == "user"]
    return labels


def list_messages_for_label(gmail_service, label_id, max_results=100):
    """Return up to max_results message stubs for a label."""
    messages = []
    page_token = None
    while len(messages) < max_results:
        batch = max_results - len(messages)
        kwargs = dict(userId="me", labelIds=[label_id], maxResults=min(batch, 500))
        if page_token:
            kwargs["pageToken"] = page_token
        response = gmail_service.users().messages().list(**kwargs).execute()
        messages.extend(response.get("messages", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return messages[:max_results]


def fetch_message(gmail_service, msg_id):
    """Fetch a full message by ID."""
    return (
        gmail_service.users()
        .messages()
        .get(userId="me", id=msg_id, format="raw")
        .execute()
    )


def decode_raw_message(raw_msg):
    """Decode base64url-encoded raw message into an email.message.Message."""
    raw_bytes = base64.urlsafe_b64decode(raw_msg["raw"] + "==")
    return message_from_bytes(raw_bytes)


def get_header(msg, name):
    """Return a header value or empty string."""
    return msg.get(name, "")


def extract_text_body(msg):
    """Extract plain-text body from a (possibly multipart) email."""
    body_parts = []
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == "text/plain" and not part.get("Content-Disposition"):
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    body_parts.append(payload.decode(charset, errors="replace"))
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            body_parts.append(payload.decode(charset, errors="replace"))
    return "\n".join(body_parts)


def extract_links(text):
    """Return a sorted-unique list of URLs found in text."""
    url_pattern = re.compile(
        r"https?://[^\s\]\[\"'<>{}|\\^`\x00-\x1f]+"
    )
    urls = url_pattern.findall(text)
    # Strip trailing punctuation that is likely not part of the URL
    cleaned = [re.sub(r"[.,;:)\]>\"']+$", "", u) for u in urls]
    return sorted(set(cleaned))


def format_email_as_text(msg, body, links):
    """Produce a human-readable text dump of an email."""
    lines = [
        "=" * 72,
        f"From   : {get_header(msg, 'From')}",
        f"To     : {get_header(msg, 'To')}",
        f"Date   : {get_header(msg, 'Date')}",
        f"Subject: {get_header(msg, 'Subject')}",
        "=" * 72,
        "",
        body.strip(),
        "",
    ]
    if links:
        lines += ["", "--- Links found in this email ---"]
        lines += [f"  {u}" for u in links]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Google Drive helpers
# ---------------------------------------------------------------------------

def find_or_create_folder(drive_service, name, parent_id=None):
    """Return the Drive folder ID for `name` under `parent_id`, creating if needed."""
    query = f"mimeType='application/vnd.google-apps.folder' and name='{name}' and trashed=false"
    if parent_id:
        query += f" and '{parent_id}' in parents"

    results = drive_service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])
    if files:
        return files[0]["id"]

    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if parent_id:
        metadata["parents"] = [parent_id]

    folder = drive_service.files().create(body=metadata, fields="id").execute()
    return folder["id"]


def upload_text_file(drive_service, filename, content, parent_id):
    """Upload a plain-text file to Drive, overwriting if it already exists."""
    from googleapiclient.http import MediaInMemoryUpload

    # Check for existing file with same name in folder
    query = (
        f"name='{filename}' and '{parent_id}' in parents and trashed=false"
    )
    results = drive_service.files().list(q=query, fields="files(id)").execute()
    existing = results.get("files", [])

    media = MediaInMemoryUpload(
        content.encode("utf-8"), mimetype="text/plain", resumable=False
    )

    if existing:
        drive_service.files().update(
            fileId=existing[0]["id"], media_body=media
        ).execute()
    else:
        metadata = {"name": filename, "parents": [parent_id]}
        drive_service.files().create(
            body=metadata, media_body=media, fields="id"
        ).execute()


# ---------------------------------------------------------------------------
# Safe filename helper
# ---------------------------------------------------------------------------

def safe_filename(text, max_len=60):
    """Convert arbitrary text to a filesystem/Drive-safe filename."""
    text = re.sub(r"[^\w\s\-]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s+", "_", text.strip())
    return text[:max_len] if text else "no_subject"


# ---------------------------------------------------------------------------
# Main export logic
# ---------------------------------------------------------------------------

def export_label(gmail_service, drive_service, label, max_per_label, label_folder_id):
    """Export all emails for one label into Drive."""
    label_name = label["name"]
    label_id = label["id"]

    print(f"\n  Label: {label_name}")
    messages = list_messages_for_label(gmail_service, label_id, max_results=max_per_label)
    print(f"    Found {len(messages)} message(s)")

    if not messages:
        return

    # Sub-folders in Drive: <label_folder>/emails/
    emails_folder_id = find_or_create_folder(drive_service, "emails", label_folder_id)

    all_links = []

    for idx, stub in enumerate(messages, 1):
        msg_id = stub["id"]
        try:
            raw = fetch_message(gmail_service, msg_id)
            msg = decode_raw_message(raw)
        except Exception as exc:
            print(f"    [WARN] Could not fetch message {msg_id}: {exc}")
            continue

        body = extract_text_body(msg)
        links = extract_links(body)
        all_links.extend(links)

        subject = get_header(msg, "Subject") or "no_subject"
        filename = f"{safe_filename(subject)}_{msg_id}.txt"
        content = format_email_as_text(msg, body, links)

        try:
            upload_text_file(drive_service, filename, content, emails_folder_id)
        except Exception as exc:
            print(f"    [WARN] Could not upload {filename}: {exc}")
            continue

        if idx % 10 == 0:
            print(f"    Uploaded {idx}/{len(messages)} ...")

    # Write combined links summary
    unique_links = sorted(set(all_links))
    if unique_links:
        links_content = "\n".join(
            [
                f"Links extracted from Gmail label: {label_name}",
                f"Exported: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
                f"Total unique links: {len(unique_links)}",
                "=" * 60,
                "",
            ]
            + unique_links
        )
        upload_text_file(drive_service, "links_summary.txt", links_content, label_folder_id)
        print(f"    Saved {len(unique_links)} unique link(s) to links_summary.txt")

    print(f"    Done: {len(messages)} email(s) exported.")


def run(args):
    print("Authenticating with Google ...")
    gmail, drive = get_google_service()
    print("Authenticated successfully.\n")

    # Resolve root Drive folder
    root_id = find_or_create_folder(drive, args.drive_root)
    print(f"Drive root folder '{args.drive_root}' ready (id={root_id})")

    # Get labels to export
    all_labels = list_labels(gmail, skip_system=args.skip_system)

    if args.labels:
        wanted = {l.strip().lower() for l in args.labels.split(",")}
        labels = [l for l in all_labels if l["name"].lower() in wanted]
        if not labels:
            print(f"ERROR: No matching labels found for: {args.labels}", file=sys.stderr)
            sys.exit(1)
    else:
        labels = all_labels

    print(f"Exporting {len(labels)} label(s) (max {args.max_per_label} emails each) ...")

    for label in labels:
        label_name = label["name"]
        # Create a folder per label (handle nested names like "Travel/2025")
        folder_id = root_id
        for part in label_name.split("/"):
            folder_id = find_or_create_folder(drive, part, folder_id)

        export_label(gmail, drive, label, args.max_per_label, folder_id)

    print("\nAll done!")
    print(f"Check Google Drive -> '{args.drive_root}' for your exported emails and links.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Export Gmail label emails & links to Google Drive.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """\
            Examples:
              # Export all user labels (default, up to 100 emails each)
              python gmail_to_drive.py

              # Export only Books and AI labels
              python gmail_to_drive.py --labels "Books,AI"

              # Export up to 500 emails per label
              python gmail_to_drive.py --max-per-label 500

              # Include system labels (INBOX, SENT, etc.) too
              python gmail_to_drive.py --no-skip-system

              # Custom Drive root folder name
              python gmail_to_drive.py --drive-root "My Gmail Archive"
            """
        ),
    )
    parser.add_argument(
        "--labels",
        default="",
        help="Comma-separated label names to export. Default: all user labels.",
    )
    parser.add_argument(
        "--max-per-label",
        type=int,
        default=100,
        dest="max_per_label",
        help="Maximum number of emails to export per label (default: 100).",
    )
    parser.add_argument(
        "--skip-system",
        action="store_true",
        default=True,
        dest="skip_system",
        help="Skip system labels like INBOX, SENT, SPAM (default: True).",
    )
    parser.add_argument(
        "--no-skip-system",
        action="store_false",
        dest="skip_system",
        help="Include system labels in the export.",
    )
    parser.add_argument(
        "--drive-root",
        default="Gmail Export",
        dest="drive_root",
        help="Name of the root folder to create in Google Drive (default: 'Gmail Export').",
    )
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
