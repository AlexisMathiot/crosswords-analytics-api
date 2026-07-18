# Crosswords Analytics API

Service d'analyse et de statistiques pour l'application Crosswords (onsengrilleune.fr), construit avec FastAPI et optimisé pour les calculs statistiques avec Pandas/NumPy.

## Stack Technique

- **Python 3.13** - Image Docker `python:3.13-slim`
- **FastAPI 0.122.0** - Framework web moderne et rapide
- **PostgreSQL 18** - Base de données v2 (partagée avec l'API Symfony, VPS OVH)
- **psycopg 3** - Driver PostgreSQL
- **Redis 8** - Cache pour optimiser les performances (roadmap)
- **Pandas 2.3.3** - Analyse de données haute performance
- **NumPy 2.2.2** - Calculs numériques optimisés
- **SQLAlchemy 2.0.40** - ORM Python
- **Docker Compose** - Déploiement sur le VPS OVH, derrière le Caddy partagé

## Fonctionnalités

### Endpoints Statistiques

- `GET /api/v1/statistics/grids?type=` - Liste des grilles disponibles (filtre optionnel par type : weekly, izipizi, duel)
- `GET /api/v1/statistics/grid/{grid_id}` - Statistiques complètes d'une grille
- `GET /api/v1/statistics/grid/{grid_id}/leaderboard` - Classement des joueurs
- `GET /api/v1/statistics/grid/{grid_id}/distribution` - Distribution des scores (histogramme)
- `GET /api/v1/statistics/grid/{grid_id}/completion-time-distribution` - Distribution des temps
- `GET /api/v1/statistics/grid/{grid_id}/temporal` - Analyse temporelle des soumissions
- `GET /api/v1/statistics/users/registrations` - Inscriptions par semaine/mois
- `GET /api/v1/statistics/users/activity` - Activité, rétention et utilisateurs réguliers
- `GET /api/v1/statistics/global` - Statistiques globales de la plateforme
- `GET /api/v1/statistics/types` - Statistiques agrégées par type de grille (weekly, izipizi, duel)
- `GET /api/v1/statistics/duels/overview` - Vue d'ensemble des duels (soumissions, matchs, résultats, Elo)
- `GET /api/v1/statistics/duels/leaderboard?limit=50` - Classement Elo (minimum 5 duels joués)
- `GET /api/v1/statistics/premium` - Statistiques d'abonnement premium (statuts, remboursements estimés, timeline)

### Métriques Calculées

**Par Grille :**
- Nombre total de joueurs et soumissions
- Taux de complétion
- Statistiques de scores (min, max, moyenne, médiane, percentiles)
- Statistiques de temps de complétion
- Analyse d'utilisation du joker
- Distribution des mots trouvés

**Globales :**
- Nombre total d'utilisateurs
- Nombre de grilles publiées
- Nombre total de soumissions
- Moyenne de soumissions par grille

## Installation (développement)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

cp .env.example .env
# Éditer .env — en local, pointer sur le Postgres de la stack Docker crosswords-api :
# DATABASE_URL=postgresql+psycopg://crossword:password@localhost:5432/crossword_db
```

## Utilisation

### Démarrer le serveur

```bash
source .venv/bin/activate
uvicorn app.main:app --reload
```

Le serveur démarre sur `http://localhost:8000`

### Documentation API

- **Swagger UI** : http://localhost:8000/docs
- **ReDoc** : http://localhost:8000/redoc
- **Health Check** : http://localhost:8000/health

### Exemples d'utilisation

```bash
# Statistiques d'une grille
curl http://localhost:8000/api/v1/statistics/grid/10

# Classement (top 50)
curl http://localhost:8000/api/v1/statistics/grid/10/leaderboard?limit=50

# Distribution des scores
curl http://localhost:8000/api/v1/statistics/grid/10/distribution

# Statistiques globales
curl http://localhost:8000/api/v1/statistics/global
```

## Structure du Projet

```
crosswords-analytics-api/
├── app/
│   ├── __init__.py
│   ├── main.py              # Application FastAPI principale
│   ├── config.py            # Configuration (Pydantic Settings)
│   ├── database.py          # Connexion SQLAlchemy
│   ├── models.py            # Modèles SQLAlchemy (schéma Postgres v2)
│   ├── routers/
│   │   ├── __init__.py
│   │   └── statistics.py    # Routes statistiques
│   └── services/
│       ├── __init__.py
│       └── statistics_service.py  # Calculs avec Pandas/NumPy
├── deploy/
│   ├── DEPLOY.md            # Guide de déploiement VPS
│   └── deploy-prod.sh       # Script de déploiement
├── Dockerfile
├── compose.prod.yaml        # Stack prod (réseaux prod_internal + web)
├── requirements.txt         # Dépendances Python
├── .env.example             # Template variables d'environnement
├── .gitignore
└── README.md
```

## Configuration

### Variables d'Environnement

Voir `.env.example` pour la liste complète. Les principales :

- `DATABASE_URL` - URL de connexion PostgreSQL (`postgresql+psycopg://...`)
- `REDIS_HOST`, `REDIS_PORT` - Configuration Redis
- `REDIS_TTL` - Durée de cache (secondes)
- `CORS_ORIGINS_STR` - Origines autorisées pour CORS (séparées par des virgules)
- `DEBUG` - Mode debug (true/false)

### Base de Données

L'API se connecte à la même base PostgreSQL que l'API Symfony v2 (`crossword_db`).

Les modèles SQLAlchemy mappent les tables existantes :
- `users` - Utilisateurs (UUID)
- `grids` - Grilles
- `submission` - Soumissions
- `progression` - Progressions
- `clues` - Indices
- `words` - Mots

**Aucune migration nécessaire** - lecture seule sur la base existante (les migrations sont gérées par Doctrine côté Symfony).

## Déploiement

L'app est déployée en Docker sur le VPS OVH, à côté de la stack `crosswords-api` :
elle rejoint le réseau `prod_internal` pour atteindre `prod_postgres:5432` et le
réseau `web` pour être exposée par Caddy sur `analytics.onsengrilleune.fr`.

Voir **[deploy/DEPLOY.md](deploy/DEPLOY.md)** pour la première installation et la
bascule DNS depuis o2switch. Ensuite :

```bash
./deploy/deploy-prod.sh   # pull main + rebuild + restart
```

## Développement

### Tests

```bash
pytest -v
```

### Linting et Formatage

```bash
ruff check .    # Vérifier le code
ruff format .   # Formater le code
```

## Performance

### Optimisations

1. **Pandas/NumPy** - Calculs vectorisés 10-50x plus rapides que Python pur
2. **Cache Redis** - TTL de 10 minutes par défaut pour les statistiques (roadmap)
3. **Connection Pooling** - SQLAlchemy pool (10 connexions + 20 overflow)
4. **Async FastAPI** - Endpoints asynchrones pour meilleure concurrence

### Benchmarks Estimés

- Calcul statistiques grille (2000 soumissions) : ~50-100ms
- Génération leaderboard (1000 entrées) : ~20-30ms
- Distribution scores : ~10-20ms

## Intégration

### Frontend Next.js

```typescript
// Exemple d'utilisation
const response = await fetch('https://analytics.onsengrilleune.fr/api/v1/statistics/grid/10');
const stats = await response.json();

console.log(stats.totalPlayers);      // 2351
console.log(stats.completionRate);     // 66.3
console.log(stats.scores.median);      // 396.1
```

### API Symfony

L'API Symfony peut appeler ce service pour obtenir des statistiques sans surcharger sa propre logique.

## Roadmap

- [x] Statistiques duels / ELO (nouvelles tables v2)
- [x] Statistiques par type de grille
- [x] Statistiques abonnements premium
- [ ] Tests unitaires et d'intégration (premiers tests sur les fonctions pures)
- [ ] Cache Redis implémenté
- [ ] Analyse de mots (taux de succès par mot)
- [ ] Heatmap de difficulté
- [ ] Métriques comportementales avancées
- [ ] Endpoints d'administration
- [ ] Documentation OpenAPI enrichie
- [ ] Monitoring et métriques (Prometheus)

## Licence

Propriétaire - Crosswords

## Contact

Pour toute question, voir le projet principal Symfony.
