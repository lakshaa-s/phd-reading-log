# PhD Reading Log

Papers I've read and plan to read during my PhD on morphological neural networks (Imperial, with Marcus Ghosh), tagged by plan arm. The site is generated from `papers.csv` and published with GitHub Pages.

## Adding and updating papers

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

## Viewing the site locally

```
python -m http.server 8000
```

then open http://localhost:8000. (Opening `index.html` directly does not work, because the page loads `papers.csv`.)

## Publishing

The site is served by GitHub Pages from the `main` branch root: Settings → Pages → Source: Deploy from a branch → `main` / root. Every push updates the site within a minute or two.
