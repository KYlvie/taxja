import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import './UATFeedbackWidget.css';

interface UATFeedbackWidgetProps {
  testScenario: string;
  onSubmit?: () => void;
}

type FeedbackCategory = 'usability' | 'functionality' | 'value' | 'bug_report' | 'feature_request';
type FeedbackSeverity = 'critical' | 'high' | 'medium' | 'low';

export const UATFeedbackWidget: React.FC<UATFeedbackWidgetProps> = ({ testScenario, onSubmit }) => {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const [category, setCategory] = useState<FeedbackCategory>('usability');
  const [rating, setRating] = useState<number>(0);
  const [comment, setComment] = useState('');
  const [severity, setSeverity] = useState<FeedbackSeverity>('medium');
  const [stepsToReproduce, setStepsToReproduce] = useState('');
  const [expectedResult, setExpectedResult] = useState('');
  const [actualResult, setActualResult] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitSuccess, setSubmitSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);

    try {
      const browserInfo = `${navigator.userAgent}`;
      
      const feedbackData = {
        test_scenario: testScenario,
        category,
        rating: category !== 'bug_report' && category !== 'feature_request' ? rating : null,
        comment,
        severity: category === 'bug_report' ? severity : null,
        steps_to_reproduce: category === 'bug_report' ? stepsToReproduce : null,
        expected_result: category === 'bug_report' ? expectedResult : null,
        actual_result: category === 'bug_report' ? actualResult : null,
        browser_info: browserInfo,
      };

      const response = await fetch('/api/v1/uat/feedback', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(feedbackData),
      });

      if (response.ok) {
        setSubmitSuccess(true);
        setTimeout(() => {
          setIsOpen(false);
          setSubmitSuccess(false);
          resetForm();
          onSubmit?.();
        }, 2000);
      }
    } catch (error) {
      console.error('Error submitting feedback:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const resetForm = () => {
    setCategory('usability');
    setRating(0);
    setComment('');
    setSeverity('medium');
    setStepsToReproduce('');
    setExpectedResult('');
    setActualResult('');
  };

  const renderRatingStars = () => {
    return (
      <div className="rating-stars">
        {[1, 2, 3, 4, 5].map((star) => (
          <button
            key={star}
            type="button"
            className={`star ${rating >= star ? 'filled' : ''}`}
            onClick={() => setRating(star)}
          >
            ★
          </button>
        ))}
      </div>
    );
  };

  const isBugReport = category === 'bug_report';
  const requiresRating = ['usability', 'functionality', 'value'].includes(category);

  return (
    <div className="uat-feedback-widget">
      {!isOpen ? (
        <button
          className="feedback-trigger"
          onClick={() => setIsOpen(true)}
          title={t('uat.feedback.trigger')}
        >
          💬 {t('uat.feedback.button')}
        </button>
      ) : (
        <div className="feedback-modal">
          <div className="feedback-modal-content">
            <div className="feedback-header">
              <h3>{t('uat.feedback.title')}</h3>
              <button
                className="close-button"
                onClick={() => setIsOpen(false)}
              >
                ×
              </button>
            </div>

            {submitSuccess ? (
              <div className="success-message">
                <div className="success-icon">✓</div>
                <p>{t('uat.feedback.success')}</p>
              </div>
            ) : (
              <form onSubmit={handleSubmit}>
                <div className="form-group">
                  <label>{t('uat.feedback.category')}</label>
                  <select
                    value={category}
                    onChange={(e) => setCategory(e.target.value as FeedbackCategory)}
                    required
                  >
                    <option value="usability">{t('uat.feedback.categories.usability')}</option>
                    <option value="functionality">{t('uat.feedback.categories.functionality')}</option>
                    <option value="value">{t('uat.feedback.categories.value')}</option>
                    <option value="bug_report">{t('uat.feedback.categories.bug_report')}</option>
                    <option value="feature_request">{t('uat.feedback.categories.feature_request')}</option>
                  </select>
                </div>

                {requiresRating && (
                  <div className="form-group">
                    <label>{t('uat.feedback.rating')}</label>
                    {renderRatingStars()}
                    <small>{t('uat.feedback.ratingHelp')}</small>
                  </div>
                )}

                {isBugReport && (
                  <div className="form-group">
                    <label>{t('uat.feedback.severity')}</label>
                    <select
                      value={severity}
                      onChange={(e) => setSeverity(e.target.value as FeedbackSeverity)}
                      required
                    >
                      <option value="critical">{t('uat.feedback.severities.critical')}</option>
                      <option value="high">{t('uat.feedback.severities.high')}</option>
                      <option value="medium">{t('uat.feedback.severities.medium')}</option>
                      <option value="low">{t('uat.feedback.severities.low')}</option>
                    </select>
                  </div>
                )}

                {isBugReport && (
                  <>
                    <div className="form-group">
                      <label>{t('uat.feedback.stepsToReproduce')}</label>
                      <textarea
                        value={stepsToReproduce}
                        onChange={(e) => setStepsToReproduce(e.target.value)}
                        rows={4}
                        placeholder={t('uat.feedback.stepsPlaceholder')}
                        required
                      />
                    </div>

                    <div className="form-group">
                      <label>{t('uat.feedback.expectedResult')}</label>
                      <textarea
                        value={expectedResult}
                        onChange={(e) => setExpectedResult(e.target.value)}
                        rows={2}
                        placeholder={t('uat.feedback.expectedPlaceholder')}
                        required
                      />
                    </div>

                    <div className="form-group">
                      <label>{t('uat.feedback.actualResult')}</label>
                      <textarea
                        value={actualResult}
                        onChange={(e) => setActualResult(e.target.value)}
                        rows={2}
                        placeholder={t('uat.feedback.actualPlaceholder')}
                        required
                      />
                    </div>
                  </>
                )}

                <div className="form-group">
                  <label>{t('uat.feedback.comment')}</label>
                  <textarea
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                    rows={4}
                    placeholder={t('uat.feedback.commentPlaceholder')}
                  />
                </div>

                <div className="form-actions">
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={() => setIsOpen(false)}
                  >
                    {t('common.cancel')}
                  </button>
                  <button
                    type="submit"
                    className="btn-primary"
                    disabled={isSubmitting || (requiresRating && rating === 0)}
                  >
                    {isSubmitting ? t('common.submitting') : t('common.submit')}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
