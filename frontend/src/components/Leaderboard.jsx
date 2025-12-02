import { useState, useEffect } from 'react';
import { statisticsAPI } from '../services/api';

function Leaderboard({ gridId, limit = 50 }) {
  const [leaderboard, setLeaderboard] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchLeaderboard = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await statisticsAPI.getLeaderboard(gridId, limit);
        setLeaderboard(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    if (gridId) {
      fetchLeaderboard();
    }
  }, [gridId, limit]);

  const formatTime = (seconds) => {
    if (!seconds) return 'N/A';
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);

    if (hours > 0) {
      return `${hours}h ${minutes}m ${secs}s`;
    } else if (minutes > 0) {
      return `${minutes}m ${secs}s`;
    } else {
      return `${secs}s`;
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleDateString('fr-FR', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getMedalEmoji = (rank) => {
    switch (rank) {
      case 1:
        return '🥇';
      case 2:
        return '🥈';
      case 3:
        return '🥉';
      default:
        return '';
    }
  };

  if (loading) return <div className="loading">Chargement du classement...</div>;
  if (error) return <div className="error">Erreur: {error}</div>;
  if (!leaderboard || leaderboard.length === 0) {
    return <div className="no-data">Aucune donnée de classement disponible.</div>;
  }

  return (
    <div className="leaderboard">
      <h2>Classement - Grille #{gridId}</h2>
      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th>Rang</th>
              <th>Pseudo</th>
              <th>Score</th>
              <th>Temps</th>
              <th>Joker</th>
              <th>Complété</th>
              <th>Date</th>
            </tr>
          </thead>
          <tbody>
            {leaderboard.map((entry, index) => (
              <tr key={`${entry.rank}-${index}`} className={entry.rank <= 3 ? 'top-rank' : ''}>
                <td>
                  {getMedalEmoji(entry.rank)} {entry.rank}
                </td>
                <td className="pseudo">{entry.pseudo}</td>
                <td className="score">{entry.finalScore?.toFixed(1) || 'N/A'}</td>
                <td>{formatTime(entry.completionTime)}</td>
                <td>{entry.jokerUsed ? '✓' : '✗'}</td>
                <td>{entry.isCompleted ? '✓' : '✗'}</td>
                <td className="date">{formatDate(entry.submittedAt)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default Leaderboard;
