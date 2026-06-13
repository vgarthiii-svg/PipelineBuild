# 📱 Add Card Tracker to both iPhones — step by step

Three parts: set up the Mac once, then add the app to each phone.
(The address `100.x.x.x` below is an example — you'll use your Mac's real number from Part A.)

---

## Part A — On your Mac (one time, ~5 min)
- [ ] 1. Browser → **https://tailscale.com/download** → download the **macOS** app.
- [ ] 2. Open it → **Sign in** (Google or Apple — free).
- [ ] 3. Click the **Tailscale icon** in the Mac's **top menu bar** (top-right of screen).
- [ ] 4. It shows your Mac with an address like **`100.92.14.7`**.
       ✍️ **Write that number down** — you'll type it on both phones.
- [ ] 5. Make sure Card Tracker is running (double-click **CardTracker**, or it's already
       running if auto-start is on). If macOS asks to **allow incoming connections**, click **Allow**.

---

## Part B — On YOUR iPhone (~3 min)
- [ ] 1. **App Store** → search **Tailscale** → install.
- [ ] 2. Open **Tailscale** → **sign in with the same account** as the Mac → toggle **On**
       (a small VPN key icon appears at the top — that's normal).
- [ ] 3. Open **Safari** and type this exactly (your number, keep the `:8001`):

           http://100.92.14.7:8001

- [ ] 4. The Card Tracker **Home** screen loads. 🎉
- [ ] 5. Tap the **Share** button (the square with an **up-arrow ⬆️**).
- [ ] 6. Scroll down → tap **Add to Home Screen** → tap **Add**.
- [ ] 7. Tap the new **Card Tracker** icon — it opens full-screen like a real app.

---

## Part C — On JAKE's iPhone (~3 min)
First get Jake onto your Tailscale network — pick ONE:
  - **Easiest:** install Tailscale on his phone and **sign in with the same account** you used.
  - **His own login:** on your Mac go to **https://login.tailscale.com** → **Users → Invite** →
    email Jake an invite → he installs Tailscale and signs in with that.

Then on Jake's phone:
- [ ] 1. **App Store** → install **Tailscale** → sign in (per the choice above) → toggle **On**.
- [ ] 2. **Safari** → type the **same address**:  `http://100.92.14.7:8001`
- [ ] 3. Tap **Share ⬆️ → Add to Home Screen → Add**.
- [ ] 4. Done — Jake taps the icon and sees the **same collection** you do.

---

## After it's set up
- Both of you just **tap the Home Screen icon**. As long as **Tailscale is On** (it stays on in
  the background) and your **Mac is awake and running the app**, it opens to your shared data.
- If you set a **password** (Settings → Security), each phone asks for it once, then remembers it.

## If a phone says "can't open the page"
1. Tailscale toggle is **On** on the phone.
2. The **Mac is awake** with Card Tracker running.
3. You typed the address exactly, including **`:8001`**.
4. Double-check the `100.x.x.x` number in the Mac's Tailscale menu-bar icon.
