"""Expand sxhkd bindings without executing their commands or shell expansion."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import shlex


def expand(text):
    """sxhkd comma lists, a-z/1-9 ranges and the empty `_` sequence."""
    match=re.search(r'(?<!\\)\{([^{}]*)\}',text)
    if not match:return [text.replace('\\{','{').replace('\\}','}')]
    values=[]
    for item in match[1].split(','):
        ranged=re.fullmatch(r'([a-zA-Z0-9])-([a-zA-Z0-9])',item)
        if ranged:
            a,b=map(ord,ranged.groups());values.extend(map(chr,range(a,b+(1 if b>=a else -1),1 if b>=a else -1)))
        else:values.append('' if item=='_' else item)
    return [item for value in values for item in expand(text[:match.start()]+value+text[match.end():])]


def key_id(text):
    aliases={'ctrl':'CTRL','control':'CTRL','super':'SUPER','alt':'ALT','shift':'SHIFT','mod4':'SUPER'}
    parts=[p.strip() for p in text.strip().split('+') if p.strip()]
    mods={aliases[p.lower()] for p in parts[:-1] if p.lower() in aliases}
    if len(mods)!=len(parts)-1:raise ValueError('Unsupported modifier sequence: '+text)
    key=parts[-1]
    if key.lower() in ('left','right','up','down'):key=key.capitalize()
    if key.lower().startswith('kp_'):
        suffix=key[3:];key='KP_'+(suffix.capitalize() if not suffix.isdecimal() else suffix)
    key={'grave':'grave','tab':'Tab','return':'Return','print':'Print','space':'space','escape':'Escape'}.get(key.lower(),key.upper() if len(key)==1 else key)
    return ' + '.join([*(m for m in ('SUPER','CTRL','ALT','SHIFT') if m in mods),key])


def parse(text):
    groups=[];key=None;command=[];start=0
    def flush():
        nonlocal key,command
        if key is None:return
        keys=expand(key);commands=expand(' '.join(command).replace('\\\n',' '))
        if not commands or not command:raise ValueError('Missing command at line '+str(start))
        if len(commands)==1:commands*=len(keys)
        if len(keys)!=len(commands):raise ValueError(f'Expansion mismatch line {start}: {len(keys)} keys/{len(commands)} commands')
        groups.extend(dict(key=key_id(k),command=c.strip(),line=start) for k,c in zip(keys,commands))
        key=None;command=[]
    continued=False
    for number,line in enumerate(text.splitlines(),1):
        if not line.strip() or line.lstrip().startswith('#'):continue
        if line[0].isspace() or continued:
            if key is None:raise ValueError('Command without key at line '+str(number))
            command.append(line.strip().removesuffix('\\').rstrip());continued=line.rstrip().endswith('\\')
        else:
            flush();key=line.strip();start=number;continued=False
    flush();return groups


def literal_lua_bindings(text):
    """Inspect the flat distributed bind block, rejecting hidden dynamic binds."""
    rows=[]
    for line in text.splitlines():
        if line.lstrip().startswith('--'):continue
        if 'hl.bind(' not in line:continue
        m=re.match(r'\s*hl\.bind\(("(?:[^"\\]|\\.)*"),\s*(.*)\)\s*$',line)
        if not m:raise ValueError('A binding is not a literal audited record: '+line)
        key=json.loads(m[1]);action=m[2]
        desc=re.search(r'description\s*=\s*("(?:[^"\\]|\\.)*")',action)
        rows.append(dict(key=key_id(key),action=action,description=json.loads(desc[1]) if desc else ''))
    return rows



def private_capture_fragment(text, home):
    """Preserve literal personal capture arguments outside the distributed repo."""
    wanted={'Print','SUPER + SHIFT + S','SUPER + SHIFT + Q','SUPER + SHIFT + A'}
    lines=['-- BEGIN WYSUN PRIVATE CAPTURE SHORTCUTS'];found=[]
    for row in parse(text):
        if row['key'] not in wanted:continue
        args=shlex.split(row['command'])
        name=Path(args.pop(0)).name
        if name=='wysun':
            if not args or args.pop(0)!='screenshot':raise ValueError('Unknown private capture command')
        elif name not in ('wybie-screenshot','wysun-screenshot'):raise ValueError('Unknown capture executable')
        expanded=[]
        for arg in args:
            if any(c in arg for c in ('\0','\n','\r')):raise ValueError('Invalid capture argument')
            if arg.startswith('${HOME}'):arg=str(home)+arg[7:]
            elif arg.startswith('$HOME'):arg=str(home)+arg[5:]
            elif arg=='~' or arg.startswith('~/'):arg=str(home)+arg[1:]
            expanded.append(arg)
        command=' '.join(shlex.quote(a) for a in ['wysun','screenshot',*expanded])
        key=json.dumps(row['key']);lines.extend(['hl.unbind('+key+')','hl.bind('+key+', hl.dsp.exec_cmd('+json.dumps(command,ensure_ascii=False)+'), {description='+json.dumps('Wysun | private | Captura con argumentos personales preservados')+'})'])
        found.append(dict(key=row['key'],argv=expanded))
    if {r['key'] for r in found}!=wanted:raise ValueError('Incomplete baseline capture shortcuts')
    lines.append('-- END WYSUN PRIVATE CAPTURE SHORTCUTS')
    return '\n'.join(lines)+'\n',found


def duplicates(rows):
    return {k:n for k,n in Counter(row['key'] for row in rows).items() if n>1}


def source_inventory(path):
    data=Path(path).read_bytes();rows=parse(data.decode())
    return dict(sha256=hashlib.sha256(data).hexdigest(),count=len(rows),duplicates=duplicates(rows),bindings=rows)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('sxhkd',type=Path);args=p.parse_args()
    print(json.dumps(source_inventory(args.sxhkd),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
