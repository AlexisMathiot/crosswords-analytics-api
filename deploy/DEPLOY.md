# Déploiement sur le VPS OVH (v2)

L'app analytics tourne en Docker sur le VPS, à côté de la stack prod de
`crosswords-api`. Elle rejoint deux réseaux Docker existants :

- `prod_internal` — pour atteindre PostgreSQL via `prod_postgres:5432` (jamais exposé publiquement)
- `web` — pour être reverse-proxyée par le Caddy partagé

## Première installation

Convention VPS : `/opt/onsengrilleune/<env>/...` (comme crosswords-api).

```bash
# 1. Cloner le repo sur le VPS
git clone -b main git@github.com:AlexisMathiot/crosswords-analytics-api.git /opt/onsengrilleune/prod/crosswords-analytics-api
cd /opt/onsengrilleune/prod/crosswords-analytics-api

# 2. Créer .env.local (gitignoré) avec la vraie config
cat > .env.local <<'EOF'
DATABASE_URL=postgresql+psycopg://crossword:MOT_DE_PASSE_PROD@prod_postgres:5432/crossword_db
DEBUG=false
CORS_ORIGINS_STR=https://crosswords-analytics-front.vercel.app,https://onsengrilleune.fr,https://www.onsengrilleune.fr
EOF

# 3. Démarrer (la stack prod de crosswords-api doit déjà tourner : réseaux prod_internal + web)
docker compose -f compose.prod.yaml up -d --build

# 4. Vérifier
curl http://127.0.0.1:8082/health
```

## Exposition via Caddy

Ajouter dans `crosswords-api/caddy/Caddyfile` :

```
# --- Analytics API (migrée depuis o2switch) ---
analytics.onsengrilleune.fr {
    reverse_proxy prod_analytics:8000
}
```

⚠️ Ne recharger Caddy qu'**après** avoir fait pointer le DNS de
`analytics.onsengrilleune.fr` vers le VPS (sinon Caddy boucle sur l'émission du
certificat Let's Encrypt). Puis :

```bash
docker exec caddy caddy reload --config /etc/caddy/Caddyfile
```

## Bascule DNS depuis o2switch

1. Déployer la stack sur le VPS et vérifier `curl http://127.0.0.1:8082/health`
2. Modifier le DNS : `analytics.onsengrilleune.fr` → IP du VPS
3. Recharger Caddy (certificat émis automatiquement)
4. Une fois la bascule validée : supprimer l'application Python dans cPanel o2switch
   (`passenger_wsgi.py` peut alors être retiré du repo)

## Déploiements suivants

```bash
./deploy/deploy-prod.sh   # pull main + rebuild + restart
```

## Recommandation : utilisateur Postgres en lecture seule

L'app est strictement read-only ; idéalement, créer un rôle dédié :

```sql
CREATE ROLE analytics_ro LOGIN PASSWORD '...';
GRANT CONNECT ON DATABASE crossword_db TO analytics_ro;
GRANT USAGE ON SCHEMA public TO analytics_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO analytics_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO analytics_ro;
```

puis utiliser `analytics_ro` dans `DATABASE_URL`.
