### `docs/USER_GUIDE.md`

# User Guide

## Running the App
- Create and activate a virtual environment (see README for details).
- Install dependencies: `pip install -r requirements.txt`.
- Start the desktop app:
  - Windows: `pwsh -File scripts/run_desktop.ps1`
  - macOS/Linux: `bash scripts/run_desktop.sh`

## Adding a New Entry
- Launch the app — today's date will already be in a blank row.
- Fill out:
  - Topic
  - Time Spent (minutes)
  - What you practiced
  - Challenges
  - Wins
  - Confidence (1-5)
  - Tags (comma-separated, optional)
- Progress Score will be calculated automatically.

### Validation
- Topic is required and limited to 200 characters.
- Minutes must be between 0 and 1440.
- Confidence must be between 1 and 5.
- Tags are comma-separated; up to 10 tags, each up to 32 characters.

## Viewing History
- Navigate to the **History** section to browse all past entries.
- Filter by date range and tags.

### Edit/Delete
- Use the "Select date to edit" dropdown to pick a past entry by its date.
- Modify fields and click "Save Changes" to update.
- To delete, check "Confirm delete" and click "Delete Entry".

## Insights
- **Bar chart:** Minutes studied per day.
- **Line chart:** Confidence over time.
- **Line chart:** Progress score over time.
- **Weekly table:** Weekly totals and averages.
- **Metrics:** Current streak, longest streak, and this-week minutes vs goal.

## Data Management
- Export your data as JSON.
- Automatic daily backups are stored locally.
- Automatic JSON sync: the app reads from and writes to a JSON file in your Documents folder (`Documents/Learning Progress Tracker/entries.json`).
- Override sync path with env var `LPT_JSON_PATH` to point to a custom file.

### Importing Data
- Go to the **Data** page.
- Click "Import JSON" and select your file.
- JSON format: a list of entries where each entry is an object with `date` and optional `topic, minutes, practiced, challenges, wins, confidence, tags`.
- The app validates in the background and imports automatically if valid.
- If there are issues (e.g., missing dates or invalid values), an error panel shows details and nothing is saved.

## Settings
- Set a weekly goal (in minutes) under the **Settings** page. The Insights page shows current week progress.
