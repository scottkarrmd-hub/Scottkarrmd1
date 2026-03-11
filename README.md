# Gmail to Google Drive Exporter

Exports saved emails and links from every Gmail label (`scottkarrmd@gmail.com`) into organised folders in Google Drive.

## What it does

For each Gmail label the script will:
- Download up to N emails (default 100, configurable)
- Save each email as a plain-text file inside `Gmail Export/<Label>/emails/`
- Extract every URL from the email bodies and write a `links_summary.txt` file inside `Gmail Export/<Label>/`

Your existing Gmail labels (Books, Travel/2025, AI, Tech, Health, Notes, Wine, etc.) each get their own Drive folder automatically.

---

## One-time setup

### 1. Install Python dependencies
```bash
pip install -r requirements.txt
```

### 2. Create Google Cloud credentials

1. Go to <https://console.cloud.google.com/>
2. Create a new project (or use an existing one)
3. Navigate to **APIs & Services → Library** and enable:
   - **Gmail API**
   - **Google Drive API**
4. Go to **APIs & Services → Credentials**
5. Click **Create Credentials → OAuth client ID**
6. Choose **Desktop app**, give it a name, click **Create**
7. Click **Download JSON** and save the file as **`credentials.json`** in this directory

### 3. Run the script
```bash
python gmail_to_drive.py
```

A browser window opens the first time – log in as `scottkarrmd@gmail.com` and grant the requested permissions.
A `token.json` file is saved so subsequent runs do not need the browser.

---

## Usage

```
python gmail_to_drive.py [options]
```

| Option | Default | Description |
|---|---|---|
| `--labels "Books,AI"` | all user labels | Comma-separated label names to export |
| `--max-per-label 500` | `100` | Max emails per label |
| `--no-skip-system` | off | Also export INBOX, SENT, SPAM, etc. |
| `--drive-root "My Archive"` | `Gmail Export` | Root folder name in Google Drive |

### Examples

```bash
# Export everything (all user labels, 100 emails each)
python gmail_to_drive.py

# Export only Books and AI labels
python gmail_to_drive.py --labels "Books,AI"

# Export up to 500 emails per label
python gmail_to_drive.py --max-per-label 500

# Include system labels too
python gmail_to_drive.py --no-skip-system

# Custom Drive folder name
python gmail_to_drive.py --drive-root "My Gmail Archive"
```

---

## Output structure in Google Drive

```
Gmail Export/
├── AI/
│   ├── emails/
│   │   ├── Subject_line_msgid123.txt
│   │   └── ...
│   └── links_summary.txt
├── Books/
│   ├── emails/
│   └── links_summary.txt
├── Travel/
│   └── 2025/              ← nested labels become nested folders
│       ├── emails/
│       └── links_summary.txt
└── ...
```

---

## Security notes

- `credentials.json` and `token.json` are in `.gitignore` and will **never** be committed.
- The script requests read-only access to Gmail and write-only (`drive.file`) access to Drive.
- No email data is stored locally – everything is streamed directly to Drive.
