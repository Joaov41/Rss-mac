import re,sys,os
I="/Volumes/screen/rss latest ios27 - UI fix copy/RSSReaderApp"
M="/Volumes/screen/rss mac copy/RSSReaderApp"
pat=re.compile(r'^\s*(?:@\w+(?:\([^)]*\))?\s+)*(?:(?:private|fileprivate|public|internal|open|static|final|override|nonisolated|mutating|class|@MainActor)\s+)*(func\s+[A-Za-z_][\w]*|struct\s+\w+|class\s+\w+|enum\s+\w+|actor\s+\w+|protocol\s+\w+|extension\s+[\w.]+|case\s+\w+|(?:@Published\s+)?(?:var|let)\s+\w+)')
def syms(path):
    out={}
    depth=0
    for ln,line in enumerate(open(path,errors='ignore'),1):
        m=pat.match(line)
        if m and depth<=2:
            key=re.sub(r'\s+',' ',m.group(1))
            if key.startswith(('var ','let ','case ')) and depth>1: pass
            else: out.setdefault(key,ln)
        t=re.sub(r'"(?:\\.|[^"\\])*"','""',line).split('//')[0]
        depth+=t.count('{')-t.count('}')
    return out
common=[]
for root,_,files in os.walk(I):
    for f in files:
        if f.endswith('.swift'):
            rel=os.path.relpath(os.path.join(root,f),I)
            if os.path.exists(os.path.join(M,rel)): common.append(rel)
for rel in sorted(common):
    a=syms(os.path.join(I,rel)); b=syms(os.path.join(M,rel))
    onlyI=sorted((k for k in a if k not in b), key=lambda k:a[k])
    onlyM=sorted((k for k in b if k not in a), key=lambda k:b[k])
    if onlyI or onlyM:
        print(f"### {rel}")
        if onlyI: print("  iOS only: "+", ".join(f"{k}@{a[k]}" for k in onlyI))
        if onlyM: print("  Mac only: "+", ".join(f"{k}@{b[k]}" for k in onlyM))
