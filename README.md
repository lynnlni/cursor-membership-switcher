# Cursor Membership Switcher

A macOS command-line tool to switch Cursor editor's membership type (Free / Pro / Pro+ / Ultra / Enterprise) by patching the bundled JavaScript — no network manipulation, no database triggers, no re-signing required.

**⚠️ Disclaimer: This project is for educational and research purposes only. Bypassing paid features violates Cursor's Terms of Service. Use at your own risk.**

---

## Background

Cursor (a VS Code-based AI editor) determines your membership tier via a network request to `/auth/full_stripe_profile`. The response is stored in both SQLite and in-memory reactive state.

Two naive approaches fail:
1. **SQLite write** — the network refresh overwrites it on every restart/login
2. **SQLite trigger** — the in-memory reactive state bypasses the database

The only reliable fix is patching the source: modifying `storeMembershipType()` in Cursor's bundled JS to intercept the value before it is written to both layers.

---

## How It Works

```js
// In workbench.desktop.main.js — before patch:
this.storeMembershipType = r => {
  const s = this.membershipType(), o = this.subscriptionStatus();
  r = r ?? Pa.FREE,   // ← network value written here
  this.storageService.store(MDt, r, -1, 1);
  // ...
};

// After patch — value is forced before any write:
this.storeMembershipType = r => {
  const s = this.membershipType(), o = this.subscriptionStatus();
  /*__cursor_membership_patch__*/r="pro";  // forced
  r = r ?? Pa.FREE,
  this.storageService.store(MDt, r, -1, 1);
  // ...
};
```

The patch is:
- A single line inserted before `r = r ?? Pa.FREE`
- Reversible via the `-r` restore option
- Auto-reapplied when Cursor updates (the JS file is replaced on each update)

---

## Requirements

- **macOS** (Cursor's JS path is hardcoded)
- **Python 3.11+** (or use the system Python on macOS 15+)
- **Cursor installed** at `/Applications/Cursor.app`

---

## Usage

```bash
# 1. Download or clone
git clone https://github.com/lynnlni/cursor-membership-switcher.git
cd cursor-membership-switcher

# 2. Quit Cursor if running
osascript -e 'quit app "Cursor"'

# 3. Run
python3 cursor_membership.py
```

```
======================================
  Cursor Membership Switcher (macOS)
======================================
  JS patch : not patched (original)
--------------------------------------
  [1] Free         (free)
  [2] Free Trial   (free_trial)
  [3] Pro          (pro)
  [4] Pro+         (pro_plus)
  [5] Ultra        (ultra)
  [6] Enterprise   (enterprise)
  [r] Restore original (remove patch)
  [q] Quit
--------------------------------------
  Select: 3

  Patched: storeMembershipType will always use "pro"
  Restart Cursor to apply.
```

---

## Building from Source

No build step needed — pure Python script:

```bash
# Verify Python version
python3 --version  # must be >= 3.11

# Run directly
python3 cursor_membership.py
```

---

## Demo Video

A live demo of the switcher in action (in Chinese):

- [Demo Recording](录屏2026-04-19%2009.45.29.mov)

---

## Technical Details

Full analysis blog post (Chinese):
- [飞书文档](https://asiainfo.feishu.cn/docx/NjXedrgiboPyHrxpS3GcacUnnud)

---

## License

MIT License — for educational purposes only.
