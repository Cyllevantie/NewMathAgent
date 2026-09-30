import zipfile, re, xml.etree.ElementTree as ET, sys

P = r'C:\Users\Cyl\Downloads\new math agent\data\附件.xlsx'
NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
z = zipfile.ZipFile(P)

# shared strings
shared = []
if 'xl/sharedStrings.xml' in z.namelist():
    root = ET.fromstring(z.read('xl/sharedStrings.xml'))
    for si in root.findall('m:si', NS):
        txt = ''.join(t.text or '' for t in si.iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t'))
        shared.append(txt)

def col_idx(ref):
    m = re.match(r'([A-Z]+)(\d+)', ref)
    letters = m.group(1)
    idx = 0
    for ch in letters:
        idx = idx*26 + (ord(ch)-64)
    return idx-1, int(m.group(2))-1  # 0-based col, row

def parse_sheet(name):
    root = ET.fromstring(z.read(name))
    out = []  # rows as dict col->value
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
            isel = c.find('m:is', NS)
            if isel is not None and t == 'inlineStr':
                val = ''.join(tt.text or '' for tt in isel.iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t'))
            d[ci] = val
        out.append(d)
    return out

for sheetname in ['xl/worksheets/sheet1.xml', 'xl/worksheets/sheet2.xml']:
    data = parse_sheet(sheetname)
    print('=====', sheetname, 'rows=', len(data))
    if not data: continue
    hdr = data[0]
    ncol = max(hdr.keys())+1 if hdr else 0
    colnames = {i: (hdr.get(i,'') or '') for i in range(ncol)}
    print('ncol', ncol)
    # print col letters + header text
    def colletter(i):
        s=''
        i+=1
        while i>0:
            i, r = divmod(i-1, 26); s = chr(65+r)+s
        return s
    print(' | '.join(f'{colletter(i)}:{colnames[i]}' for i in range(ncol)))
    # male/female split by col U/V (Y Z-score and Y conc): col indices -> find by name
    # We'll guess: header order per appendix. Print first data rows summary.
    for r in data[1:6]:
        print([ (colletter(i), (str(r.get(i))[:26] if r.get(i) is not None else '')) for i in sorted(r.keys())])
