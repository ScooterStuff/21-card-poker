# 21 Card Poker — Web

Modern web version of the 21-card poker game. Pure HTML/CSS/vanilla JS — **no build step**.

## Run locally

Just open `web/index.html` in any modern browser, or serve with a static server:

```powershell
# from repo root
cd web
python -m http.server 8080
# then visit http://localhost:8080
```

## Deploy

The whole `web/` folder is the entire site. Pick any one:

### GitHub Pages (one-click via included workflow)

1. Commit + push this repo to GitHub.
2. In your repo: **Settings → Pages → Build and deployment → Source: GitHub Actions**.
3. Push to `main`. The included `.github/workflows/deploy.yml` publishes the `web/` folder automatically.
4. Your site lives at `https://<user>.github.io/<repo>/`.

### Netlify

- Drag-and-drop the `web/` folder onto https://app.netlify.com/drop, **or**
- Connect the repo and set **Publish directory** to `web` (no build command needed).

### Vercel

- `vercel` from inside the `web/` folder, **or**
- Import the repo and set the **Root Directory** to `web` (Framework Preset: *Other*, no build command).

### Cloudflare Pages

- Connect the repo, set **Build output directory** to `web`, leave build command empty.

## File map

```
web/
  index.html       # markup
  styles.css       # modern dark UI
  js/
    game.js        # deck, betting, round flow
    hand_eval.js   # hand ranking + joker resolution
    ai.js          # AI opponent
    main.js        # UI controller (entry)
```
