import { useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import LanguageSwitcher from '../components/common/LanguageSwitcher';
import SubpageBackLink from '../components/common/SubpageBackLink';
import './LegalPage.css';

type LegalType = 'impressum' | 'agb' | 'datenschutz' | 'terms' | 'privacy';

const LegalPage = () => {
  const { type } = useParams<{ type: string }>();
  const { t } = useTranslation();
  const typeMap: Record<string, LegalType> = { terms: 'agb', privacy: 'datenschutz' };
  const page = (typeMap[type || ''] || type || 'impressum') as LegalType;

  useEffect(() => { window.scrollTo(0, 0); }, [page]);

  return (
    <div className="legal-page">
      <header className="legal-nav">
        <div className="legal-nav-in">
          <Link to="/" className="legal-logo">
            <span className="legal-logo-ic"><span /></span>
            <span className="legal-logo-tx">{t('common.appName')}</span>
          </Link>
          <div className="legal-nav-r">
            <LanguageSwitcher />
            <SubpageBackLink to="/" label={t('legal.back')} className="legal-back" />
          </div>
        </div>
      </header>

      <div className="legal-tabs">
        <Link to="/legal/impressum" className={"legal-tab" + (page === 'impressum' ? " active" : "")}>{t('legal.impressum')}</Link>
        <Link to="/legal/agb" className={"legal-tab" + (page === 'agb' ? " active" : "")}>{t('legal.agb')}</Link>
        <Link to="/legal/datenschutz" className={"legal-tab" + (page === 'datenschutz' ? " active" : "")}>{t('legal.datenschutz')}</Link>
      </div>

      <main className="legal-content">
        {page === 'impressum' && <ImpressumContent />}
        {page === 'agb' && <AGBContent />}
        {page === 'datenschutz' && <DatenschutzContent />}
      </main>

      <footer className="legal-footer">
        <p>© {new Date().getFullYear()} Taxja. {t('legal.allRightsReserved')}</p>
      </footer>
    </div>
  );
};

const Nl = ({ text }: { text: string }) => (
  <>{text.split('\n').map((line, i) => <span key={i}>{line}<br /></span>)}</>
);

const ImpressumContent = () => {
  const { t } = useTranslation();
  const serviceProviderLines = String(t('legal.serviceProviderContent')).split('\n').filter(Boolean);
  const [serviceProviderName, ...serviceProviderDetails] = serviceProviderLines;
  const companyHomepageUrl = String(t('legal.companyHomepageUrl', '/company'));

  return (
    <article className="legal-article">
      <h1>{t('legal.impressumTitle')}</h1>
      <p className="legal-meta">{t('legal.impressumMeta')}</p>

      <section>
        <h2>{t('legal.serviceProvider')}</h2>
        <p>
          <Link to={companyHomepageUrl} className="legal-company-link">
            {serviceProviderName || String(t('legal.companyHomepage', 'OOHK'))}
          </Link>
          <br />
          {serviceProviderDetails.map((line, index) => (
            <span key={index}>
              {line}
              <br />
            </span>
          ))}
        </p>
      </section>
      <section><h2>{t('legal.contact')}</h2><p><Nl text={t('legal.contactContent')} /></p></section>
      <section><h2>{t('legal.tradeInfo')}</h2><p><Nl text={t('legal.tradeInfoContent')} /></p></section>
      <section><h2>{t('legal.taxInfo')}</h2><p><Nl text={t('legal.taxInfoContent')} /></p></section>
      <section><h2>{t('legal.mediaLaw')}</h2><p><Nl text={t('legal.mediaLawContent')} /></p></section>
      <section><h2>{t('legal.wtbgDisclaimer')}</h2><p>{t('legal.wtbgDisclaimerContent')}</p></section>
      <section><h2>{t('legal.aiDisclaimer')}</h2><p>{t('legal.aiDisclaimerContent')}</p></section>
      <section><h2>{t('legal.jurisdiction')}</h2><p>{t('legal.jurisdictionContent')}</p></section>
      <section><h2>{t('legal.liability')}</h2><p>{t('legal.liabilityContent')}</p><p>{t('legal.liabilityContent2')}</p></section>
      <section>
        <h2>{t('legal.disputeResolution')}</h2>
        <p>{t('legal.disputeResolutionContent')}{' '}
          <a href="https://ec.europa.eu/consumers/odr" target="_blank" rel="noopener noreferrer">https://ec.europa.eu/consumers/odr</a>
        </p>
      </section>
    </article>
  );
};

const AGBContent = () => {
  const { t } = useTranslation();
  return (
    <article className="legal-article">
      <h1>{t('legal.agbTitle')}</h1>
      <p className="legal-meta">{t('legal.agbMeta')}</p>
      <section><h2>{t('legal.agbScope')}</h2><p>{t('legal.agbScopeContent')}</p></section>
      <section><h2>{t('legal.agbService')}</h2><p>{t('legal.agbServiceContent')}</p></section>
      <section><h2>{t('legal.agbRegistration')}</h2><p>{t('legal.agbRegistrationContent')}</p></section>
      <section><h2>{t('legal.agbPricing')}</h2><p>{t('legal.agbPricingContent')}</p></section>
      <section><h2>{t('legal.agbWithdrawal')}</h2><p>{t('legal.agbWithdrawalContent')}</p></section>
      <section><h2>{t('legal.agbAvailability')}</h2><p>{t('legal.agbAvailabilityContent')}</p></section>
      <section><h2>{t('legal.agbNoTaxAdvice')}</h2><p>{t('legal.agbNoTaxAdviceContent')}</p></section>
      <section><h2>{t('legal.agbAI')}</h2><p>{t('legal.agbAIContent')}</p></section>
      <section><h2>{t('legal.agbLiability')}</h2><p>{t('legal.agbLiabilityContent')}</p></section>
      <section><h2>{t('legal.agbTermination')}</h2><p>{t('legal.agbTerminationContent')}</p></section>
      <section><h2>{t('legal.agbChanges')}</h2><p>{t('legal.agbChangesContent')}</p></section>
      <section><h2>{t('legal.agbDataPortability')}</h2><p>{t('legal.agbDataPortabilityContent')}</p></section>
      <section><h2>{t('legal.agbDisputeResolution')}</h2><p>{t('legal.agbDisputeResolutionContent')}</p></section>
      <section><h2>{t('legal.agbFinal')}</h2><p>{t('legal.agbFinalContent')}</p></section>
    </article>
  );
};

const DatenschutzContent = () => {
  const { t } = useTranslation();
  return (
    <article className="legal-article">
      <h1>{t('legal.datenschutzTitle')}</h1>
      <p className="legal-meta">{t('legal.datenschutzMeta')}</p>
      <section><h2>{t('legal.controller')}</h2><p><Nl text={t('legal.controllerContent')} /></p></section>
      <section><h2>{t('legal.dataCollected')}</h2><p>{t('legal.dataCollectedContent')}</p></section>
      <section><h2>{t('legal.legalBasis')}</h2><p>{t('legal.legalBasisContent')}</p></section>
      <section><h2>{t('legal.dataSecurity')}</h2><p>{t('legal.dataSecurityContent')}</p></section>
      <section><h2>{t('legal.processors')}</h2><p>{t('legal.processorsContent')}</p></section>
      <section><h2>{t('legal.retention')}</h2><p>{t('legal.retentionContent')}</p></section>
      <section><h2>{t('legal.rights')}</h2><p>{t('legal.rightsContent')}</p></section>
      <section><h2>{t('legal.dataExport')}</h2><p>{t('legal.dataExportContent')}</p></section>
      <section><h2>{t('legal.aiDataProcessing')}</h2><p>{t('legal.aiDataProcessingContent')}</p></section>
      <section><h2>{t('legal.cookies')}</h2><p>{t('legal.cookiesContent')}</p></section>
      <section><h2>{t('legal.complaint')}</h2><p>{t('legal.complaintContent')}</p></section>
    </article>
  );
};

export default LegalPage;
