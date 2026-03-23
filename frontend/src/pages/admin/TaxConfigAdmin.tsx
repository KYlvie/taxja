import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useConfirm } from '../../hooks/useConfirm';
import { getLocaleForLanguage } from '../../utils/locale';
import taxConfigService, { TaxConfigSummary } from '../../services/taxConfigService';
import SubpageBackLink from '../../components/common/SubpageBackLink';
import './TaxConfigAdmin.css';

const TaxConfigAdmin = () => {
  const { t, i18n } = useTranslation();
  const { confirm: showConfirm } = useConfirm();
  const [configs, setConfigs] = useState<TaxConfigSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedYear, setSelectedYear] = useState<number | null>(null);
  const [detail, setDetail] = useState<TaxConfigSummary | null>(null);
  const [cloneTarget, setCloneTarget] = useState('');
  const [showCloneModal, setShowCloneModal] = useState(false);

  const loadConfigs = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await taxConfigService.listConfigs();
      setConfigs(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load configs');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadConfigs(); }, []);

  const handleViewDetail = async (year: number) => {
    try {
      const data = await taxConfigService.getConfig(year);
      setDetail(data);
      setSelectedYear(year);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load config');
    }
  };

  const handleClone = async (sourceYear: number) => {
    const target = parseInt(cloneTarget);
    if (!target || target < 2020 || target > 2099) {
      setError(t('taxConfig.invalidYear'));
      return;
    }
    try {
      await taxConfigService.cloneConfig(sourceYear, target);
      setShowCloneModal(false);
      setCloneTarget('');
      await loadConfigs();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Clone failed');
    }
  };

  const handleDelete = async (year: number) => {
    const ok = await showConfirm(t('taxConfig.confirmDelete', { year }), { variant: 'danger', confirmText: t('common.delete') });
    if (!ok) return;
    try {
      await taxConfigService.deleteConfig(year);
      if (selectedYear === year) {
        setDetail(null);
        setSelectedYear(null);
      }
      await loadConfigs();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Delete failed');
    }
  };

  const fmt = (n: number) =>
    new Intl.NumberFormat(getLocaleForLanguage(i18n.language), {
      style: 'currency', currency: 'EUR', minimumFractionDigits: 2,
    }).format(n);

  const fmtPct = (n: number) => `${(n * 100).toFixed(1)}%`;

  if (loading) return <div className="tax-config-admin loading">{t('taxConfig.loading')}</div>;

  return (
    <div className="tax-config-admin">
      <div className="page-header">
        <SubpageBackLink to="/admin" />
        <h1>{t('taxConfig.title')}</h1>
        <p className="page-subtitle">{t('taxConfig.subtitle')}</p>
      </div>

      {error && (
        <div className="alert alert-error" style={{ marginBottom: 16 }}>
          {error}
          <button onClick={() => setError(null)} style={{ marginLeft: 8, cursor: 'pointer' }}>×</button>
        </div>
      )}

      <div className="config-layout">
        <div className="config-list">
          <h2>{t('taxConfig.configuredYears')}</h2>
          <table className="config-table">
            <thead>
              <tr>
                <th>{t('taxConfig.year')}</th>
                <th>{t('taxConfig.exemption')}</th>
                <th>{t('taxConfig.bracketCount')}</th>
                <th>{t('taxConfig.smallBizThreshold')}</th>
                <th>{t('taxConfig.updatedAt')}</th>
                <th>{t('taxConfig.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {configs.map(c => (
                <tr
                  key={c.tax_year}
                  className={selectedYear === c.tax_year ? 'selected' : ''}
                  onClick={() => handleViewDetail(c.tax_year)}
                >
                  <td className="year-cell">{c.tax_year}</td>
                  <td>{fmt(c.exemption_amount)}</td>
                  <td>{c.tax_brackets.length}</td>
                  <td>{fmt(c.vat_rates?.small_business_threshold || 0)}</td>
                  <td className="date-cell">
                    {c.updated_at ? new Date(c.updated_at).toLocaleDateString(getLocaleForLanguage(i18n.language)) : '—'}
                  </td>
                  <td className="actions-cell" onClick={e => e.stopPropagation()}>
                    <button
                      className="btn-sm btn-clone"
                      onClick={() => { setSelectedYear(c.tax_year); setShowCloneModal(true); }}
                      title={t('taxConfig.clone')}
                    >+</button>
                    <button
                      className="btn-sm btn-delete"
                      onClick={() => handleDelete(c.tax_year)}
                      title={t('common.delete')}
                    >×</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {configs.length === 0 && (
            <p style={{ textAlign: 'center', color: '#888', padding: 20 }}>
              {t('taxConfig.noConfigs')}
            </p>
          )}
        </div>

        {detail && (
          <div className="config-detail">
            <h2>{t('taxConfig.yearConfig', { year: detail.tax_year })}</h2>

            <div className="detail-section">
              <h3>{t('taxConfig.incomeBrackets')}</h3>
              <table className="bracket-table">
                <thead>
                  <tr>
                    <th>{t('taxConfig.lowerBound')}</th>
                    <th>{t('taxConfig.upperBound')}</th>
                    <th>{t('taxConfig.taxRate')}</th>
                  </tr>
                </thead>
                <tbody>
                  {detail.tax_brackets.map((b: any, i: number) => (
                    <tr key={i}>
                      <td>{fmt(b.lower)}</td>
                      <td>{b.upper ? fmt(b.upper) : '∞'}</td>
                      <td>{fmtPct(b.rate)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="detail-section">
              <h3>{t('taxConfig.vat')}</h3>
              <div className="detail-grid">
                <span>{t('taxConfig.vatStandard')}:</span><span>{fmtPct(detail.vat_rates.standard)}</span>
                <span>{t('taxConfig.vatResidential')}:</span><span>{fmtPct(detail.vat_rates.residential)}</span>
                <span>{t('taxConfig.vatSmallBiz')}:</span><span>{fmt(detail.vat_rates.small_business_threshold)}</span>
                <span>{t('taxConfig.vatTolerance')}:</span><span>{fmt(detail.vat_rates.tolerance_threshold)}</span>
              </div>
            </div>

            <div className="detail-section">
              <h3>{t('taxConfig.svs')}</h3>
              <div className="detail-grid">
                <span>{t('taxConfig.svsPension')}:</span><span>{fmtPct(detail.svs_rates.pension)}</span>
                <span>{t('taxConfig.svsHealth')}:</span><span>{fmtPct(detail.svs_rates.health)}</span>
                <span>{t('taxConfig.svsAccident')}:</span><span>{fmt(detail.svs_rates.accident_fixed)}{t('taxConfig.perMonth')}</span>
                {detail.svs_rates.supplementary_pension != null && (
                  <><span>{t('taxConfig.svsSupplementaryPension')}:</span><span>{fmtPct(detail.svs_rates.supplementary_pension)}</span></>
                )}
                <span>{t('taxConfig.svsMinBase')}:</span><span>{fmt(detail.svs_rates.gsvg_min_base_monthly)}{t('taxConfig.perMonth')}</span>
                {detail.svs_rates.gsvg_min_income_yearly != null && (
                  <><span>{t('taxConfig.svsMinIncomeYearly')}:</span><span>{fmt(detail.svs_rates.gsvg_min_income_yearly)}{t('taxConfig.perYear')}</span></>
                )}
                {detail.svs_rates.neue_min_monthly != null && (
                  <><span>{t('taxConfig.svsNeueMinMonthly')}:</span><span>{fmt(detail.svs_rates.neue_min_monthly)}{t('taxConfig.perMonth')}</span></>
                )}
                <span>{t('taxConfig.svsMaxBase')}:</span><span>{fmt(detail.svs_rates.max_base_monthly)}{t('taxConfig.perMonth')}</span>
              </div>
            </div>

            {detail.deduction_config && (
              <div className="detail-section">
                <h3>{t('taxConfig.deductions')}</h3>
                <div className="detail-grid">
                  {detail.deduction_config.home_office != null && (
                    <><span>{t('taxConfig.homeOffice')}:</span><span>{fmt(detail.deduction_config.home_office)}</span></>
                  )}
                  {detail.deduction_config.werbungskostenpauschale != null && (
                    <><span>{t('taxConfig.werbungskostenpauschale')}:</span><span>{fmt(detail.deduction_config.werbungskostenpauschale)}</span></>
                  )}
                  {detail.deduction_config.sonderausgabenpauschale != null && (
                    <><span>{t('taxConfig.sonderausgabenpauschale')}:</span><span>{fmt(detail.deduction_config.sonderausgabenpauschale)}</span></>
                  )}
                  {detail.deduction_config.verkehrsabsetzbetrag != null && (
                    <><span>{t('taxConfig.verkehrsabsetzbetrag')}:</span><span>{fmt(detail.deduction_config.verkehrsabsetzbetrag)}</span></>
                  )}
                  {detail.deduction_config.zuschlag_verkehrsabsetzbetrag != null && (
                    <><span>{t('taxConfig.zuschlagVerkehr')}:</span><span>{fmt(detail.deduction_config.zuschlag_verkehrsabsetzbetrag)}</span></>
                  )}
                  {detail.deduction_config.zuschlag_income_lower != null && (
                    <><span>{t('taxConfig.zuschlagIncomeLower')}:</span><span>{fmt(detail.deduction_config.zuschlag_income_lower)}</span></>
                  )}
                  {detail.deduction_config.zuschlag_income_upper != null && (
                    <><span>{t('taxConfig.zuschlagIncomeUpper')}:</span><span>{fmt(detail.deduction_config.zuschlag_income_upper)}</span></>
                  )}
                  {detail.deduction_config.child_deduction_monthly != null && (
                    <><span>{t('taxConfig.childDeduction')}:</span><span>{fmt(detail.deduction_config.child_deduction_monthly)}</span></>
                  )}
                  {detail.deduction_config.familienbonus_under_18 != null && (
                    <><span>{t('taxConfig.familienbonusUnder18')}:</span><span>{fmt(detail.deduction_config.familienbonus_under_18)}</span></>
                  )}
                  {detail.deduction_config.familienbonus_18_24 != null && (
                    <><span>{t('taxConfig.familienbonus18_24')}:</span><span>{fmt(detail.deduction_config.familienbonus_18_24)}</span></>
                  )}
                  {detail.deduction_config.single_parent_deduction != null && (
                    <><span>{t('taxConfig.singleParentDeduction')}:</span><span>{fmt(detail.deduction_config.single_parent_deduction)}</span></>
                  )}
                  {detail.deduction_config.alleinverdiener_base != null && (
                    <><span>{t('taxConfig.alleinverdienerBase')}:</span><span>{fmt(detail.deduction_config.alleinverdiener_base)}</span></>
                  )}
                  {detail.deduction_config.alleinverdiener_per_child != null && (
                    <><span>{t('taxConfig.alleinverdienerPerChild')}:</span><span>{fmt(detail.deduction_config.alleinverdiener_per_child)}</span></>
                  )}
                  {detail.deduction_config.pensionisten_absetzbetrag != null && (
                    <><span>{t('taxConfig.pensionistenAbsetzbetrag')}:</span><span>{fmt(detail.deduction_config.pensionisten_absetzbetrag)}</span></>
                  )}
                  {detail.deduction_config.pensionisten_income_lower != null && (
                    <><span>{t('taxConfig.pensionistenIncomeLower')}:</span><span>{fmt(detail.deduction_config.pensionisten_income_lower)}</span></>
                  )}
                  {detail.deduction_config.pensionisten_income_upper != null && (
                    <><span>{t('taxConfig.pensionistenIncomeUpper')}:</span><span>{fmt(detail.deduction_config.pensionisten_income_upper)}</span></>
                  )}
                  {detail.deduction_config.erhoehter_pensionisten != null && (
                    <><span>{t('taxConfig.erhoehterPensionisten')}:</span><span>{fmt(detail.deduction_config.erhoehter_pensionisten)}</span></>
                  )}
                  {detail.deduction_config.erhoehter_pensionisten_upper != null && (
                    <><span>{t('taxConfig.erhoehterPensionistenUpper')}:</span><span>{fmt(detail.deduction_config.erhoehter_pensionisten_upper)}</span></>
                  )}
                  {detail.deduction_config.pendler_euro_per_km != null && (
                    <><span>{t('taxConfig.pendlerEuro')}:</span><span>€ {detail.deduction_config.pendler_euro_per_km.toFixed(2)}</span></>
                  )}
                  {detail.deduction_config.basic_exemption_rate != null && (
                    <><span>{t('taxConfig.basicExemptionRate')}:</span><span>{fmtPct(detail.deduction_config.basic_exemption_rate)}</span></>
                  )}
                  {detail.deduction_config.basic_exemption_max != null && (
                    <><span>{t('taxConfig.basicExemptionMax')}:</span><span>{fmt(detail.deduction_config.basic_exemption_max)}</span></>
                  )}
                </div>
              </div>
            )}

            {detail.deduction_config?.commuting_brackets && (
              <div className="detail-section">
                <h3>{t('taxConfig.commuting')}</h3>
                {Object.entries(detail.deduction_config.commuting_brackets as Record<string, Record<string, number>>).map(([size, brackets]) => (
                  <div key={size} style={{ marginBottom: '0.5rem' }}>
                    <h4>{size === 'small' ? t('taxConfig.commutingSmall') : t('taxConfig.commutingLarge')}</h4>
                    <div className="detail-grid">
                      {Object.entries(brackets).map(([km, amount]) => (
                        <><span key={km}>{t('taxConfig.kmRange', { km })}:</span><span>{fmt(amount)}{t('taxConfig.perMonth')}</span></>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {detail.deduction_config?.self_employed && (
              <div className="detail-section">
                <h3>{t('taxConfig.selfEmployedDetails')}</h3>
                <div className="detail-grid">
                  <span>{t('taxConfig.grundfreibetragProfitLimit')}:</span>
                  <span>{fmt(detail.deduction_config.self_employed.grundfreibetrag_profit_limit)}</span>
                  <span>{t('taxConfig.grundfreibetragRate')}:</span>
                  <span>{fmtPct(detail.deduction_config.self_employed.grundfreibetrag_rate)}</span>
                  <span>{t('taxConfig.grundfreibetragMax')}:</span>
                  <span>{fmt(detail.deduction_config.self_employed.grundfreibetrag_max)}</span>
                  <span>{t('taxConfig.maxTotalFreibetrag')}:</span>
                  <span>{fmt(detail.deduction_config.self_employed.max_total_freibetrag)}</span>
                  <span>{t('taxConfig.flatRateTurnoverLimit')}:</span>
                  <span>{fmt(detail.deduction_config.self_employed.flat_rate_turnover_limit)}</span>
                  <span>{t('taxConfig.flatRateGeneral')}:</span>
                  <span>{fmtPct(detail.deduction_config.self_employed.flat_rate_general)}</span>
                  <span>{t('taxConfig.flatRateConsulting')}:</span>
                  <span>{fmtPct(detail.deduction_config.self_employed.flat_rate_consulting)}</span>
                  <span>{t('taxConfig.kleinunternehmerThreshold')}:</span>
                  <span>{fmt(detail.deduction_config.self_employed.kleinunternehmer_threshold)}</span>
                  <span>{t('taxConfig.kleinunternehmerTolerance')}:</span>
                  <span>{fmt(detail.deduction_config.self_employed.kleinunternehmer_tolerance)}</span>
                  <span>{t('taxConfig.ustVoranmeldungThreshold')}:</span>
                  <span>{fmt(detail.deduction_config.self_employed.ust_voranmeldung_monthly_threshold)}</span>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {showCloneModal && selectedYear && (
        <div className="modal-overlay" onClick={() => setShowCloneModal(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <h3>{t('taxConfig.cloneTitle', { year: selectedYear })}</h3>
            <p>{t('taxConfig.cloneDesc', { year: selectedYear })}</p>
            <div className="form-group">
              <label htmlFor="clone-target">{t('taxConfig.targetYear')}</label>
              <input
                id="clone-target"
                type="number"
                min="2020"
                max="2099"
                value={cloneTarget}
                onChange={e => setCloneTarget(e.target.value)}
                placeholder={String(selectedYear + 1)}
              />
            </div>
            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={() => setShowCloneModal(false)}>
                {t('common.cancel')}
              </button>
              <button className="btn btn-primary" onClick={() => handleClone(selectedYear)}>
                {t('taxConfig.clone')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default TaxConfigAdmin;
