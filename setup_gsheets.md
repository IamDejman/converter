# Google Sheets Setup Guide

Follow these steps once to enable Google Sheets export.

## 1. Create a Google Cloud Project

1. Go to https://console.cloud.google.com/
2. Create a new project (or select an existing one).

## 2. Enable the Google Sheets API

1. In the left sidebar → **APIs & Services** → **Library**
2. Search for **Google Sheets API** → click **Enable**

## 3. Create OAuth2 Credentials

1. **APIs & Services** → **Credentials** → **+ Create Credentials** → **OAuth client ID**
2. Application type: **Desktop app**
3. Click **Create**, then **Download JSON**
4. Save the file as `credentials.json` in this project directory.

## 4. Run the converter

```bash
python main.py sample.json \
  --gsheets \
  --credentials credentials.json \
  --title "My Converted Sheet"
```

The first run will open a browser window asking you to sign in with your Google account.
A `token.pickle` file will be saved next to `credentials.json` so you won't need to log in again.

## Re-using an existing spreadsheet

```bash
python main.py sample.json \
  --gsheets \
  --credentials credentials.json \
  --spreadsheet-id YOUR_SPREADSHEET_ID
```

The spreadsheet ID is the long string in the URL:
`https://docs.google.com/spreadsheets/d/**SPREADSHEET_ID**/edit`
