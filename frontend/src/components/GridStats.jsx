import { useState, useEffect } from 'react';
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { statisticsAPI } from '../services/api';

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8'];

function GridStats({ gridId }) {
  const [stats, setStats] = useState(null);
  const [distribution, setDistribution] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);
        const [statsData, distData] = await Promise.all([
          statisticsAPI.getGridStatistics(gridId),
          statisticsAPI.getScoreDistribution(gridId),
        ]);
        setStats(statsData);
        setDistribution(distData);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    if (gridId) {
      fetchData();
    }
  }, [gridId]);

  if (loading) return <div className="loading">Chargement...</div>;
  if (error) return <div className="error">Erreur: {error}</div>;
  if (!stats) return null;

  const scoreData = [
    { name: 'Min', value: stats.scores?.min || 0 },
    { name: 'Moyenne', value: stats.scores?.mean || 0 },
    { name: 'Médiane', value: stats.scores?.median || 0 },
    { name: 'Max', value: stats.scores?.max || 0 },
  ];

  const timingData = [
    { name: 'Min', seconds: stats.timing?.min || 0 },
    { name: 'Moyenne', seconds: stats.timing?.mean || 0 },
    { name: 'Médiane', seconds: stats.timing?.median || 0 },
    { name: 'Max', seconds: stats.timing?.max || 0 },
  ];

  const completionData = [
    { name: 'Complété', value: stats.completionRate || 0 },
    { name: 'Non complété', value: 100 - (stats.completionRate || 0) },
  ];

  const jokerData = [
    { name: 'Avec joker', value: stats.jokerUsage?.totalUsed || 0 },
    { name: 'Sans joker', value: (stats.totalSubmissions || 0) - (stats.jokerUsage?.totalUsed || 0) },
  ];

  // Format distribution bins for display
  const distributionData = distribution?.bins?.map(bin => ({
    range: `${Math.round(bin.start)}-${Math.round(bin.end)}`,
    count: bin.count,
    start: bin.start,
    end: bin.end
  })) || [];

  return (
    <div className="grid-stats">
      <h2>Statistiques de la Grille #{gridId}</h2>

      <div className="stats-summary">
        <div className="stat-card">
          <h3>Total Joueurs</h3>
          <p className="stat-value">{stats.totalPlayers}</p>
        </div>
        <div className="stat-card">
          <h3>Total Soumissions</h3>
          <p className="stat-value">{stats.totalSubmissions}</p>
        </div>
        <div className="stat-card">
          <h3>Taux de Complétion</h3>
          <p className="stat-value">{stats.completionRate?.toFixed(1)}%</p>
        </div>
      </div>

      <div className="charts-grid">
        <div className="chart-container">
          <h3>Distribution des Scores</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={scoreData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey="value" fill="#8884d8" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-container">
          <h3>Temps de Complétion (secondes)</h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={timingData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="seconds" stroke="#82ca9d" />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-container">
          <h3>Taux de Complétion</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={completionData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, value }) => `${name}: ${value.toFixed(1)}%`}
                outerRadius={80}
                fill="#8884d8"
                dataKey="value"
              >
                {completionData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-container">
          <h3>Utilisation du Joker</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={jokerData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, value }) => `${name}: ${value}`}
                outerRadius={80}
                fill="#8884d8"
                dataKey="value"
              >
                {jokerData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index + 2]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {distributionData.length > 0 && (
          <div className="chart-container full-width">
            <h3>Distribution Détaillée des Scores</h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={distributionData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="range" angle={-45} textAnchor="end" height={80} />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="count" fill="#8884d8" name="Nombre de joueurs" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  );
}

export default GridStats;
