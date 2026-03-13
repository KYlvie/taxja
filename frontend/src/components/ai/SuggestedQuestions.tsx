import React from 'react';
import { useTranslation } from 'react-i18next';
import { HelpCircle, Calculator, FileText, TrendingUp, Home } from 'lucide-react';
import './SuggestedQuestions.css';

interface SuggestedQuestionsProps {
  contextData?: {
    page?: string;
    documentId?: string;
    transactionId?: string;
  };
  onQuestionClick: (question: string) => void;
}

const SuggestedQuestions: React.FC<SuggestedQuestionsProps> = ({
  contextData,
  onQuestionClick,
}) => {
  const { t } = useTranslation();

  // Get context-aware questions based on current page
  const getContextQuestions = () => {
    const page = contextData?.page;

    switch (page) {
      case 'dashboard':
        return [
          { icon: TrendingUp, text: t('ai.questions.dashboard.taxSavings') },
          { icon: Calculator, text: t('ai.questions.dashboard.estimatedTax') },
          { icon: FileText, text: t('ai.questions.dashboard.nextDeadline') },
        ];

      case 'transactions':
        return [
          { icon: Calculator, text: t('ai.questions.transactions.deductible') },
          { icon: FileText, text: t('ai.questions.transactions.categorize') },
          { icon: HelpCircle, text: t('ai.questions.transactions.vat') },
        ];

      case 'documents':
        return [
          { icon: FileText, text: t('ai.questions.documents.receipt') },
          { icon: HelpCircle, text: t('ai.questions.documents.invoice') },
          { icon: Calculator, text: t('ai.questions.documents.deductible') },
        ];

      case 'reports':
        return [
          { icon: FileText, text: t('ai.questions.reports.generate') },
          { icon: HelpCircle, text: t('ai.questions.reports.finanzonline') },
          { icon: Calculator, text: t('ai.questions.reports.refund') },
        ];

      default:
        return getGeneralQuestions();
    }
  };

  // General questions for all pages
  const getGeneralQuestions = () => [
    { icon: Calculator, text: t('ai.questions.general.incomeTax') },
    { icon: FileText, text: t('ai.questions.general.deductions') },
    { icon: TrendingUp, text: t('ai.questions.general.svs') },
    { icon: Home, text: t('ai.questions.general.commuting') },
    { icon: HelpCircle, text: t('ai.questions.general.vat') },
    { icon: Calculator, text: t('ai.questions.general.flatRate') },
  ];

  const questions = getContextQuestions();

  return (
    <div className="suggested-questions">
      <div className="suggested-questions-title">
        <HelpCircle size={16} />
        <span>{t('ai.suggestedQuestions')}</span>
      </div>
      <div className="suggested-questions-grid">
        {questions.map((question, index) => {
          const Icon = question.icon;
          return (
            <button
              key={index}
              className="suggested-question-btn"
              onClick={() => onQuestionClick(question.text)}
            >
              <Icon size={18} />
              <span>{question.text}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
};

export default SuggestedQuestions;
