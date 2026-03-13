import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import './PaymentEventLog.css';

interface PaymentEvent {
  id: number;
  stripe_event_id: string;
  event_type: string;
  user_id: number;
  user_email?: string;
  payload: Record<string, any>;
  processed_at: string;
  created_at: string;
}

interface Filters {
  event_type: string;
  user_email: string;
  date_from: string;
  date_to: string;
}

const PaymentEventLog: React.FC = () => {
  const { t } = useTranslation();
  const [events, setEvents] = useState<PaymentEvent[]>([]);
  const [expandedEvent, setExpandedEvent] = useState<number | null>(null);
  const [filters, setFilters] = useState<Filters>({
    event_type: '',
    user_email: '',
    date_from: '',
    date_to: ''
  });
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  useEffect(() => {
    fetchEvents();
  }, [page, filters]);

  const fetchEvents = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams({
        page: page.toString(),
        limit: '20',
        ...(filters.event_type && { event_type: filters.event_type }),
        ...(filters.user_email && { user_email: filters.user_email }),
        ...(filters.date_from && { date_from: filters.date_from }),
        ...(filters.date_to && { date_to: filters.date_to })
      });

      const response = await fetch(`/api/v1/admin/payment-events?${params}`);
      const data = await response.json();
      setEvents(data.events);
      setTotalPages(data.total_pages);
    } catch (error) {
      console.error('Failed to fetch payment events:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleFilterChange = (key: keyof Filters, value: string) => {
    setFilters({ ...filters, [key]: value });
    setPage(1);
  };

  const toggleExpand = (eventId: number) => {
    setExpandedEvent(expandedEvent === eventId ? null : eventId);
  };

  const exportToCSV = () => {
    const headers = ['Event ID', 'Type', 'User Email', 'Processed At', 'Created At'];
    const rows = events.map(e => [
      e.stripe_event_id,
      e.event_type,
      e.user_email || 'N/A',
      new Date(e.processed_at).toLocaleString(),
      new Date(e.created_at).toLocaleString()
    ]);

    const csv = [
      headers.join(','),
      ...rows.map(row => row.join(','))
    ].join('\n');

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `payment-events-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
  };

  const getEventTypeClass = (eventType: string): string => {
    if (eventType.includes('succeeded')) return 'success';
    if (eventType.includes('failed')) return 'error';
    if (eventType.includes('updated')) return 'info';
    return 'default';
  };

  if (loading && events.length === 0) {
    return <div className="loading">{t('common.loading')}</div>;
  }

  return (
    <div className="payment-event-log">
      <div className="header">
        <h2>{t('admin.payment_events.title')}</h2>
        <button onClick={exportToCSV} className="btn-export">
          {t('admin.actions.export_csv')}
        </button>
      </div>

      {/* Filters */}
      <div className="filters">
        <div className="filter-group">
          <label>{t('admin.payment_events.event_type')}</label>
          <select
            value={filters.event_type}
            onChange={(e) => handleFilterChange('event_type', e.target.value)}
          >
            <option value="">{t('admin.filters.all')}</option>
            <option value="checkout.session.completed">Checkout Completed</option>
            <option value="invoice.payment_succeeded">Payment Succeeded</option>
            <option value="invoice.payment_failed">Payment Failed</option>
            <option value="customer.subscription.updated">Subscription Updated</option>
            <option value="customer.subscription.deleted">Subscription Deleted</option>
          </select>
        </div>

        <div className="filter-group">
          <label>{t('admin.payment_events.user_email')}</label>
          <input
            type="text"
            value={filters.user_email}
            onChange={(e) => handleFilterChange('user_email', e.target.value)}
            placeholder={t('admin.filters.search_email')}
          />
        </div>

        <div className="filter-group">
          <label>{t('admin.payment_events.date_from')}</label>
          <input
            type="date"
            value={filters.date_from}
            onChange={(e) => handleFilterChange('date_from', e.target.value)}
          />
        </div>

        <div className="filter-group">
          <label>{t('admin.payment_events.date_to')}</label>
          <input
            type="date"
            value={filters.date_to}
            onChange={(e) => handleFilterChange('date_to', e.target.value)}
          />
        </div>
      </div>

      {/* Events Table */}
      <div className="events-table">
        <table>
          <thead>
            <tr>
              <th>{t('admin.payment_events.event_id')}</th>
              <th>{t('admin.payment_events.type')}</th>
              <th>{t('admin.payment_events.user')}</th>
              <th>{t('admin.payment_events.processed_at')}</th>
              <th>{t('admin.payment_events.actions')}</th>
            </tr>
          </thead>
          <tbody>
            {events.map((event) => (
              <React.Fragment key={event.id}>
                <tr>
                  <td className="event-id">{event.stripe_event_id.substring(0, 20)}...</td>
                  <td>
                    <span className={`event-type ${getEventTypeClass(event.event_type)}`}>
                      {event.event_type}
                    </span>
                  </td>
                  <td>{event.user_email || `User #${event.user_id}`}</td>
                  <td>{new Date(event.processed_at).toLocaleString()}</td>
                  <td>
                    <button
                      onClick={() => toggleExpand(event.id)}
                      className="btn-expand"
                    >
                      {expandedEvent === event.id ? '▼' : '▶'}
                    </button>
                  </td>
                </tr>
                {expandedEvent === event.id && (
                  <tr className="expanded-row">
                    <td colSpan={5}>
                      <div className="event-details">
                        <div className="detail-section">
                          <h4>{t('admin.payment_events.full_event_id')}</h4>
                          <code>{event.stripe_event_id}</code>
                        </div>
                        <div className="detail-section">
                          <h4>{t('admin.payment_events.created_at')}</h4>
                          <p>{new Date(event.created_at).toLocaleString()}</p>
                        </div>
                        <div className="detail-section">
                          <h4>{t('admin.payment_events.payload')}</h4>
                          <pre>{JSON.stringify(event.payload, null, 2)}</pre>
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="pagination">
        <button
          onClick={() => setPage(p => Math.max(1, p - 1))}
          disabled={page === 1}
          className="btn-page"
        >
          {t('admin.pagination.previous')}
        </button>
        <span className="page-info">
          {t('admin.pagination.page')} {page} {t('admin.pagination.of')} {totalPages}
        </span>
        <button
          onClick={() => setPage(p => Math.min(totalPages, p + 1))}
          disabled={page === totalPages}
          className="btn-page"
        >
          {t('admin.pagination.next')}
        </button>
      </div>
    </div>
  );
};

export default PaymentEventLog;
