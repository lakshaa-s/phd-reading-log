"""Weekly paper finder: search recent papers, file them under plan arms, write suggestions.csv.

Runs every Monday from .github/workflows/suggest.yml, or by hand:
    python scripts/suggest.py                # search the last `days_back` days (suggest_config.json)
    python scripts/suggest.py --days 14      # search further back
    python scripts/suggest.py --dry-run      # print what it would suggest, change nothing

Sources: arXiv (q-bio.NC, cs.NE, and matching cs.LG), bioRxiv (neuroscience), and OpenAlex
(journals, by search phrase). A paper is suggested only if it contains a `require_any` term from
suggest_config.json; each arm's terms decide where it is filed. Papers already in papers.csv,
or already suggested (including ones you dismissed), are never suggested again.
Only the Python standard library is used.
"""
import argparse, csv, json, os, re, sys, time, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
CONFIG = os.path.join(ROOT, 'suggest_config.json')
PAPERS = os.path.join(ROOT, 'papers.csv')
OUT = os.path.join(ROOT, 'suggestions.csv')
FIELDS = ['sid', 'week', 'title', 'authors', 'year', 'venue', 'link', 'arms', 'score', 'matched', 'summary', 'status']
UA = {'User-Agent': 'phd-reading-log/1.0 (weekly paper suggestions; github.com/lakshaa-s/phd-reading-log)'}
KEEP_NEW_WEEKS = 6     # unreviewed suggestions older than this are dropped from the list


def get(url, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return r.read()
        except Exception as e:
            if i == tries - 1:
                raise
            print(f'  retrying after {e}', file=sys.stderr)
            time.sleep(5 * (i + 1))


def norm_title(t):
    return re.sub(r'[^a-z0-9]', '', (t or '').lower())


def authors_str(names):
    names = [n for n in names if n]
    if not names:
        return ''
    if len(names) <= 4:
        return ', '.join(names[:-1]) + (' & ' if len(names) > 1 else '') + names[-1]
    return names[0] + ' et al.'


def clean(s):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', s or '')).strip()


# ------------------------------------------------------------------ sources
def from_arxiv(cfg, since):
    q = urllib.parse.urlencode({'search_query': cfg['sources']['arxiv_query'], 'sortBy': 'submittedDate',
                                'sortOrder': 'descending', 'max_results': cfg['sources'].get('arxiv_max_results', 400)})
    root = ET.fromstring(get('https://export.arxiv.org/api/query?' + q))
    ns = {'a': 'http://www.w3.org/2005/Atom'}
    out = []
    for e in root.findall('a:entry', ns):
        pub = e.findtext('a:published', '', ns)[:10]
        if pub < since:
            continue
        aid = re.sub(r'v\d+$', '', e.findtext('a:id', '', ns).rsplit('/abs/', 1)[-1])
        out.append({'title': clean(e.findtext('a:title', '', ns)), 'abstract': clean(e.findtext('a:summary', '', ns)),
                    'authors': authors_str([n.text.strip().split()[-1] for n in e.findall('a:author/a:name', ns) if n.text]),
                    'year': pub[:4], 'venue': f'arXiv {aid}', 'link': f'https://arxiv.org/abs/{aid}'})
    return out


def from_biorxiv(cfg, since, until):
    cats = {c.lower() for c in cfg['sources'].get('biorxiv_categories', ['neuroscience'])}
    out, cursor, seen = [], 0, set()
    while True:
        j = json.loads(get(f'https://api.biorxiv.org/details/biorxiv/{since}/{until}/{cursor}'))
        coll = j.get('collection', [])
        for p in coll:
            if p.get('category', '').lower() not in cats or p.get('doi') in seen:
                continue
            seen.add(p.get('doi'))          # the API lists every version; keep the first
            surn = [a.split(',')[0].strip() for a in p.get('authors', '').split(';')]
            out.append({'title': clean(p.get('title')), 'abstract': clean(p.get('abstract')), 'authors': authors_str(surn),
                        'year': p.get('date', '')[:4], 'venue': 'bioRxiv', 'link': 'https://doi.org/' + p['doi']})
        total = int((j.get('messages') or [{}])[0].get('total', 0) or 0)
        cursor += len(coll)
        if not coll or cursor >= total:
            return out
        time.sleep(0.5)


def openalex_abstract(inv):
    if not inv:
        return ''
    pos = sorted((i, w) for w, idx in inv.items() for i in idx)
    return ' '.join(w for _, w in pos)


def from_openalex(cfg, since):
    out = []
    for phrase in cfg['sources'].get('openalex_searches', []):
        q = urllib.parse.urlencode({'search': phrase, 'per-page': 25, 'sort': 'publication_date:desc',
                                    'filter': f'from_publication_date:{since},type:article'})
        j = json.loads(get('https://api.openalex.org/works?' + q))
        for w in j.get('results', []):
            src = ((w.get('primary_location') or {}).get('source') or {}).get('display_name') or ''
            if src.lower() in ('biorxiv', 'arxiv', 'arxiv (cornell university)'):
                continue                    # those come from their own sources
            doi = (w.get('doi') or '').replace('https://doi.org/', '')
            surn = [((a.get('author') or {}).get('display_name') or '').split()[-1:] for a in w.get('authorships', [])]
            out.append({'title': clean(w.get('title') or w.get('display_name')), 'abstract': openalex_abstract(w.get('abstract_inverted_index')),
                        'authors': authors_str([s[0] for s in surn if s]), 'year': str(w.get('publication_year') or ''),
                        'venue': src, 'link': 'https://doi.org/' + doi if doi else (w.get('id') or '')})
        time.sleep(0.3)
    return out


# ------------------------------------------------------------------ scoring
def score(paper, cfg):
    title, abstract = ' ' + paper['title'].lower() + ' ', ' ' + paper['abstract'].lower() + ' '
    text = title + abstract
    if not any(t in text for t in cfg['require_any']) or any(t in text for t in cfg.get('exclude_any', [])):
        return 0, [], []
    per_arm, matched = {}, set()
    for arm, a in cfg['arms'].items():
        s = 0
        for t in a['terms']:
            hit = 3 if t in title else (1 if t in abstract else 0)
            if hit:
                s += hit; matched.add(t.strip())
        if s:
            per_arm[arm] = s
    total = sum(per_arm.values())
    ranked = sorted(per_arm, key=lambda k: -per_arm[k])
    arms = [a for a in ranked if per_arm[a] >= 2][:3] or ranked[:1]
    return total, arms, sorted(matched)


def load_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--days', type=int)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    cfg = json.load(open(CONFIG, encoding='utf-8'))
    today = datetime.now(timezone.utc).date()
    since = (today - timedelta(days=args.days or cfg.get('days_back', 7))).isoformat()
    week = (today - timedelta(days=today.weekday())).isoformat()       # Monday of this week

    found = []
    for name, fn in [('arXiv', lambda: from_arxiv(cfg, since)), ('bioRxiv', lambda: from_biorxiv(cfg, since, today.isoformat())),
                     ('OpenAlex', lambda: from_openalex(cfg, since))]:
        try:
            got = fn(); found += got
            print(f'{name}: {len(got)} papers since {since}')
        except Exception as e:                       # one source failing should not stop the others
            print(f'{name}: failed ({e})', file=sys.stderr)

    papers, old = load_csv(PAPERS), load_csv(OUT)
    known = {norm_title(r['title']) for r in papers + old} | {r['link'] for r in papers + old if r.get('link')}
    cands, seen = [], set()
    for p in found:
        k = norm_title(p['title'])
        if not k or k in known or p['link'] in known or k in seen:
            continue
        seen.add(k)
        s, arms, matched = score(p, cfg)
        if s >= cfg.get('min_score', 4):
            cands.append({**p, 'score': s, 'arms': arms, 'matched': matched})
    cands.sort(key=lambda p: -p['score'])

    picked, per_arm = [], {}
    for p in cands:
        if len(picked) >= cfg.get('max_suggestions', 20):
            break
        if per_arm.get(p['arms'][0], 0) >= cfg.get('max_per_arm', 6):
            continue
        per_arm[p['arms'][0]] = per_arm.get(p['arms'][0], 0) + 1
        picked.append(p)

    print(f'{len(cands)} relevant, {len(picked)} suggested for week of {week}')
    for p in picked:
        print(f"  [{'; '.join(p['arms'])}] {p['score']:>3}  {p['title'][:90]}")
    if args.dry_run:
        return

    cutoff = (date.fromisoformat(week) - timedelta(weeks=KEEP_NEW_WEEKS)).isoformat()
    kept = [r for r in old if r.get('status') != 'new' or r.get('week', '') >= cutoff]
    n0 = sum(1 for r in old if r.get('week') == week)
    rows = [{'sid': f'{week}-{n0 + i + 1:02d}', 'week': week, 'title': p['title'], 'authors': p['authors'], 'year': p['year'],
             'venue': p['venue'], 'link': p['link'], 'arms': '; '.join(p['arms']), 'score': p['score'],
             'matched': '; '.join(p['matched']), 'summary': p['abstract'][:400] + ('…' if len(p['abstract']) > 400 else ''),
             'status': 'new'} for i, p in enumerate(picked)]
    with open(OUT, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows + kept:
            w.writerow({k: r.get(k, '') for k in FIELDS})
    print(f'wrote {OUT}')


if __name__ == '__main__':
    main()
