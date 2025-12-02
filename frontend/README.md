# Crosswords Analytics Dashboard

Dashboard React pour visualiser les statistiques et analytics de l'application Crosswords.

## Stack Technique

- **React 18** - Library UI moderne
- **Vite** - Build tool rapide
- **Recharts** - Library de graphiques pour React
- **Axios** - Client HTTP pour l'API

## Fonctionnalités

### Statistiques Globales
- Total utilisateurs, grilles, et soumissions
- Moyenne de soumissions par grille
- Graphique de vue d'ensemble

### Statistiques par Grille
- Nombre de joueurs et soumissions
- Taux de complétion
- Distribution des scores (min, max, moyenne, médiane)
- Temps de complétion
- Utilisation du joker
- Histogramme détaillé des scores

### Classement (Leaderboard)
- Top 50 joueurs par grille
- Affichage des médailles pour le top 3
- Score, temps, et détails de complétion
- Tri par rang

## Installation

```bash
npm install
```

## Configuration

Le fichier `.env` a déjà été créé avec la configuration par défaut :

```env
VITE_API_URL=http://localhost:8000
```

Modifiez cette URL si votre API FastAPI est sur un autre port.

## Développement

```bash
npm run dev
```

L'application sera disponible sur `http://localhost:5173`

## Build Production

```bash
npm run build
```

Les fichiers de production seront générés dans le dossier `dist/`

## Preview Production

```bash
npm run preview
```

## Structure du Projet

```
frontend/
├── src/
│   ├── components/
│   │   ├── GlobalStats.jsx      # Statistiques globales
│   │   ├── GridStats.jsx        # Statistiques par grille
│   │   └── Leaderboard.jsx      # Classement
│   ├── services/
│   │   └── api.js               # Service API (Axios)
│   ├── App.jsx                  # Composant principal
│   ├── App.css                  # Styles de l'app
│   ├── index.css                # Styles globaux
│   └── main.jsx                 # Point d'entrée
├── .env                         # Variables d'environnement
├── package.json
└── vite.config.js
```

## Composants

### GlobalStats
Affiche les statistiques globales de la plateforme avec un graphique en barres.

### GridStats
Affiche les statistiques détaillées d'une grille spécifique avec :
- Cards de résumé
- Graphique en barres pour les scores
- Graphique en ligne pour les temps
- Graphiques en camembert pour la complétion et les jokers
- Histogramme de distribution des scores

### Leaderboard
Affiche le classement des joueurs pour une grille avec :
- Médailles pour le top 3
- Tableau avec pseudo, score, temps, joker, complétion, date

## API

Le frontend communique avec l'API FastAPI via les endpoints suivants :

- `GET /api/v1/statistics/global` - Statistiques globales
- `GET /api/v1/statistics/grid/{grid_id}` - Statistiques d'une grille
- `GET /api/v1/statistics/grid/{grid_id}/leaderboard` - Classement
- `GET /api/v1/statistics/grid/{grid_id}/distribution` - Distribution des scores

## Démarrage Rapide

1. Assurez-vous que l'API FastAPI est démarrée sur `http://localhost:8000`
2. Installez les dépendances : `npm install`
3. Lancez le serveur de développement : `npm run dev`
4. Ouvrez votre navigateur sur `http://localhost:5173`

## Personnalisation

### Couleurs
Les couleurs principales peuvent être modifiées dans `App.css` :
- Primaire : `#667eea`
- Secondaire : `#764ba2`

### Graphiques
Les graphiques Recharts peuvent être personnalisés dans les composants respectifs.
