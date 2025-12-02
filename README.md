# Crosswords Analytics API

Service d'analyse et de statistiques pour l'application Crosswords, construit avec FastAPI et optimisé pour les calculs statistiques avec Pandas/NumPy.

## Stack Technique

- **Python 3.14.0** - Dernière version stable
- **FastAPI 0.122.0** - Framework web moderne et rapide
- **PostgreSQL 18.1** - Base de données (partagée avec l'API Symfony)
- **Redis 8.2.2** - Cache pour optimiser les performances
- **Pandas 2.3.3** - Analyse de données haute performance
- **NumPy 2.2.2** - Calculs numériques optimisés
- **SQLAlchemy 2.0.40** - ORM Python
- **Devbox** - Environnement de développement reproductible

## Fonctionnalités

### Endpoints Statistiques

- `GET /api/v1/statistics/grid/{grid_id}` - Statistiques complètes d'une grille
- `GET /api/v1/statistics/grid/{grid_id}/leaderboard` - Classement des joueurs
- `GET /api/v1/statistics/grid/{grid_id}/distribution` - Distribution des scores (histogramme)
- `GET /api/v1/statistics/global` - Statistiques globales de la plateforme

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

## Installation

### Avec Devbox (Recommandé)

1. **Installer Devbox** (si pas déjà fait) :
```bash
curl -fsSL https://get.jetify.com/devbox | bash
```

2. **Cloner et initialiser le projet** :
```bash
cd /home/alexis/Projects/crosswords-analytics-api
devbox shell
```

Devbox va automatiquement :
- Installer Python 3.14.0, PostgreSQL 18.1, Redis 8.2.2
- Mettre à jour pip
- Installer toutes les dépendances Python

3. **Configurer les variables d'environnement** :
```bash
cp .env.example .env
# Éditer .env avec vos configurations
```

### Sans Devbox (Virtual Environment)

```bash
python3.14 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Utilisation

### Démarrer le serveur

**Avec Devbox :**
```bash
devbox run dev
# ou
devbox shell
uvicorn app.main:app --reload
```

**Sans Devbox :**
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
│   ├── models.py            # Modèles SQLAlchemy
│   ├── routers/
│   │   ├── __init__.py
│   │   └── statistics.py    # Routes statistiques
│   └── services/
│       ├── __init__.py
│       └── statistics_service.py  # Calculs avec Pandas/NumPy
├── devbox.json              # Configuration Devbox
├── requirements.txt         # Dépendances Python
├── .env.example            # Template variables d'environnement
├── .gitignore
└── README.md
```

## Configuration

### Variables d'Environnement

Voir `.env.example` pour la liste complète. Les principales :

- `DATABASE_URL` - URL de connexion PostgreSQL
- `REDIS_HOST`, `REDIS_PORT` - Configuration Redis
- `REDIS_TTL` - Durée de cache (secondes)
- `CORS_ORIGINS` - Origines autorisées pour CORS
- `DEBUG` - Mode debug (true/false)

### Base de Données

L'API se connecte à la même base de données PostgreSQL que l'API Symfony (`crosswords_db`).

Les modèles SQLAlchemy mappent les tables existantes :
- `user` - Utilisateurs
- `grid` - Grilles
- `submission` - Soumissions
- `progression` - Progressions
- `clue` - Indices
- `word` - Mots

**Aucune migration nécessaire** - lecture seule sur la base existante.

## Développement

### Tests

```bash
devbox run test
# ou
pytest -v
```

### Linting et Formatage

```bash
devbox run lint    # Vérifier le code avec Ruff
devbox run format  # Formater le code avec Ruff
```

### Scripts Devbox

Définis dans `devbox.json` :
- `devbox run dev` - Démarrer en mode développement
- `devbox run test` - Lancer les tests
- `devbox run lint` - Linter le code
- `devbox run format` - Formater le code

## Performance

### Optimisations

1. **Pandas/NumPy** - Calculs vectorisés 10-50x plus rapides que Python pur
2. **Cache Redis** - TTL de 10 minutes par défaut pour les statistiques
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
const response = await fetch('http://localhost:8000/api/v1/statistics/grid/10');
const stats = await response.json();

console.log(stats.totalPlayers);      // 2351
console.log(stats.completionRate);     // 66.3
console.log(stats.scores.median);      // 396.1
```

### API Symfony

L'API Symfony peut appeler ce service pour obtenir des statistiques sans surcharger sa propre logique.

## Roadmap

- [ ] Tests unitaires et d'intégration
- [ ] Cache Redis implémenté
- [ ] Analyse temporelle (soumissions par heure/jour)
- [ ] Analyse de mots (taux de succès par mot)
- [ ] Heatmap de difficulté
- [ ] Métriques comportementales avancées
- [ ] Endpoints d'administration
- [ ] Documentation OpenAPI enrichie
- [ ] Monitoring et métriques (Prometheus)

## Licence

Propriétaire - Crosswords V1

## Contact

Pour toute question, voir le projet principal Symfony.
