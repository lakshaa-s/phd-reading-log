# PhD Reading Log

Papers I've read and plan to read during my PhD on morphological neural networks (Imperial, with Marcus Ghosh), tagged by plan arm. The site is generated from `papers.csv` and published with GitHub Pages.

## Editing on the site

Click **Edit** on the site and paste a fine-grained personal access token (GitHub → Settings → Developer settings → Fine-grained tokens) with access to this repository only and **Contents: Read and write** permission. The token stays in that browser. Then you can add papers (with DOI or arXiv look-up), change status, priority and arms, write notes and remove papers; each save is a commit to `papers.csv`, and the public site updates a minute or two later. **Stop editing** removes the token from the browser.

## Adding and updating papers from the terminal

From the repo folder:

```
python scripts/paper.py add 10.1038/s41593-018-0310-2 --arms B2,Background --why "Many-task RNNs; task-specialised clusters"
python scripts/paper.py add https://arxiv.org/abs/2207.03523 --arms B2,Methods --status Reading --priority High
python scripts/paper.py set yang-2019 --status Read --append-notes "Clusters form by task family."
python scripts/paper.py list --status "To read"
git commit -am "Reading log: add Yang 2019" && git push
```

`add` looks up the title, authors, year, venue and link from a DOI (Crossref) or an arXiv ID. For anything else, give the fields by hand: `add --title "..." --authors "..." --year 2026 --venue "..." --link https://...`.

You can also edit `papers.csv` directly in Excel, Numbers or the GitHub web editor. Keep the header row and these values:

| Field | Values |
| --- | --- |
| status | To read · Reading · Read · Key paper |
| priority | High · Medium · Low |
| arms | A1 build with motifs (evolution) · A2 build with morphological neurons (gradients) · B1 E:I balance · B2 multisensory integration · C1 perturbing morphology · C2 disease-model sets · Methods · Background (separate several with `;`) |

## Weekly paper suggestions

Every Monday morning a GitHub Action (`.github/workflows/suggest.yml`) runs `scripts/suggest.py`. It searches the past week of arXiv (q-bio.NC, cs.NE and matching cs.LG), bioRxiv neuroscience and journals (through OpenAlex), and keeps papers that match the PhD topics. It files each one under plan arms and writes them to `suggestions.csv`. They appear on the site under **Suggested this week**. In edit mode, **Add to log** copies a paper into `papers.csv` as To read, and **Dismiss** hides it. Nothing already in the log, and nothing dismissed, is suggested again.

- Run it now: GitHub → Actions → Weekly paper suggestions → Run workflow (you can choose how many days back to search).
- Steer it: edit `suggest_config.json`. `require_any` decides what counts as relevant, each arm's `terms` decide where a paper is filed, and `max_suggestions`, `max_per_arm` and `min_score` control how many you get.
- Try it locally: `python scripts/suggest.py --dry-run` prints what it would suggest without changing anything.

## Viewing the site locally

```
python -m http.server 8000
```

then open http://localhost:8000. (Opening `index.html` directly does not work, because the page loads `papers.csv`.)

## Publishing

The site is served by GitHub Pages from the `main` branch root: Settings → Pages → Source: Deploy from a branch → `main` / root. Every push updates the site within a minute or two.
