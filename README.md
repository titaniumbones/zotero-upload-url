# Zotero URL Saver

A simple macOS tool to save URLs to Zotero using your existing Firefox browser with the Zotero Connector extension.

## How It Works

1. Opens the URL in your existing Firefox (new tab)
2. Waits for you to complete any authentication (Duo push, login, etc.)
3. You press Enter when ready
4. Sends `Cmd+Shift+S` to trigger Zotero Connector
5. Zotero saves the item with full metadata and snapshot

## Prerequisites

- **macOS** (uses AppleScript)
- **Firefox** with [Zotero Connector](https://www.zotero.org/download/connectors) extension installed
- **Zotero** desktop app running
- **Python 3**

## Installation

No installation needed with `uv` - dependencies are handled automatically:

```bash
uv run zotero_saver.py "https://example.com"
```

Or install manually:

```bash
pip install requests
```

## Usage

### Interactive Mode (recommended for sites requiring login)

```bash
uv run zotero_saver.py "https://example-library.edu/article"
```

The script will:
1. Open the URL in Firefox
2. Wait for you to press Enter (giving you time to authenticate)
3. Trigger Zotero save

### Auto Mode (for public sites)

```bash
uv run zotero_saver.py --auto 10 "https://arxiv.org/abs/2301.07041"
```

Waits 10 seconds for the page to load, then saves automatically.

### Save Current Tab

```bash
uv run zotero_saver.py --no-open placeholder
```

Just triggers the Zotero save on whatever tab is currently open in Firefox.

## Options

```
positional arguments:
  url                   URL to save (or placeholder if using --no-open)

options:
  -h, --help            show this help message and exit
  --auto SECONDS, -a SECONDS
                        Auto-save after N seconds instead of waiting for Enter
  --no-open, -n         Don't open URL (assume it's already open in Firefox)
  --skip-check          Skip checking if Zotero is running
```

## Troubleshooting

### "Zotero is not running"

Start the Zotero desktop app before running this script.

### AppleScript permissions

On first run, macOS may ask for permissions to control Firefox and System Events. Grant these permissions in System Preferences > Security & Privacy > Privacy > Accessibility.

### Nothing happens when saving

Make sure the Zotero Connector extension is installed in Firefox and that Firefox is the frontmost window when the save is triggered.
