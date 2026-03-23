import { useTranslation } from 'react-i18next';
import { getLocaleForLanguage } from '../../utils/locale';
import './TaxCalendar.css';

interface TaxDeadline {
  id: number;
  title: string;
  date: string;
  description: string;
  isOverdue: boolean;
}

interface TaxCalendarProps {
  deadlines: TaxDeadline[];
}

const TaxCalendar = ({ deadlines }: TaxCalendarProps) => {
  const { t, i18n } = useTranslation();

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return new Intl.DateTimeFormat(getLocaleForLanguage(i18n.language), {
      day: '2-digit',
      month: 'long',
      year: 'numeric',
    }).format(date);
  };

  const getDaysUntil = (dateString: string) => {
    const date = new Date(dateString);
    const today = new Date();
    const diffTime = date.getTime() - today.getTime();
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    return diffDays;
  };

  const getUrgencyClass = (deadline: TaxDeadline) => {
    if (deadline.isOverdue) return 'overdue';
    const daysUntil = getDaysUntil(deadline.date);
    if (daysUntil <= 7) return 'urgent';
    if (daysUntil <= 30) return 'soon';
    return 'normal';
  };

  const getUrgencyLabel = (deadline: TaxDeadline) => {
    if (deadline.isOverdue) return t('dashboard.overdue');
    const daysUntil = getDaysUntil(deadline.date);
    if (daysUntil === 0) return t('dashboard.today');
    if (daysUntil === 1) return t('dashboard.tomorrow');
    if (daysUntil <= 7) return t('dashboard.thisWeek');
    if (daysUntil <= 30) return t('dashboard.thisMonth');
    return '';
  };

  // Sort deadlines by date
  const sortedDeadlines = [...deadlines].sort(
    (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
  );

  // Show only upcoming deadlines (next 90 days) and overdue
  const upcomingDeadlines = sortedDeadlines.filter((deadline) => {
    const daysUntil = getDaysUntil(deadline.date);
    return deadline.isOverdue || daysUntil <= 90;
  });

  if (upcomingDeadlines.length === 0) {
    return (
      <div className="tax-calendar">
        <h3>{t('dashboard.taxCalendar')}</h3>
        <div className="no-deadlines">
          <p>âœ… {t('dashboard.noUpcomingDeadlines')}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="tax-calendar">
      <div className="calendar-header">
        <h3>{t('dashboard.taxCalendar')}</h3>
        <span className="deadlines-count">
          {upcomingDeadlines.length} {t('dashboard.upcoming')}
        </span>
      </div>

      <div className="deadlines-list">
        {upcomingDeadlines.map((deadline) => (
          <div
            key={deadline.id}
            className={`deadline-item ${getUrgencyClass(deadline)}`}
          >
            <div className="deadline-date">
              <div className="date-day">
                {new Date(deadline.date).getDate()}
              </div>
              <div className="date-month">
                {new Intl.DateTimeFormat(getLocaleForLanguage(i18n.language), { month: 'short' }).format(
                  new Date(deadline.date)
                )}
              </div>
            </div>

            <div className="deadline-content">
              <div className="deadline-title-row">
                <h4>{deadline.title}</h4>
                {getUrgencyLabel(deadline) && (
                  <span className="urgency-badge">
                    {getUrgencyLabel(deadline)}
                  </span>
                )}
              </div>
              <p className="deadline-description">{deadline.description}</p>
              <p className="deadline-full-date">{formatDate(deadline.date)}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default TaxCalendar;
