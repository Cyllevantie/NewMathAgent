import zipfile, re, xml.etree.ElementTree as ET, collections

P = r'C:\Users\Cyl\Downloads\new math agent\data\附件.xlsx'
NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
z = zipfile.ZipFile(P)

shared = []
if 'xl/sharedStrings.xml' in z.namelist():
    root = ET.fromstring(z.read('xl/sharedStrings.xml'))
    for si in root.findall('m:si', NS):
        shared.append(''.join(t.text or '' for t in si.iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t')))

def col_idx(ref):
    m = re.match(r'([A-Z]+)(\d+)', ref)
    idx = 0
    for ch in m.group(1):
        idx = idx*26 + (ord(ch)-64)
    return idx-1, int(m.group(2))-1

def parse_sheet(name):
    root = ET.fromstring(z.read(name))
    out = []
    for row in root.iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row'):
        d = {}
        for c in row.findall('m:c', NS):
            ref = c.get('r')
            if not ref: continue
            ci, ri = col_idx(ref)
            t = c.get('t')
            v = c.find('m:v', NS)
            val = None
            if v is not None and v.text is not None:
                val = v.text
                if t == 's':
                    val = shared[int(val)]
            d[ci] = val
        out.append(d)
    return out

def gw(s):
    # '11w+6' -> 11.857 ; '23w' -> 23.0 ; '' -> None
    s = (s or '').strip()
    if not s: return None
    m = re.match(r'(\d+)\s*w(?:\+(\d+))?', s, re.I)
    if not m: return None
    w = int(m.group(1)); d = int(m.group(2)) if m.group(2) else 0
    return round(w + d/7.0, 4)

for sheetname, label in [('xl/worksheets/sheet1.xml','男胎 sheet1'), ('xl/worksheets/sheet2.xml','女胎 sheet2')]:
    data = parse_sheet(sheetname)[1:]  # drop header
    print('=====', label, 'data rows', len(data))
    # B=1 subject code, J=9 gestational week, V=21 Yconc (sheet1), AB=28
    codes = [r.get(1) for r in data]
    nsubj = len(set(codes))
    print('distinct subjects:', nsubj)
    c = collections.Counter(collections.Counter(codes).values())
    print('draws-per-subject histogram (n_draws: n_subjects):', dict(sorted(c.items())))
    gws = [gw(r.get(9)) for r in data]
    gws = [g for g in gws if g is not None]
    print('GA weeks min/median/max:', min(gws), sorted(gws)[len(gws)//2], max(gws))
    ab_vals = [(r.get(27) or '').strip() for r in data]  # AB = index 27 (aneuploidy)
    nn = [a for a in ab_vals if a]
    print('AB(aneuploidy) nonblank rows:', len(nn), 'values:', collections.Counter(nn).most_common())
    # subject-level: a subject is 'any-aneuploidy' if any of its rows carries an AB label
    subj_ab = collections.defaultdict(list)
    for r in data:
        v = (r.get(27) or '').strip()
        if v:
            subj_ab[r.get(1)].append(v)
    print('subjects with any aneuploid AB label:', len(subj_ab), 'of', len(set(codes)))
    # among aneuploid subjects, which chromosomes involved
    chroms = collections.Counter()
    for labs in subj_ab.values():
        for lab in labs:
            for ch in ['T13','T18','T21']:
                if ch in lab:
                    chroms[ch]+=1
    print('chromosome involvement (subject rows):', dict(chroms))
    if label.startswith('男胎'):
        vs = []
        for r in data:
            try:
                v = float(r.get(21))
                vs.append(v)
            except (TypeError, ValueError):
                pass
        vs.sort()
        print('Yconc (V) n/min/median/max:', len(vs), round(vs[0],4), round(vs[len(vs)//2],4), round(vs[-1],4))
        print('rows with V>=0.04 share:', round(sum(1 for v in vs if v>=0.04)/len(vs),4))
        rowwise = collections.defaultdict(list)
        for r in data:
            rowwise[r.get(1)].append(gw(r.get(9)))
        print('n subjects with >=2 draws:', sum(1 for k,v in rowwise.items() if len([x for x in v if x is not None])>=2))
    else:
        wv = []
        for r in data:
            try:
                wv.append(float(r.get(22)))  # W=22
            except (TypeError, ValueError):
                pass
        wv.sort()
        print('Xconc (W) n/neg share/min/median/max:', len(wv), round(sum(1 for x in wv if x<0)/len(wv),3), round(wv[0],4), round(wv[len(wv)//2],4), round(wv[-1],4))
        wv = []
        for r in data:
            try:
                wv.append(float(r.get(22)))  # W=22
            except (TypeError, ValueError):
                pass
        wv.sort()
        print('Xconc (W) n/neg share/min/median/max:', len(wv), round(sum(1 for x in wv if x<0)/len(wv),3), round(wv[0],4), round(wv[len(wv)//2],4), round(wv[-1],4))
