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

const COLORS = ["#0088FE", "#00C49F", "#FFBB28", "#FF8042", "#8884D8"];

function GridStats({ gridId }) {
  const [stats, setStats] = useState(null);
  const [distribution, setDistribution] = useState(null);
  const [timeDistribution, setTimeDistribution] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);
        const [statsData, distData, timeDistData] = await Promise.all([
          statisticsAPI.getGridStatistics(gridId),
          statisticsAPI.getScoreDistribution(gridId),
          statisticsAPI.getCompletionTimeDistribution(gridId),
        ]);
        setStats(statsData);
        setDistribution(distData);
        setTimeDistribution(timeDistData);
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

  // Format time distribution bins for display (convert seconds to minutes)
  const timeDistributionData =
    timeDistribution?.bins?.map((bin) => {
      const startMin = Math.floor(bin.start / 60);
      const endMin = Math.floor(bin.end / 60);
      return {
        range: `${startMin}-${endMin} min`,
        count: bin.count,
        start: bin.start,
        end: bin.end,
        minutes: (bin.start + bin.end) / 120, // midpoint in minutes for tooltip
      };
    }) || [];

  const completionData = [
    { name: "Complété", value: stats.completionRate || 0 },
    { name: "Non complété", value: 100 - (stats.completionRate || 0) },
  ];

  const jokerData = [
    { name: "Avec joker", value: stats.jokerUsage?.totalUsed || 0 },
    {
      name: "Sans joker",
      value: (stats.totalSubmissions || 0) - (stats.jokerUsage?.totalUsed || 0),
    },
  ];

  // Words found data for pie chart
  const wordsFoundData = [
    {
      name: "Mots trouvés",
      value: Math.round(stats.wordsStats?.averageFound || 0)
    },
    {
      name: "Mots restants",
      value: (stats.wordsStats?.totalWords || 0) - Math.round(stats.wordsStats?.averageFound || 0)
    },
  ];

  // Format distribution bins for display
  const distributionData =
    distribution?.bins?.map((bin) => ({
      range: `${Math.round(bin.start)}-${Math.round(bin.end)}`,
      count: bin.count,
      start: bin.start,
      end: bin.end,
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
        {distributionData.length > 0 && (
          <div className="chart-container">
            <h3>Distribution des Scores</h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={distributionData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  dataKey="range"
                  angle={-45}
                  textAnchor="end"
                  height={80}
                />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="count" fill="#8884d8" name="Nombre de joueurs" />
              </BarChart>
            </ResponsiveContainer>
            {distribution && (
              <div style={{
                display: "flex",
                gap: "1rem",
                justifyContent: "center",
                marginTop: "1rem",
                fontSize: "0.85rem",
                color: "#555",
                backgroundColor: "#f8f9fa",
                padding: "0.75rem 1rem",
                borderRadius: "8px",
                boxShadow: "0 2px 4px rgba(0,0,0,0.1)",
                border: "1px solid #e0e0e0"
              }}>
                <span>
                  <strong>Min:</strong> {Math.round(distribution.min)}
                </span>
                <span>
                  <strong>Moyenne:</strong> {Math.round(distribution.mean)}
                </span>
                <span>
                  <strong>Médiane:</strong> {Math.round(stats.scores?.median || 0)}
                </span>
                <span>
                  <strong>Max:</strong> {Math.round(distribution.max)}
                </span>
              </div>
            )}
          </div>
        )}

        {timeDistributionData.length > 0 && (
          <div className="chart-container">
            <h3>Distribution des Temps de Complétion</h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={timeDistributionData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  dataKey="range"
                  angle={-45}
                  textAnchor="end"
                  height={80}
                />
                <YAxis />
                <Tooltip
                  formatter={(value, name) => {
                    if (name === "count") return [value, "Nombre de joueurs"];
                    return [value, name];
                  }}
                />
                <Legend />
                <Bar dataKey="count" fill="#82ca9d" name="Nombre de joueurs" />
              </BarChart>
            </ResponsiveContainer>
            {timeDistribution && (
              <div style={{
                display: "flex",
                gap: "1rem",
                justifyContent: "center",
                marginTop: "1rem",
                fontSize: "0.85rem",
                color: "#555",
                backgroundColor: "#f8f9fa",
                padding: "0.75rem 1rem",
                borderRadius: "8px",
                boxShadow: "0 2px 4px rgba(0,0,0,0.1)",
                border: "1px solid #e0e0e0"
              }}>
                <span>
                  <strong>Min:</strong> {Math.floor(timeDistribution.min / 60)}m {timeDistribution.min % 60}s
                </span>
                <span>
                  <strong>Moyenne:</strong> {Math.floor(timeDistribution.mean / 60)}m {Math.round(timeDistribution.mean % 60)}s
                </span>
                <span>
                  <strong>Médiane:</strong> {Math.floor(timeDistribution.median / 60)}m {Math.round(timeDistribution.median % 60)}s
                </span>
                <span>
                  <strong>Max:</strong> {Math.floor(timeDistribution.max / 60)}m {timeDistribution.max % 60}s
                </span>
              </div>
            )}
          </div>
        )}

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
                  <Cell
                    key={`cell-${index}`}
                    fill={COLORS[index % COLORS.length]}
                  />
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

        <div className="chart-container">
          <h3>Mots Trouvés en Moyenne</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={wordsFoundData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, value }) => `${name}: ${value}`}
                outerRadius={80}
                fill="#8884d8"
                dataKey="value"
              >
                {wordsFoundData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index === 0 ? 1 : 4]} />
                ))}
              </Pie>
              <Tooltip
                formatter={(value, name) => {
                  if (name === "Mots trouvés" || name === "Mots restants") {
                    const total = stats.wordsStats?.totalWords || 0;
                    const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
                    return [`${value} (${percentage}%)`, name];
                  }
                  return [value, name];
                }}
              />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

export default GridStats;
