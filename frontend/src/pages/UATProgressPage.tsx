import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import './UATProgressPage.css';

interface UATProgress {
  user_id: number;
  scenarios_completed: string[];
  completion_percentage: number;
  total_time_spent_minutes: number;
  feedback_submitted: number;
  bugs_reported: number;
}

const TEST_SCENARIOS = [
  'property_registration',
  'historical_backfill',
  'transaction_linking',
  'property_metrics',
  'report_generation',
  'multi_property',
  'property_archival',
];

export const UATProgressPage: React.FC = () => {
  const { t } = useTranslation();
  const [progress, setProgress] = useState<UATProgress | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchProgress();
  }, []);

  const fetchProgress = async () => {
    try {
      const response = await fetch('/api/v1/uat/progress');
      if (response.ok) {
        const data = await response.json();
        setProgress(data);
      }
    } catch (error) {
      console.error('Error fetching UAT progress:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="loading">Loading...</div>;
  }

  if (!progress) {
    return <div className="error">Failed to load progress</div>;
  }

  const getScenarioStatus = (scenario: string) => {
    return progress.scenarios_completed.includes(scenario) ? 'completed' : 'pending';
  };

  return (
    <div className="uat-progress-page">
      <div className="page-header">
        <h1>{t('uat.progress.title')}</h1>
        <p>{t('uat.progress.subtitle')}</p>
      </div>

      <div className="progress-overview">
        <div className="progress-card">
          <div className="progress-circle">
            <svg viewBox="0 0 100 100">
              <circle
                cx="50"
                cy="50"
                r="45"
                fill="none"
                stroke="#e0e0e0"
                strokeWidth="10"
              />
              <circle
                cx="50"
                cy="50"
                r="45"
                fill="none"
                stroke="#4CAF50"
                strokeWidth="10"
                strokeDasharray={`${progress.completion_percentage * 2.827} 282.7`}
                strokeLinecap="round"
                transform="rotate(-90 50 50)"
              />
            </svg>
            <div className="progress-text">
              <span className="percentage">{progress.completion_percentage}%</span>
              <span className="label">{t('uat.progress.complete')}</span>
            </div>
          </div>
        </div>

        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-icon">✓</div>
            <div className="stat-value">{progress.scenarios_completed.length}</div>
            <div className="stat-label">{t('uat.progress.scenariosCompleted')}</div>
          </div>

          <div className="stat-card">
            <div className="stat-icon">⏱</div>
            <div className="stat-value">{Math.round(progress.total_time_spent_minutes)}</div>
            <div className="stat-label">{t('uat.progress.minutesSpent')}</div>
          </div>

          <div className="stat-card">
            <div className="stat-icon">💬</div>
            <div className="stat-value">{progress.feedback_submitted}</div>
            <div className="stat-label">{t('uat.progress.feedbackSubmitted')}</div>
          </div>

          <div className="stat-card">
            <div className="stat-icon">🐛</div>
            <div className="stat-value">{progress.bugs_reported}</div>
            <div className="stat-label">{t('uat.progress.bugsReported')}</div>
          </div>
        </div>
      </div>

      <div className="scenarios-section">
        <h2>{t('uat.progress.testScenarios')}</h2>
        <div className="scenarios-list">
          {TEST_SCENARIOS.map((scenario) => {
            const status = getScenarioStatus(scenario);
            return (
              <div key={scenario} className={`scenario-item ${status}`}>
                <div className="scenario-status">
                  {status === 'completed' ? '✓' : '○'}
                </div>
                <div className="scenario-content">
                  <h3>{t(`uat.scenarios.${scenario}.title`)}</h3>
                  <p>{t(`uat.scenarios.${scenario}.description`)}</p>
                </div>
                {status === 'completed' && (
                  <div className="scenario-badge">
                    {t('uat.progress.completed')}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div className="next-steps">
        <h2>{t('uat.progress.nextSteps')}</h2>
        <div className="next-steps-content">
          {progress.completion_percentage < 100 ? (
            <>
              <p>{t('uat.progress.continueTestingMessage')}</p>
              <ul>
                {TEST_SCENARIOS.filter(s => !progress.scenarios_completed.includes(s)).map(scenario => (
                  <li key={scenario}>{t(`uat.scenarios.${scenario}.title`)}</li>
                ))}
              </ul>
            </>
          ) : (
            <>
              <p>{t('uat.progress.allCompleteMessage')}</p>
              <p>{t('uat.progress.thankYouMessage')}</p>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
