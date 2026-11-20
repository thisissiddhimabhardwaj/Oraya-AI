"""Create a sanitized source archive, then extract and verify it in a clean directory.

Usage: python scripts/package_source.py --output /absolute/path/ORAYA.zip --verify-dir /absolute/path/empty-dir
The script never modifies source files, databases, environment secrets, or Git state.
"""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
import argparse,hashlib,json

ROOT=Path(__file__).resolve().parents[1]
EXCLUDED={'.git','.venv','venv','node_modules','__pycache__','.pytest_cache','.vite','dist','dist-ssr','storage','.tools','.opencode'}
DOCS={'IMPLEMENTATION_AUDIT.md','FEATURE_COMPLETION.md','TEST_REPORT.md','KNOWN_LIMITATIONS.md','RUN_INSTRUCTIONS.md'}


def include(p):
    rel=p.relative_to(ROOT)
    if any(x in EXCLUDED for x in rel.parts):return False
    if p.is_symlink():return False
    if p.name.startswith('.env') and p.name!='.env.example':return False
    if p.suffix in {'.db','.sqlite','.sqlite3','.pyc','.log','.zip'} or p.name in {'.DS_Store','Thumbs.db'}:return False
    if rel.parts[0]=='docs' and p.name not in DOCS and not ('rebuild-screenshots' in rel.parts and p.name.startswith('premium-')):return False
    return True


def main():
    args=argparse.ArgumentParser();args.add_argument('--output',required=True);args.add_argument('--verify-dir',required=True);a=args.parse_args()
    output=Path(a.output).resolve();verify=Path(a.verify_dir).resolve()
    if verify.exists() and any(verify.iterdir()):raise SystemExit('Verification directory must be empty')
    if output.exists():raise SystemExit('Output archive already exists; choose a new name rather than overwrite it')
    files=sorted(p for p in ROOT.rglob('*') if p.is_file() and include(p))
    checksums={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    with ZipFile(output,'w',ZIP_DEFLATED,compresslevel=9) as z:
        for p in files:z.write(p,'ORAYA/'+str(p.relative_to(ROOT)))
        z.writestr('ORAYA/SOURCE_CHECKSUMS.json',json.dumps(checksums,indent=2)+'\n')
    verify.mkdir(parents=True,exist_ok=True)
    with ZipFile(output) as z:
        if z.testzip():raise SystemExit('ZIP CRC validation failed')
        for item in z.infolist():
            target=(verify/item.filename).resolve()
            if not target.is_relative_to(verify):raise SystemExit('Unsafe archive path')
        z.extractall(verify)
    for rel,expected in checksums.items():
        if hashlib.sha256((verify/'ORAYA'/rel).read_bytes()).hexdigest()!=expected:raise SystemExit('Extracted source checksum mismatch: '+rel)
    required=['frontend/package.json','frontend/package-lock.json','backend/requirements.txt','backend/app/main.py','backend/app/models.py','backend/app/migrations.py','backend/.env.example','frontend/.env.example','backend/tests/test_rebuild.py','README.md','docs/FEATURE_COMPLETION.md']
    if not all((verify/'ORAYA'/p).is_file() for p in required):raise SystemExit('Required source file is missing')
    print(json.dumps({'archive':str(output),'files':len(files)+1,'bytes':output.stat().st_size,'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'extracted_to':str(verify/'ORAYA'),'crc':'passed','source_checksums':'passed','required_structure':'passed'},indent=2))


if __name__=='__main__':main()
