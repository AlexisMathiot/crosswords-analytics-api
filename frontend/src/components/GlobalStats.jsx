import { useState, useEffect } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { statisticsAPI } from "../services/api";

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
    </div>
  );
}

export default GlobalStats;
