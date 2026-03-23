import { useTranslation } from 'react-i18next';
import ChatInterface from '../components/ai/ChatInterface';
import SubpageBackLink from '../components/common/SubpageBackLink';
import './AIAssistantPage.css';

const AIAssistantPage = () => {
  const { t } = useTranslation();

  return (
    <div className="ai-assistant-page">
      <SubpageBackLink to="/dashboard" />
      <div className="page-header">
        <h1>{t('ai.taxjaAssistant')}</h1>
        <p className="page-description">
          {t(
            'ai.pageDescription',
            'Ask the AI tax assistant about Austrian tax rules, deductibility, and optimization options.'
          )}
        </p>
      </div>
      <div className="ai-chat-fullpage">
        <ChatInterface />
      </div>
    </div>
  );
};

export default AIAssistantPage;
