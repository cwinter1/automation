# Daily Work-Log — iOS 18 Shortcut Setup

When you arrive at the office, a location automation fires automatically.
Your iPhone immediately shows a banner — **"In since 08:32 — leave by 17:32"** —
then quietly logs the entry to this GitHub repo in the background.

Time target: **9 hours** from arrival.

---

## Prerequisites

| What | Where to check |
|---|---|
| iPhone running **iOS 18** | Settings → General → Software Update |
| **Shortcuts** app installed | Pre-installed on iOS 18; if missing, get it from the App Store |
| Location Services enabled for Shortcuts | Settings → Privacy & Security → Location Services → Shortcuts → **Always** |
| Background App Refresh ON | Settings → General → Background App Refresh → Shortcuts → ON |
| Low Power Mode **OFF** when commuting | Settings → Battery (Low Power Mode blocks background automation) |

---

## Step 1 — Create a GitHub Personal Access Token (PAT)

You need this so the Shortcut can write to this repo on your behalf.

1. On your iPhone, open **Safari** and go to:
   `github.com/settings/personal-access-tokens/new`
   (Sign in to GitHub if prompted.)
2. Fill in:
   - **Token name:** `iPhone Work Log`
   - **Expiration:** No expiration
3. Under **Repository access** → choose **Only selected repositories** → add `cwinter1/automation`
4. Under **Permissions → Repository permissions → Contents** → set to **Read and Write**
5. Scroll down → tap **Generate token**
6. **Copy the token immediately** (you cannot see it again after leaving the page)
7. Paste it into your **Notes app** temporarily — you will need it in Step 2

---

## Step 2 — Build the Shortcut (12 actions)

Open the **Shortcuts** app → tap the **+** button (top right of the My Shortcuts tab) → tap the name field at the top and name it **`Work Log Arrival`**.

> **How to add actions:** Tap the search bar at the bottom of the screen and type the action name. Tap it to add it.
>
> **How to rename a variable:** After an action runs, it produces a coloured result pill. Tap that pill → tap **Rename** → type the new name.
>
> **How to insert a variable into a text field:** Tap inside the field → tap the **variable icon** (looks like `{x}`) in the keyboard toolbar → pick the variable.

---

### Action 1 — Get the current date and time

- Search: **Date**
- Tap it to add — inside the action confirm it says **Current Date** (not a specific date)
- Rename the result variable: **`Arrival`**

---

### Action 2 — Format arrival time for display

- Search: **Format Date**
- **Date:** `Arrival`
- **Format:** Custom → clear the field → type exactly: `HH:mm`
- Rename the result variable: **`ArrivalHHMM`**

> `HH` = 24-hour clock. Example output: `08:32`

---

### Action 3 — Format today's date for the log file

- Search: **Format Date** (add a second one)
- **Date:** `Arrival`
- **Format:** Custom → type exactly: `yyyy-MM-dd`
- Rename the result variable: **`TodayDate`**

> Example output: `2026-06-17`

---

### Action 4 — Calculate leave time

- Search: **Adjust Date**
- **Date:** `Arrival`
- **Add:** `9` **Hours**
- Rename the result variable: **`Departure`**

---

### Action 5 — Format leave time for display

- Search: **Format Date** (add a third one)
- **Date:** `Departure`
- **Format:** Custom → type exactly: `HH:mm`
- Rename the result variable: **`LeaveHHMM`**

---

### Action 6 — Show the notification NOW (before any network call)

> This fires immediately. Even if your internet is slow or the GitHub steps below fail, you already have your banner.

- Search: **Show Notification**
- **Title:** `Work Day Started`
- **Body:** tap the `{x}` icon and insert `ArrivalHHMM`, then type ` — leave by `, then insert `LeaveHHMM`
  - Final result looks like: `In since 08:32 — leave by 17:32`
- **Play Sound:** ON

---

### Action 7 — Build the JSON log entry

- Search: **Text**
- Tap inside the text box and type the following, inserting each variable using the `{x}` picker:

```
{"date":"TodayDate","arrived":"ArrivalHHMM","leave_by":"LeaveHHMM"}
```

Replace `TodayDate`, `ArrivalHHMM`, `LeaveHHMM` with the actual variable tokens (tap `{x}` → choose each one).

- Rename the result variable: **`LogJSON`**

---

### Action 8 — Base64-encode the JSON

- Search: **Encode** (full name shown: "Encode / Decode")
- **Input:** `LogJSON`
- **Encode / Decode:** Encode
- **Format:** Base64
- Rename the result variable: **`LogBase64Raw`**

---

### Action 9 — Strip any line breaks from the base64 output

> iOS sometimes wraps base64 output with line breaks. GitHub rejects wrapped base64. This step removes them.

- Search: **Replace Text**
- **Text:** `LogBase64Raw`
- **Find:** tap the Find field → press **Return once** on the keyboard to insert a real newline (the field will look like it has one empty line)
- **Replace:** leave completely empty
- **Regular Expressions:** OFF
- **Case Sensitive:** OFF
- Rename the result variable: **`LogBase64`**

---

### Action 10 — Fetch the current SHA from GitHub

> GitHub requires the existing file's SHA to update it. This step retrieves it.

- Search: **Get Contents of URL**
- **URL:** `https://api.github.com/repos/cwinter1/automation/contents/work_log/latest.json`
- **Method:** GET
- Tap **Show More** to reveal Headers → tap **Add new header** three times:

| Header name | Value |
|---|---|
| `Authorization` | `Bearer YOUR_PAT_HERE` (paste your token directly after "Bearer ") |
| `Accept` | `application/vnd.github+json` |
| `X-GitHub-Api-Version` | `2022-11-28` |

- Rename the result variable: **`GHGetResponse`**

---

### Action 11 — Extract the SHA value

- Search: **Get Dictionary Value**
- **Get:** Value
- **Key:** `sha`
- **Dictionary:** `GHGetResponse`
- Rename the result variable: **`FileSHA`**

---

### Action 12 — Write the log entry to GitHub

- Search: **Get Contents of URL** (add a second one)
- **URL:** `https://api.github.com/repos/cwinter1/automation/contents/work_log/latest.json`
- **Method:** PUT
- Tap **Show More** → add four headers:

| Header name | Value |
|---|---|
| `Authorization` | `Bearer YOUR_PAT_HERE` (same token as Action 10) |
| `Accept` | `application/vnd.github+json` |
| `X-GitHub-Api-Version` | `2022-11-28` |
| `Content-Type` | `application/json` |

- **Request Body:** JSON
- Tap **+** to add three fields:

| Key | Type | Value |
|---|---|---|
| `message` | Text | `Work log ` + insert `TodayDate` + ` arrived ` + insert `ArrivalHHMM` |
| `content` | Text | insert variable `LogBase64` |
| `sha` | Text | insert variable `FileSHA` |

---

## Step 3 — Set up the Location Automation

1. In Shortcuts, tap the **Automation** tab (second tab, clock icon)
2. Tap **+** (top right) → **New Automation**
3. Scroll down to **Location** → tap it
4. Tap **Choose** → search for your office address → select it
5. Set the trigger to **Arrives**
6. Adjust the radius circle to just cover your building entrance
7. Tap **Next**
8. Tap **+** → search for `Work Log Arrival` → tap it to add
9. Tap **Next** → **disable "Ask Before Running"** (toggle it OFF) → tap **Done**

---

## Step 4 — Add a Home Screen button (manual fallback)

For days when the geo-fence misses:

1. In the My Shortcuts tab, long-press **Work Log Arrival**
2. Tap **Add to Home Screen**
3. Place it on your first Home Screen page
4. One tap runs the full Shortcut manually

---

## What happens each day

```
Walk into office
        |
iOS geo-fence fires (or tap Home Screen button)
        |
Actions 1-5: Compute arrival + leave time   (no internet needed)
        |
Action 6:  Banner notification fires        (no internet needed)
           "In since 08:32 — leave by 17:32"
        |
Actions 7-12: Log entry written to GitHub   (needs internet)
              Commit appears in repo history
```

Your full attendance history is in the Git commit log of `work_log/latest.json`.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Automation doesn't fire automatically | Location Services not set to Always | Settings → Privacy & Security → Location Services → Shortcuts → **Always** |
| Automation fires but asks "Run?" | "Ask Before Running" is ON | Shortcuts → Automation tab → tap the automation → turn it OFF |
| Notification doesn't appear | Notifications not allowed for Shortcuts | Settings → Notifications → Shortcuts → Allow Notifications ON |
| 401 Unauthorized on GitHub steps | PAT is wrong or expired | Regenerate PAT on github.com, paste into Action 10 and Action 12 headers |
| 409 Conflict on PUT | SHA mismatch (fired twice) | Run the Shortcut once manually from the Home Screen button — it will resync |
| No banner on bad network days | Expected — notification fires before network calls | Nothing to fix; this is by design |
| Low Power Mode suppresses automation | iOS restricts background activity | Plug in or disable Low Power Mode before commuting |
