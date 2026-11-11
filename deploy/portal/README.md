# Portail d'accès (Caddy + Authelia) sur VM Proxmox

Une seule porte d'entrée HTTPS pour accServerAnalyser et accCoachAnalyser,
avec gestion des accès par personne. Les deux applis restent indépendantes.

```
Internet → box (80/443 forwardés vers la VM) → Caddy (HTTPS Let's Encrypt)
        → Authelia (login, groupes, 2FA) → appli (Remote-User)
```

## 1. Préparer la VM/LXC Proxmox
- Debian 12, IP fixe LAN (ex 192.168.1.10), Docker + compose installés
- Forward des ports 80 et 443 de la box vers 192.168.1.10

## 2. DNS
Créer chez ton registrar : `auth`, `accserver`, `acccoach` → IP publique de la box.

## 3. Déployer
```bash
cd deploy/portal
# secrets (voir secrets/README.md)
# hashs bcrypt des mots de passe dans authelia/users_database.yml
# IPs des PCs applicatifs dans le Caddyfile (192.168.1.42 / .43)
docker compose up -d
```

## 4. Ajouter un utilisateur
```bash
docker run --rm authelia/authelia:4 authelia hash-password 'NOUVEAU_MDP'
# coller le hash dans authelia/users_database.yml, puis:
docker compose restart authelia
```

## 5. Accès
- https://accserver.ton-domaine.fr → login Authelia (1 facteur) → appli
- https://acccoach.ton-domaine.fr → réservé au groupe `admins` + 2FA (TOTP)
- Révocation : retirer l'utilisateur du fichier ou de son groupe

## Notes
- Caddy obtient automatiquement les certificats Let's Encrypt (ports 80/443 ouverts)
- Les applis recoivent l'utilisateur via le header `Remote-User` (elles peuvent l'afficher)
- Ne pas exposer Authelia directement (seul Caddy y parle)
