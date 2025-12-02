import { useState, useEffect } from "react";
import {
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { statisticsAPI } from "../services/api";

const COLORS = ["#FF8042", "#00C49F"];

function GlobalStats() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchGlobalStats = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await statisticsAPI.getGlobalStatistics();
        setStats(data);
        console.log(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchGlobalStats();
  }, []);

  if (loading)
    return (
      <div className="loading">Chargement des statistiques globales...</div>
    );
  if (error) return <div className="error">Erreur: {error}</div>;
  if (!stats) return null;

  const chartData = [
    { name: "Utilisateurs", value: stats.totalUsers || 0 },
    { name: "Grilles", value: stats.totalGrids || 0 },
    { name: "Soumissions", value: stats.totalSubmissions || 0 },
  ];

  // Format grid stats for charts
  const gridsData = stats.gridStats?.map((grid) => ({
    name: `Grille ${grid.gridId}`,
    gridId: grid.gridId,
    version: grid.gridVersion,
    joueurs: grid.totalPlayers,
    completion: grid.completionRate,
    joker: grid.jokerUsageRate,
    totalWords: grid.totalWords,
    averageWordsFound: grid.averageWordsFound,
    medianTime: grid.medianCompletionTime,
    medianTimeMinutes: Math.floor(grid.medianCompletionTime / 60),
  })) || [];

  // Calculate global joker usage average
  const globalJokerRate = gridsData.length > 0
    ? gridsData.reduce((sum, grid) => sum + grid.joker, 0) / gridsData.length
    : 0;

  const jokerData = [
    { name: "Avec joker", value: Math.round(globalJokerRate * 10) / 10 },
    { name: "Sans joker", value: Math.round((100 - globalJokerRate) * 10) / 10 },
  ];

  return (
    <div className="global-stats">
      <h2>Statistiques Globales de la Plateforme</h2>

      <div className="stats-summary">
        <div className="stat-card">
          <h3>Total Utilisateurs</h3>
          <p className="stat-value">{stats.totalUsers?.toLocaleString()}</p>
        </div>
        <div className="stat-card">
          <h3>Total Grilles</h3>
          <p className="stat-value">{stats.totalGrids?.toLocaleString()}</p>
        </div>
        <div className="stat-card">
          <h3>Total Soumissions</h3>
          <p className="stat-value">
            {stats.totalSubmissions?.toLocaleString()}
          </p>
        </div>
        <div className="stat-card">
          <h3>Moyenne Soumissions/Grille</h3>
          <p className="stat-value">
            {stats.averageSubmissionsPerGrid?.toFixed(1)}
          </p>
        </div>
      </div>

      <div className="charts-grid">
        <div className="chart-container">
          <h3>Vue d'ensemble</h3>
          <ResponsiveContainer width="100%" height={400}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey="value" fill="#82ca9d" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {gridsData.length > 0 && (
          <>
            <div className="chart-container">
              <h3>Nombre de Joueurs par Grille</h3>
              <ResponsiveContainer width="100%" height={400}>
                <BarChart data={gridsData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="joueurs" fill="#8884d8" name="Joueurs" />
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="chart-container">
              <h3>Taux de Complétion par Grille (%)</h3>
              <ResponsiveContainer width="100%" height={400}>
                <BarChart data={gridsData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis domain={[0, 100]} />
                  <Tooltip
                    formatter={(value, name, props) => {
                      if (name === "Complétion %") {
                        return [
                          `${value}% (${props.payload.averageWordsFound} / ${props.payload.totalWords} mots en moyenne)`,
                          name
                        ];
                      }
                      return [value, name];
                    }}
                  />
                  <Legend />
                  <Bar dataKey="completion" fill="#00C49F" name="Complétion %" />
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="chart-container">
              <h3>Utilisation Globale du Joker</h3>
              <ResponsiveContainer width="100%" height={400}>
                <PieChart>
                  <Pie
                    data={jokerData}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={({ name, value }) => `${name}: ${value}%`}
                    outerRadius={120}
                    fill="#8884d8"
                    dataKey="value"
                  >
                    {jokerData.map((entry, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={COLORS[index % COLORS.length]}
                      />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value) => `${value}%`} />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </div>

            <div className="chart-container">
              <h3>Temps de Complétion Médian par Grille</h3>
              <ResponsiveContainer width="100%" height={400}>
                <BarChart data={gridsData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis />
                  <Tooltip
                    formatter={(value, name, props) => {
                      if (name === "Temps (min)") {
                        const seconds = props.payload.medianTime % 60;
                        return [
                          `${Math.floor(value)} min ${seconds}s`,
                          "Temps médian"
                        ];
                      }
                      return [value, name];
                    }}
                  />
                  <Legend />
                  <Bar dataKey="medianTimeMinutes" fill="#8884d8" name="Temps (min)" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default GlobalStats;
