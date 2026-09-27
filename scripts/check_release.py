#!/usr/bin/env python3
"""Conservative release-tree scan. Reports paths, lines and categories, never values."""
from pathlib import Path
import ipaddress
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
RULES = {
    'personal-path': re.compile(r'/(?:Users|home)/[A-Za-z0-9_.-]+'),
    'private-key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'credential-url': re.compile(r'https?://[^\s<>"\x27]+/mcp/[A-Za-z0-9_-]{24,}'),
    'provider-token': re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{24,})'),
    'literal-credential': re.compile(r'(?i)(?:token|secret|password)\s*[:=]\s*["\x27]?[A-Za-z0-9_-]{24,}'),
    'long-hex': re.compile(r'\b[a-fA-F0-9]{40,}\b'),
}
IP = re.compile(r'(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])')
ALLOWED_IPS = {'127.0.0.1', '0.0.0.0'}
SKIP = {'.git', '.venv', '__pycache__', '.pytest_cache'}

def findings(root):
    out=[]
    for p in sorted(root.rglob('*')):
        rel=p.relative_to(root)
        if any(x in SKIP for x in rel.parts):
            continue
        if p.is_symlink():
            out.append((str(rel),0,'symlink'));continue
        if not p.is_file():continue
        if p.name in {'.env','config.toml','.DS_Store'} or p.suffix in {'.db','.log','.pem','.key','.p12','.zip','.gz'} or p.name.endswith(('.db-wal','.db-shm')):
            out.append((str(rel),0,'private-or-generated-file'))
        try:s=p.read_text()
        except UnicodeError:
            out.append((str(rel),0,'unreviewed-binary'));continue
        for n,line in enumerate(s.splitlines(),1):
            for name,pattern in RULES.items():
                if pattern.search(line):out.append((str(rel),n,name))
            for match in IP.finditer(line):
                value=match.group()
                try:ipaddress.ip_address(value)
                except ValueError:continue
                if value not in ALLOWED_IPS:out.append((str(rel),n,'non-loopback-ip'))
    return out

if __name__=='__main__':
    found=findings(ROOT)
    for path,line,category in found:print(f'{path}:{line}: {category}')
    print(f'Release content scan: {len(found)} finding(s). Values suppressed.')
    sys.exit(bool(found))
