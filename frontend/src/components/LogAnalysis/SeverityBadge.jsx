import React, { useState } from 'react';
import { ShieldAlert, AlertTriangle, AlertCircle, ShieldCheck, HelpCircle } from 'lucide-react';

const getConsistentScore = (severityName, rawScore) => {
  const s = String(severityName || '').toLowerCase();
  const num = Number(rawScore);
  if (s === 'critical') return num >= 90 ? num : 95;
  if (s === 'high') return (num >= 70 && num < 90) ? num : 75;
  if (s === 'medium') return (num >= 40 && num < 70) ? num : 50;
  if (s === 'low') return (num >= 10 && num < 40) ? num : 20;
  return num || 20;
};

export default function SeverityBadge({ severity = 'low', score, reasons = [], showScore = false }) {
  const [showTooltip, setShowTooltip] = useState(false);
  const sev = (severity || 'low').toLowerCase();
  const displayScore = getConsistentScore(sev, score);

  const getIcon = () => {
    switch (sev) {
      case 'critical':
        return <ShieldAlert size={12} className="sev-icon" />;
      case 'high':
        return <AlertCircle size={12} className="sev-icon" />;
      case 'medium':
        return <AlertTriangle size={12} className="sev-icon" />;
      case 'low':
      default:
        return <ShieldCheck size={12} className="sev-icon" />;
    }
  };

  const reasonsList = Array.isArray(reasons)
    ? reasons
    : typeof reasons === 'string'
    ? JSON.parse(reasons || '[]')
    : [];

  return (
    <div
      className="severity-badge-wrapper"
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      <span className={`severity-pill severity-${sev}`}>
        {getIcon()}
        <span className="severity-text">{sev.toUpperCase()}</span>
        {showScore && score !== undefined && (
          <span className="severity-score-tag">{displayScore}</span>
        )}
      </span>

      {showTooltip && (
        <div className="severity-tooltip">
          <div className="tooltip-header">
            <strong>Severity: {sev.toUpperCase()}</strong>
            <span className="tooltip-score">Score: {displayScore}/100</span>
          </div>
          {reasonsList.length > 0 ? (
            <ul className="tooltip-reasons">
              {reasonsList.map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
          ) : (
            <div className="tooltip-empty">Classified by baseline security rules</div>
          )}
        </div>
      )}
    </div>
  );
}
