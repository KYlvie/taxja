import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { formatCurrency, normalizeLanguage } from '../../utils/locale';
import './SavingsSuggestions.css';

interface Suggestion {
  id: number;
  title: string;
  description: string;
  potentialSavings: number;
  actionLink: string;
  actionLabel?: string;
  type?: string;
  documentType?: string;
}

interface SavingsSuggestionsProps {
  suggestions: Suggestion[];
}

/** Helper that builds a GuideCopy-compatible object from t() calls */
const buildGuideCopy = (t: (key: string) => string) => ({
  intro: t('savingsSuggestions.intro'),
  amountHint: t('savingsSuggestions.amountHint'),
  whyLabel: t('savingsSuggestions.whyLabel'),
  nextStepLabel: t('savingsSuggestions.nextStepLabel'),
  afterLabel: t('savingsSuggestions.afterLabel'),
  destinationLabel: t('savingsSuggestions.destinationLabel'),
  badges: {
    missingDeduction: t('savingsSuggestions.badges.missingDeduction'),
    missingDocument: t('savingsSuggestions.badges.missingDocument'),
    manualCheck: t('savingsSuggestions.badges.manualCheck'),
    reviewNeeded: t('savingsSuggestions.badges.reviewNeeded'),
    dataConflict: t('savingsSuggestions.badges.dataConflict'),
    gettingStarted: t('savingsSuggestions.badges.gettingStarted'),
    generic: t('savingsSuggestions.badges.generic'),
  },
  amountLabels: {
    deduction: t('savingsSuggestions.amountLabels.deduction'),
    review: t('savingsSuggestions.amountLabels.review'),
    generic: t('savingsSuggestions.amountLabels.generic'),
  },
  destinations: {
    transactions: t('savingsSuggestions.destinations.transactions'),
    documents: t('savingsSuggestions.destinations.documents'),
    profile: t('savingsSuggestions.destinations.profile'),
    recurring: t('savingsSuggestions.destinations.recurring'),
    dashboard: t('savingsSuggestions.destinations.dashboard'),
    generic: t('savingsSuggestions.destinations.generic'),
  },
  buttons: {
    homeOffice: t('savingsSuggestions.buttons.homeOffice'),
    commuting: t('savingsSuggestions.buttons.commuting'),
    insurance: t('savingsSuggestions.buttons.insurance'),
    review: t('savingsSuggestions.buttons.review'),
    ocr: t('savingsSuggestions.buttons.ocr'),
    missingDocument: t('savingsSuggestions.buttons.missingDocument'),
    conflict: t('savingsSuggestions.buttons.conflict'),
    gettingStarted: t('savingsSuggestions.buttons.gettingStarted'),
    generic: t('savingsSuggestions.buttons.generic'),
  },
  docs: {
    lohnzettel: t('savingsSuggestions.docs.lohnzettel'),
    einkommensteuerbescheid: t('savingsSuggestions.docs.einkommensteuerbescheid'),
    e1_form: t('savingsSuggestions.docs.e1_form'),
    svs_notice: t('savingsSuggestions.docs.svs_notice'),
    purchase_contract: t('savingsSuggestions.docs.purchase_contract'),
    rental_contract: t('savingsSuggestions.docs.rental_contract'),
  },
  templates: {
    homeOffice: {
      title: t('savingsSuggestions.templates.homeOffice.title'),
      reason: t('savingsSuggestions.templates.homeOffice.reason'),
      next: t('savingsSuggestions.templates.homeOffice.next'),
      after: t('savingsSuggestions.templates.homeOffice.after'),
    },
    commuting: {
      title: t('savingsSuggestions.templates.commuting.title'),
      reason: t('savingsSuggestions.templates.commuting.reason'),
      next: t('savingsSuggestions.templates.commuting.next'),
      after: t('savingsSuggestions.templates.commuting.after'),
    },
    insurance: {
      title: t('savingsSuggestions.templates.insurance.title'),
      reason: t('savingsSuggestions.templates.insurance.reason'),
      next: t('savingsSuggestions.templates.insurance.next'),
      after: t('savingsSuggestions.templates.insurance.after'),
    },
    review: {
      next: t('savingsSuggestions.templates.review.next'),
      after: t('savingsSuggestions.templates.review.after'),
    },
    ocr: {
      title: t('savingsSuggestions.templates.ocr.title'),
      reason: t('savingsSuggestions.templates.ocr.reason'),
      next: t('savingsSuggestions.templates.ocr.next'),
      after: t('savingsSuggestions.templates.ocr.after'),
    },
    missingDocument: {
      reasonPrefix: t('savingsSuggestions.templates.missingDocument.reasonPrefix'),
      nextPrefix: t('savingsSuggestions.templates.missingDocument.nextPrefix'),
      after: t('savingsSuggestions.templates.missingDocument.after'),
    },
    conflict: {
      title: t('savingsSuggestions.templates.conflict.title'),
      next: t('savingsSuggestions.templates.conflict.next'),
      after: t('savingsSuggestions.templates.conflict.after'),
    },
    gettingStarted: {
      title: t('savingsSuggestions.templates.gettingStarted.title'),
      reason: t('savingsSuggestions.templates.gettingStarted.reason'),
      next: t('savingsSuggestions.templates.gettingStarted.next'),
      after: t('savingsSuggestions.templates.gettingStarted.after'),
    },
    generic: {
      next: t('savingsSuggestions.templates.generic.next'),
      after: t('savingsSuggestions.templates.generic.after'),
    },
  },
});

type GuideCopy = ReturnType<typeof buildGuideCopy>;

interface ResolvedSuggestionGuide {
  title: string;
  reason: string;
  nextStep: string;
  after: string;
  badge: string;
  destination: string;
  amountLabel: string;
  actionLabel: string;
  toneClass: string;
  icon: string;
}


const getDestinationLabel = (actionLink: string, copy: GuideCopy) => {
  const [path] = actionLink.split('?');

  switch (path) {
    case '/transactions':
      return copy.destinations.transactions;
    case '/documents':
      return copy.destinations.documents;
    case '/profile':
      return copy.destinations.profile;
    case '/recurring':
      return copy.destinations.recurring;
    case '/dashboard':
      return copy.destinations.dashboard;
    default:
      return copy.destinations.generic;
  }
};

const getToneClass = (suggestion: Suggestion) => {
  switch (suggestion.type) {
    case 'data_conflict':
      return 'suggestion-conflict';
    case 'missing_document':
      return 'suggestion-missing-document';
    case 'action_needed':
      return 'suggestion-action-needed';
    case 'review_needed':
      return 'suggestion-review-needed';
    case 'getting_started':
      return 'suggestion-getting-started';
    case 'missing_deduction':
    default:
      return 'suggestion-deduction';
  }
};

const getIcon = (suggestion: Suggestion) => {
  switch (suggestion.type) {
    case 'missing_document':
      return '\u{1F4C4}';
    case 'data_conflict':
      return '\u26A0';
    case 'action_needed':
      return '\u{1F50D}';
    case 'review_needed':
      return '\u{1F4CB}';
    case 'getting_started':
      return '\u{1F680}';
    case 'missing_deduction':
    default:
      return '\u{1F4A1}';
  }
};

const getBadgeLabel = (suggestion: Suggestion, copy: GuideCopy) => {
  switch (suggestion.type) {
    case 'missing_document':
      return copy.badges.missingDocument;
    case 'action_needed':
      return copy.badges.manualCheck;
    case 'review_needed':
      return copy.badges.reviewNeeded;
    case 'data_conflict':
      return copy.badges.dataConflict;
    case 'getting_started':
      return copy.badges.gettingStarted;
    case 'missing_deduction':
      return copy.badges.missingDeduction;
    default:
      return copy.badges.generic;
  }
};

const getAmountLabel = (suggestion: Suggestion, copy: GuideCopy) => {
  if (suggestion.type === 'missing_deduction') {
    return copy.amountLabels.deduction;
  }

  if (suggestion.type === 'review_needed') {
    return copy.amountLabels.review;
  }

  return copy.amountLabels.generic;
};

const resolveGuide = (suggestion: Suggestion, copy: GuideCopy): ResolvedSuggestionGuide => {
  const query = new URLSearchParams(suggestion.actionLink.split('?')[1] || '');
  const category = query.get('category');
  const destination = getDestinationLabel(suggestion.actionLink, copy);
  const toneClass = getToneClass(suggestion);
  const icon = getIcon(suggestion);
  const badge = getBadgeLabel(suggestion, copy);
  const amountLabel = getAmountLabel(suggestion, copy);

  if (suggestion.type === 'missing_deduction' && category === 'home_office') {
    return {
      title: copy.templates.homeOffice.title,
      reason: copy.templates.homeOffice.reason,
      nextStep: copy.templates.homeOffice.next,
      after: copy.templates.homeOffice.after,
      badge,
      destination,
      amountLabel,
      actionLabel: copy.buttons.homeOffice,
      toneClass,
      icon,
    };
  }

  if (suggestion.type === 'missing_deduction' && category === 'commuting') {
    return {
      title: copy.templates.commuting.title,
      reason: copy.templates.commuting.reason,
      nextStep: copy.templates.commuting.next,
      after: copy.templates.commuting.after,
      badge,
      destination,
      amountLabel,
      actionLabel: copy.buttons.commuting,
      toneClass,
      icon,
    };
  }

  if (suggestion.type === 'missing_deduction' && category === 'insurance') {
    return {
      title: copy.templates.insurance.title,
      reason: copy.templates.insurance.reason,
      nextStep: copy.templates.insurance.next,
      after: copy.templates.insurance.after,
      badge,
      destination,
      amountLabel,
      actionLabel: copy.buttons.insurance,
      toneClass,
      icon,
    };
  }

  if (suggestion.type === 'review_needed') {
    return {
      title: suggestion.title,
      reason: suggestion.description,
      nextStep: copy.templates.review.next,
      after: copy.templates.review.after,
      badge,
      destination,
      amountLabel,
      actionLabel: suggestion.actionLabel || copy.buttons.review,
      toneClass,
      icon,
    };
  }

  if (suggestion.type === 'action_needed') {
    return {
      title: copy.templates.ocr.title,
      reason: copy.templates.ocr.reason,
      nextStep: copy.templates.ocr.next,
      after: copy.templates.ocr.after,
      badge,
      destination,
      amountLabel,
      actionLabel: suggestion.actionLabel || copy.buttons.ocr,
      toneClass,
      icon,
    };
  }

  if (suggestion.type === 'missing_document') {
    const docKey = (suggestion.documentType || '') as keyof typeof copy.docs;
    const documentLabel = copy.docs[docKey] || suggestion.title;

    return {
      title: documentLabel,
      reason: `${copy.templates.missingDocument.reasonPrefix} ${documentLabel}`,
      nextStep: `${copy.templates.missingDocument.nextPrefix} ${documentLabel}`,
      after: copy.templates.missingDocument.after,
      badge,
      destination,
      amountLabel,
      actionLabel: suggestion.actionLabel || copy.buttons.missingDocument,
      toneClass,
      icon,
    };
  }

  if (suggestion.type === 'data_conflict') {
    return {
      title: copy.templates.conflict.title,
      reason: suggestion.description,
      nextStep: copy.templates.conflict.next,
      after: copy.templates.conflict.after,
      badge,
      destination,
      amountLabel,
      actionLabel: suggestion.actionLabel || copy.buttons.conflict,
      toneClass,
      icon,
    };
  }

  if (suggestion.type === 'getting_started') {
    return {
      title: copy.templates.gettingStarted.title,
      reason: copy.templates.gettingStarted.reason,
      nextStep: copy.templates.gettingStarted.next,
      after: copy.templates.gettingStarted.after,
      badge,
      destination,
      amountLabel,
      actionLabel: suggestion.actionLabel || copy.buttons.gettingStarted,
      toneClass,
      icon,
    };
  }

  return {
    title: suggestion.title,
    reason: suggestion.description,
    nextStep: copy.templates.generic.next,
    after: copy.templates.generic.after,
    badge,
    destination,
    amountLabel,
    actionLabel: suggestion.actionLabel || copy.buttons.generic,
    toneClass,
    icon,
  };
};

const SavingsSuggestions = ({ suggestions }: SavingsSuggestionsProps) => {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const currentLanguage = normalizeLanguage(i18n.resolvedLanguage || i18n.language);
  const copy = buildGuideCopy(t);
  const topSuggestions = suggestions.slice(0, 5);

  const handleAction = (actionLink: string) => {
    navigate(actionLink);
  };

  if (topSuggestions.length === 0) {
    return (
      <div className="savings-suggestions">
        <h3>{t('dashboard.savingsSuggestions')}</h3>
        <div className="no-suggestions">
          <p>
            {'\u{1F389}'} {t('dashboard.noSuggestions')}
          </p>
          <p className="subtitle">{t('dashboard.optimizedTaxes')}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="savings-suggestions">
      <div className="suggestions-header">
        <div>
          <h3>{t('dashboard.savingsSuggestions')}</h3>
          <p className="suggestions-intro">{copy.intro}</p>
          <p className="suggestions-amount-hint">{copy.amountHint}</p>
        </div>
        <span className="suggestions-badge">{suggestions.length}</span>
      </div>

      <div className="suggestions-list">
        {topSuggestions.map((suggestion) => {
          const guide = resolveGuide(suggestion, copy);

          return (
            <div key={suggestion.id} className={`suggestion-card ${guide.toneClass}`}>
              <div className="suggestion-rank">{guide.icon}</div>
              <div className="suggestion-content">
                <div className="suggestion-meta">
                  <span className="suggestion-kind">{guide.badge}</span>
                  <span className="suggestion-destination">
                    {copy.destinationLabel}: {guide.destination}
                  </span>
                </div>

                <h4>{guide.title}</h4>

                <div className="suggestion-panels">
                  <div className="suggestion-panel">
                    <span className="panel-label">{copy.whyLabel}</span>
                    <p>{guide.reason}</p>
                  </div>
                  <div className="suggestion-panel">
                    <span className="panel-label">{copy.nextStepLabel}</span>
                    <p>{guide.nextStep}</p>
                  </div>
                </div>

                <div className="suggestion-footer">
                  <div className="suggestion-action-copy">
                    <span className="panel-label">{copy.afterLabel}</span>
                    <p>{guide.after}</p>
                  </div>

                  <div className="suggestion-action-group">
                    {suggestion.potentialSavings > 0 && (
                      <div className="potential-savings">
                        <span className="savings-label">{guide.amountLabel}</span>
                        <span className="savings-amount">
                          {formatCurrency(suggestion.potentialSavings, currentLanguage)}
                        </span>
                      </div>
                    )}

                    <button className="action-button" onClick={() => handleAction(suggestion.actionLink)}>
                      {guide.actionLabel}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {suggestions.length > 5 && (
        <div className="more-suggestions">
          <p>
            {t('dashboard.moreSuggestions', {
              count: suggestions.length - 5,
            })}
          </p>
        </div>
      )}
    </div>
  );
};

export default SavingsSuggestions;
