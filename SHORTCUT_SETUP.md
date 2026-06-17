# Daily Work-Log — iOS Shortcut Setup

Everything runs on your iPhone. When you arrive at the office, a location automation fires, logs your arrival to this repo, and shows a banner: **"In since 08:32 — leave by 17:32"**.

Time target: **9 hours** from arrival.

---

## Step 1 — Create a GitHub Personal Access Token

1. Open Safari → go to **github.com/settings/personal-access-tokens/new** (sign in if needed).
2. Note name: `iPhone Work Log`
3. Expiration: No expiration (or 1 year).
4. Repository access: **Only selected repositories** → pick `cwinter1/automation`.
5. Under **Permissions → Repository → Contents** → set to **Read and Write**.
6. Tap **Generate token** and **copy it now** (you won't see it again).
7. Save it somewhere safe (Notes app, password manager).

---

## Step 2 — Build the Shortcut

Open the **Shortcuts** app → tap **+** (top right) → name it `Work Log Arrival`.

Add these actions **in order**:

### 1. Get current date
- Search for action: **Date**
- Setting: **Current Date**
- Tap the result variable → rename to `Arrival`

### 2. Format arrival time (HH:mm)
- Search for action: **Format Date**
- Date: `Arrival`
- Format: **Custom** → type `HH:mm`
- Tap result variable → rename to `ArrivalHHMM`

### 3. Format today's date (yyyy-MM-dd)
- Add another **Format Date**
- Date: `Arrival`
- Format: **Custom** → type `yyyy-MM-dd`
- Tap result variable → rename to `TodayDate`

### 4. Calculate leave time
- Search for action: **Adjust Date**
- Date: `Arrival`
- Adjust: **+9 Hours**
- Tap result variable → rename to `Departure`

### 5. Format leave time (HH:mm)
- Add another **Format Date**
- Date: `Departure`
- Format: **Custom** → type `HH:mm`
- Tap result variable → rename to `LeaveHHMM`

### 6. Build the JSON log entry
- Search for action: **Text**
- Type this exactly, inserting variables (tap them from the variable picker):
  ```
  {"date":"[TodayDate]","arrived":"[ArrivalHHMM]","leave_by":"[LeaveHHMM]"}
  ```
- Tap result variable → rename to `LogJSON`

### 7. Base64-encode the JSON
- Search for action: **Encode** (full name: "Encode / Decode")
- Input: `LogJSON`
- Encoding: **Base64 Encode**
- Line Breaks: **OFF** (important — GitHub rejects MIME-wrapped base64)
- Tap result variable → rename to `LogBase64`

### 8. Fetch the current file SHA from GitHub
- Search for action: **Get Contents of URL**
- URL: `https://api.github.com/repos/cwinter1/automation/contents/work_log/latest.json`
- Method: **GET**
- Expand **Headers** → add:
  | Key | Value |
  |-----|-------|
  | `Authorization` | `Bearer PASTE_YOUR_PAT_HERE` |
  | `Accept` | `application/vnd.github+json` |
  | `X-GitHub-Api-Version` | `2022-11-28` |
- Tap result variable → rename to `GHGetResponse`

### 9. Extract the file SHA
- Search for action: **Get Dictionary Value**
- Get: **Value** for Key: `sha`
- From: `GHGetResponse`
- Tap result variable → rename to `FileSHA`

### 10. Upload the updated log entry
- Add another **Get Contents of URL**
- URL: `https://api.github.com/repos/cwinter1/automation/contents/work_log/latest.json`
- Method: **PUT**
- Headers: same three as step 8, **plus**:
  | Key | Value |
  |-----|-------|
  | `Content-Type` | `application/json` |
- Request Body: **JSON**
- Add three JSON fields (tap "+" to add each):
  | Key | Type | Value |
  |-----|------|-------|
  | `message` | Text | `Work log [TodayDate] arrived [ArrivalHHMM]` |
  | `content` | Text | `LogBase64` (use variable picker) |
  | `sha` | Text | `FileSHA` (use variable picker) |

### 11. Show arrival notification
- Search for action: **Show Notification**
- Title: `Work Day Started`
- Body: `In since [ArrivalHHMM] — leave by [LeaveHHMM]`
- Play Sound: ON

---

## Step 3 — Set up the Location Automation

1. In Shortcuts, tap the **Automation** tab (bottom center).
2. Tap **+** → **Personal Automation**.
3. Choose **Arrive**.
4. Tap **Choose** next to Location → search for your office address → select it.
5. Adjust radius to minimum that covers the entrance.
6. Tap **Next** → tap **Add Action** → search `Work Log Arrival` → select it.
7. Tap **Next** → **turn OFF "Ask Before Running"** → tap **Done**.

---

## What happens each day

| Event | Action |
|---|---|
| You arrive at office | Shortcut fires automatically |
| GitHub API GET | Fetches current SHA of `work_log/latest.json` |
| GitHub API PUT | Overwrites the file; commit appears in history |
| Notification banner | Shows arrival time and 9-hour leave time |

Your full attendance history is preserved in the Git commit log of this repo (`work_log/latest.json`).

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Shortcut doesn't fire | Ensure Location Services → Shortcuts is set to **Always** in iPhone Settings |
| 401 Unauthorized | PAT expired or wrong — regenerate and paste into both GET and PUT header steps |
| 409 Conflict on PUT | SHA mismatch — re-run the Shortcut; the GET step fetches fresh SHA each time |
| Automation asks for confirmation | Turn off "Ask Before Running" in the automation settings |
