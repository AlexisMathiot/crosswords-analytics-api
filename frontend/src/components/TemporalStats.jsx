import { useState, useEffect } from 'react';
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { statisticsAPI } from '../services/api';

function TemporalStats({ gridId }) {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await statisticsAPI.getTemporalStatistics(gridId);
        setStats(data);
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

  // Prepare data for submissions by hour
  const hourlyData = Object.entries(stats.submissionsByHour || {}).map(([hour, count]) => ({
    hour: `${hour}h`,
    hourNumber: parseInt(hour),
    count,
  }));

  // Prepare data for submissions by day of week
  const weeklyData = stats.submissionsByDayOfWeek || [];

  // Prepare data for daily timeline
  const timelineData = (stats.dailyTimeline || []).map(item => ({
    date: new Date(item.date).toLocaleDateString('fr-FR', {
      month: 'short',
      day: 'numeric'
    }),
    count: item.count,
  }));

  // Format date for display
  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('fr-FR', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="grid-stats">
      <h2>Analyse Temporelle - Grille #{gridId}</h2>

      <div className="stats-summary">
        <div className="stat-card">
          <h3>Total Soumissions</h3>
          <p className="stat-value">{stats.totalSubmissions}</p>
        </div>
        <div className="stat-card">
          <h3>Jours Actifs</h3>
          <p className="stat-value">{stats.uniqueDays}</p>
        </div>
        <div className="stat-card">
          <h3>Moyenne / Jour</h3>
          <p className="stat-value">{stats.averageSubmissionsPerDay?.toFixed(1)}</p>
        </div>
      </div>

      <div className="stats-info">
        <p>
          <strong>Première soumission:</strong> {formatDate(stats.firstSubmission)}
        </p>
        <p>
          <strong>Dernière soumission:</strong> {formatDate(stats.lastSubmission)}
        </p>
      </div>

      {stats.peakHours && stats.peakHours.length > 0 && (
        <div className="peak-hours">
          <h3>Heures de Pic</h3>
          <div className="peak-hours-list">
            {stats.peakHours.map((peak, index) => (
              <div key={index} className="peak-hour-item">
                <span className="peak-rank">#{index + 1}</span>
                <span className="peak-hour">{peak.hour}h</span>
                <span className="peak-count">{peak.count} soumissions</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="charts-grid">
        <div className="chart-container full-width">
          <h3>Soumissions par Heure de la Journée</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={hourlyData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="hour" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey="count" fill="#8884d8" name="Nombre de soumissions" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-container full-width">
          <h3>Soumissions par Jour de la Semaine</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={weeklyData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="day" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey="count" fill="#82ca9d" name="Nombre de soumissions" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {timelineData.length > 0 && (
          <div className="chart-container full-width">
            <h3>Chronologie des Soumissions</h3>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={timelineData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  dataKey="date"
                  angle={-45}
                  textAnchor="end"
                  height={80}
                  interval="preserveStartEnd"
                />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="count"
                  stroke="#ff7300"
                  strokeWidth={2}
                  name="Soumissions par jour"
                  dot={{ r: 3 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  );
}

export default TemporalStats;
