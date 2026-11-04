"""Add or update papers in papers.csv.

Add a paper from a DOI or arXiv ID (title, authors, year, venue and link are looked up):
    python scripts/paper.py add 10.1038/s41593-018-0310-2 --arms B2,Background --why "Many-task RNNs"
    python scripts/paper.py add 2207.03523 --arms B2 --status Reading --priority High
Add one by hand:
    python scripts/paper.py add --title "Some paper" --authors "A & B" --year 2025 --venue "bioRxiv" --link https://...
Update a paper (by id, as shown with `list`):
    python scripts/paper.py set yang-2019 --status Read --notes "Clusters of task-specialised units..."
    python scripts/paper.py set yang-2019 --append-notes "Second read: ..."
List papers (optionally filtered):
    python scripts/paper.py list --status "To read"

Fields: status = To read | Reading | Read | Key paper; priority = High | Medium | Low;
arms = A1, A2, B1, B2, C1, C2, Methods, Background (comma-separated).
Only the Python standard library is used.
"""
import argparse, csv, json, os, re, sys, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(HERE, '..', 'papers.csv')
FIELDS = ['id', 'title', 'authors', 'year', 'venue', 'link', 'arms', 'status', 'priority', 'why', 'notes', 'added']
STATUSES = ['To read', 'Reading', 'Read', 'Key paper']
PRIORITIES = ['High', 'Medium', 'Low']
ARMS = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2', 'Methods', 'Background']
UA = {'User-Agent': 'phd-reading-log/1.0 (paper metadata lookup)'}


def load():
    if not os.path.exists(CSV_PATH):
        return []
    with open(CSV_PATH, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def save(rows):
    with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, '') for k in FIELDS})


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
        return r.read()


def authors_str(names):
    names = [n for n in names if n]
    if not names:
        return ''
    if len(names) <= 4:
        return ', '.join(names[:-1]) + (' & ' if len(names) > 1 else '') + names[-1]
    return names[0] + ' et al.'


def lookup_arxiv(aid):
    xml = get('http://export.arxiv.org/api/query?id_list=' + urllib.parse.quote(aid))
    ns = {'a': 'http://www.w3.org/2005/Atom'}
    e = ET.fromstring(xml).find('a:entry', ns)
    if e is None or e.find('a:title', ns) is None:
        raise ValueError(f'arXiv ID {aid} not found')
    surn = [n.text.strip().split()[-1] for n in e.findall('a:author/a:name', ns)]
    return {'title': ' '.join(e.find('a:title', ns).text.split()), 'authors': authors_str(surn),
            'year': e.find('a:published', ns).text[:4], 'venue': f'arXiv {aid}', 'link': f'https://arxiv.org/abs/{aid}'}


def lookup_doi(doi):
    m = json.loads(get('https://api.crossref.org/works/' + urllib.parse.quote(doi)))['message']
    surn = [a.get('family') or a.get('name', '') for a in m.get('author', [])]
    year = ''
    for k in ('published-print', 'published-online', 'issued', 'posted'):
        if m.get(k, {}).get('date-parts'):
            year = str(m[k]['date-parts'][0][0]); break
    venue = (m.get('container-title') or [''])[0] or m.get('publisher', '')
    return {'title': ' '.join((m.get('title') or [''])[0].split()), 'authors': authors_str(surn),
            'year': year, 'venue': venue, 'link': f'https://doi.org/{doi}'}


def lookup(ident):
    ident = ident.strip()
    ident = re.sub(r'^https?://(dx\.)?doi\.org/', '', ident)
    m = re.search(r'arxiv\.org/(abs|pdf)/([^\s?#]+?)(v\d+)?(\.pdf)?$', ident)
    if m:
        return lookup_arxiv(m.group(2))
    if re.fullmatch(r'\d{4}\.\d{4,5}(v\d+)?', ident) or re.fullmatch(r'[a-z\-]+(\.[A-Z]{2})?/\d{7}', ident):
        return lookup_arxiv(re.sub(r'v\d+$', '', ident))
    if ident.startswith('10.'):
        return lookup_doi(ident)
    raise ValueError(f'Not a DOI or arXiv ID: {ident}')


def make_id(rows, p):
    first = re.sub(r'[^a-z]', '', (p.get('authors') or 'paper').split(',')[0].split('&')[0].split()[0].lower()) or 'paper'
    base = f"{first}-{p.get('year') or 'nd'}"
    ids, i, out = {r['id'] for r in rows}, 2, base
    while out in ids:
        out = f'{base}-{i}'; i += 1
    return out


def check(val, allowed, name):
    if val and val not in allowed:
        sys.exit(f'{name} must be one of: {", ".join(allowed)}')


def norm_arms(s):
    arms = [a.strip() for a in re.split(r'[;,]', s or '') if a.strip()]
    for a in arms:
        check(a, ARMS, 'arms')
    return '; '.join(arms)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    a = sub.add_parser('add')
    a.add_argument('ident', nargs='?', help='DOI, arXiv ID, or a doi.org / arxiv.org link')
    for f in ('title', 'authors', 'year', 'venue', 'link', 'why', 'notes', 'arms'):
        a.add_argument('--' + f, default='')
    a.add_argument('--status', default='To read'); a.add_argument('--priority', default='Medium')
    s = sub.add_parser('set')
    s.add_argument('id')
    for f in ('title', 'authors', 'year', 'venue', 'link', 'why', 'notes', 'arms', 'status', 'priority', 'append_notes'):
        s.add_argument('--' + f.replace('_', '-'), dest=f, default=None)
    l = sub.add_parser('list')
    l.add_argument('--status'); l.add_argument('--arm')
    args = ap.parse_args()
    rows = load()

    if args.cmd == 'add':
        check(args.status, STATUSES, 'status'); check(args.priority, PRIORITIES, 'priority')
        p = {}
        if args.ident:
            try:
                p = lookup(args.ident)
            except Exception as e:
                sys.exit(f'Could not look up {args.ident}: {e}. Add it by hand with --title etc.')
        for f in ('title', 'authors', 'year', 'venue', 'link'):
            if getattr(args, f):
                p[f] = getattr(args, f)
        if not p.get('title'):
            sys.exit('Give a DOI / arXiv ID, or at least --title.')
        dup = [r for r in rows if r['title'].strip().lower() == p['title'].strip().lower() or (p.get('link') and r['link'] == p['link'])]
        if dup:
            sys.exit(f"Already in the log as '{dup[0]['id']}'. Use `set` to update it.")
        p.update(arms=norm_arms(args.arms), status=args.status, priority=args.priority, why=args.why,
                 notes=args.notes, added=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
        p['id'] = make_id(rows, p)
        rows.append(p); save(rows)
        print(f"Added {p['id']}: {p['title']} ({p.get('authors', '')}, {p.get('year', '')})")

    elif args.cmd == 'set':
        r = next((r for r in rows if r['id'] == args.id), None)
        if not r:
            sys.exit(f'No paper with id {args.id}. Run `python scripts/paper.py list` to see ids.')
        if args.status: check(args.status, STATUSES, 'status')
        if args.priority: check(args.priority, PRIORITIES, 'priority')
        for f in ('title', 'authors', 'year', 'venue', 'link', 'why', 'notes', 'status', 'priority'):
            v = getattr(args, f)
            if v is not None:
                r[f] = v
        if args.arms is not None:
            r['arms'] = norm_arms(args.arms)
        if args.append_notes:
            r['notes'] = (r.get('notes', '') + '\n' if r.get('notes') else '') + args.append_notes
        save(rows)
        print(f"Updated {r['id']}: status {r['status']}, priority {r['priority']}")

    else:
        for r in rows:
            if args.status and r['status'] != args.status:
                continue
            if args.arm and args.arm not in r['arms']:
                continue
            print(f"{r['id']:<34} {r['status']:<10} {r['priority']:<7} {r['title'][:70]}")


if __name__ == '__main__':
    main()
