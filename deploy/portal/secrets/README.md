# Secrets à générer avant le premier lancement

```bash
mkdir -p secrets
openssl rand -hex 32 > secrets/jwt_secret.txt
openssl rand -hex 32 > secrets/session_secret.txt
openssl rand -hex 16 > secrets/storage_password.txt
```

Ne jamais committer le dossier `secrets/` (ajouter à .gitignore local de la VM).
