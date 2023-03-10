from pathlib import Path


_secrets_dir = Path('/var/openfaas/secrets')


def get_secrets(names=None):
    if names is None:
        names = _secrets_dir.iterdir()
    secrets = {}
    for file_name in names:
        with open(_secrets_dir / file_name) as f:
            secrets[file_name] = f.read().strip()
    return secrets
