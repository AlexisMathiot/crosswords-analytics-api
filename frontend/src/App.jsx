import { useState, useEffect } from 'react';
import GlobalStats from './components/GlobalStats';
import GridStats from './components/GridStats';
import Leaderboard from './components/Leaderboard';
import TemporalStats from './components/TemporalStats';
import { statisticsAPI } from './services/api';
import './App.css';

function App() {
  const [activeTab, setActiveTab] = useState('global');
  const [gridId, setGridId] = useState(null);
  const [availableGrids, setAvailableGrids] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchGrids = async () => {
      try {
        const grids = await statisticsAPI.getAvailableGrids();
        setAvailableGrids(grids);
        if (grids.length > 0) {
          setGridId(grids[0].id);
        }
      } catch (error) {
        console.error('Error fetching grids:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchGrids();
  }, []);

  return (
    <div className="app">
      <header className="app-header">
        <h1>Crosswords Analytics Dashboard</h1>
        <p>Tableau de bord d'analyse et statistiques</p>
      </header>

      <nav className="tabs">
        <button
          className={activeTab === 'global' ? 'active' : ''}
          onClick={() => setActiveTab('global')}
        >
          Statistiques Globales
        </button>
        <button
          className={activeTab === 'grid' ? 'active' : ''}
          onClick={() => setActiveTab('grid')}
        >
          Statistiques Grille
        </button>
        <button
          className={activeTab === 'temporal' ? 'active' : ''}
          onClick={() => setActiveTab('temporal')}
        >
          Analyse Temporelle
        </button>
        <button
          className={activeTab === 'leaderboard' ? 'active' : ''}
          onClick={() => setActiveTab('leaderboard')}
        >
          Classement
        </button>
      </nav>

      {(activeTab === 'grid' || activeTab === 'temporal' || activeTab === 'leaderboard') && !loading && (
        <div className="grid-selector">
          <label htmlFor="gridId">Grille:</label>
          <select
            id="gridId"
            value={gridId || ''}
            onChange={(e) => setGridId(parseInt(e.target.value))}
          >
            {availableGrids.map((grid) => (
              <option key={grid.id} value={grid.id}>
                Grille #{grid.id} - {grid.version}
              </option>
            ))}
          </select>
        </div>
      )}

      <main className="content">
        {loading ? (
          <div className="loading">Chargement des grilles...</div>
        ) : (
          <>
            {activeTab === 'global' && <GlobalStats />}
            {activeTab === 'grid' && gridId && <GridStats gridId={gridId} />}
            {activeTab === 'temporal' && gridId && <TemporalStats gridId={gridId} />}
            {activeTab === 'leaderboard' && gridId && <Leaderboard gridId={gridId} limit={50} />}
          </>
        )}
      </main>

      <footer className="app-footer">
        <p>Powered by FastAPI + React + Recharts</p>
      </footer>
    </div>
  );
}

export default App;
