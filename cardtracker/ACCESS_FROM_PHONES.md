# Use Card Tracker on your iPhone (and Jake's) — free & private

This keeps **all your data on your Mac** (nothing goes to the cloud) and lets both
iPhones open the app from anywhere using **Tailscale**, a free private network.

Because every device talks to the *one* app running on your Mac, the data is always
shared and consistent: whoever adds or edits a card, the other sees it after a refresh.

> ⚠️ The one catch with this free route: **your Mac must be powered on and running the
> Card Tracker app** whenever you or Jake want to use it. (See "Keep the Mac awake" below.)

---

## One‑time setup (about 10 minutes)

### 1. Install Tailscale on your Mac
1. Go to **https://tailscale.com/download** → download the **macOS** app.
2. Open it and **sign in** (you can use your Google or Apple account — it's free).
3. After sign‑in, click the **Tailscale icon** in your Mac's top menu bar. It shows
   **This device** with a name like `johns-macbook` and an address like `100.x.y.z`.
   **Write that `100.x.y.z` number down — that's your Mac's private address.**

### 2. Make sure the app is running
- Double‑click your **CardTracker** Desktop icon (the Terminal window it opens is the
  app's engine — leave it open).
- If macOS pops up **"Do you want to allow incoming network connections?"** for Python,
  click **Allow**.

### 3. Put Tailscale on your iPhone
1. App Store → install **Tailscale**.
2. Open it and **sign in with the same account** you used on the Mac.
3. Flip the toggle **On** (you'll see a small VPN key icon at the top — that's normal).

### 4. Put Tailscale on Jake's iPhone
Easiest for family: on Jake's phone, install Tailscale and **sign in with the same
account**. (Or, to keep separate logins: on your Mac go to the Tailscale admin console
→ **Users → Invite**, and email Jake an invite so he joins your network with his own
account. Either works.)

### 5. Open the app on each phone
1. Make sure Tailscale is **On** (step 3).
2. Open **Safari** and go to:  **`http://100.x.y.z:8001`**
   (use the number from step 1 — keep the `:8001` on the end).
3. The Card Tracker Home screen loads. 🎉

### 6. Add it to the Home Screen (so it feels like a real app)
In Safari with the app open: tap the **Share** button (the square with the up‑arrow) →
**Add to Home Screen** → **Add**. You'll get an app icon (your logo, if you set one in
**Settings**) that opens full‑screen. Do this on **both** phones.

---

## Keep the Mac awake (so the phones can always reach it)
The phones can only reach the app while the Mac is on and not asleep.
- **System Settings → Lock Screen / Battery →** set **"Turn display off…"** to a longer
  time, and (on a desktop/plugged‑in Mac) **"Prevent automatic sleeping when the display
  is off."**
- Leave the **CardTracker Terminal window open** — closing it stops the app.

---

## Good to know
- **It's private.** Tailscale encrypts all traffic, and only devices signed into *your*
  network can reach the app. It is **not** open to the public internet.
- **`http`, not `https`, is fine here** — Tailscale already encrypts the connection.
- **Same data everywhere.** Both phones and the Mac read/write the one database on your
  Mac. Pull‑to‑refresh (or reopen) to see the latest after the other person makes a change.
- **Backups.** Your data lives in the `CardTrackerData` folder on your Mac. Use
  **Settings → Export inventory (CSV)** now and then for a backup, and make sure that Mac
  is included in Time Machine.
- **Want a password too?** You don't strictly need one on Tailscale (only your devices can
  connect), but there's an optional second layer built in: **Settings → Security → Shared
  password**. Set one and everyone gets a sign-in screen the first time (then it remembers
  them). Leave it blank to keep it off. Give the same password to Jake.

## Troubleshooting
- **"Safari can't open the page."** Check: (a) Tailscale toggle is **On** on the phone,
  (b) the Mac is **awake** with the CardTracker Terminal window open, (c) you typed the
  address exactly, including **`:8001`**.
- **It worked at home but not away.** That's usually the Mac asleep — wake it / adjust the
  sleep settings above.
- **Wrong address?** Re‑check the `100.x.y.z` number in the Mac's Tailscale menu‑bar icon.
