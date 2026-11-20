"""Create a private local configuration with a stable, random signing secret."""
from pathlib import Path
import secrets

root=Path(__file__).resolve().parents[1]
target=root/'backend'/'.env'
if target.exists():
    print('backend/.env already exists; it was left unchanged.')
else:
    template=(root/'backend'/'.env.example').read_text()
    template=template.replace('JWT_SECRET=change-me-to-a-long-random-string','JWT_SECRET='+secrets.token_hex(48))
    with target.open('x') as f:f.write(template)
    target.chmod(0o600)
    print('Created backend/.env with a random signing secret. Configure your AI provider there to enable generated content.')
