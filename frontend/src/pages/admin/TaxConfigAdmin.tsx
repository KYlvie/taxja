import { useState, useEffect } from 'react';
import taxConfigService, { TaxConfigSummary } from '../../services/taxConfigService';
import './TaxConfigAdmin.css';

const TaxConfigAdmin = () => {
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
      setError('请输入有效年份 (2020-2099)');
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
    if (!window.confirm(`确定删除 ${year} 年的税务配置？此操作不可撤销。`)) return;
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
    new Intl.NumberFormat('de-AT', {
      style: 'currency', currency: 'EUR', minimumFractionDigits: 2,
    }).format(n);

  const fmtPct = (n: number) => `${(n * 100).toFixed(1)}%`;

  if (loading) return <div className="tax-config-admin loading">加载中...</div>;

  return (
    <div className="tax-config-admin">
      <div className="page-header">
        <h1>🏛️ 税务配置管理</h1>
        <p className="page-subtitle">
          管理各年度的奥地利税务参数。新增年份时，建议从最近年份克隆后修改。
        </p>
      </div>

      {error && (
        <div className="alert alert-error" style={{ marginBottom: 16 }}>
          ⚠️ {error}
          <button onClick={() => setError(null)} style={{ marginLeft: 8, cursor: 'pointer' }}>✕</button>
        </div>
      )}

      <div className="config-layout">
        <div className="config-list">
          <h2>已配置年份</h2>
          <table className="config-table">
            <thead>
              <tr>
                <th>年份</th>
                <th>免税额</th>
                <th>税级数</th>
                <th>小企业门槛</th>
                <th>更新时间</th>
                <th>操作</th>
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
                    {c.updated_at ? new Date(c.updated_at).toLocaleDateString('de-AT') : '—'}
                  </td>
                  <td className="actions-cell" onClick={e => e.stopPropagation()}>
                    <button
                      className="btn-sm btn-clone"
                      onClick={() => { setSelectedYear(c.tax_year); setShowCloneModal(true); }}
                      title="克隆到新年份"
                    >📋</button>
                    <button
                      className="btn-sm btn-delete"
                      onClick={() => handleDelete(c.tax_year)}
                      title="删除"
                    >🗑️</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {configs.length === 0 && (
            <p style={{ textAlign: 'center', color: '#888', padding: 20 }}>
              数据库中没有税务配置。请运行 seed 脚本初始化。
            </p>
          )}
        </div>

        {detail && (
          <div className="config-detail">
            <h2>{detail.tax_year} 年税务配置</h2>

            <div className="detail-section">
              <h3>所得税级距</h3>
              <table className="bracket-table">
                <thead>
                  <tr><th>下限</th><th>上限</th><th>税率</th></tr>
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
              <h3>增值税 (USt)</h3>
              <div className="detail-grid">
                <span>标准税率:</span><span>{fmtPct(detail.vat_rates.standard)}</span>
                <span>住宅税率:</span><span>{fmtPct(detail.vat_rates.residential)}</span>
                <span>小企业门槛:</span><span>{fmt(detail.vat_rates.small_business_threshold)}</span>
                <span>容差门槛:</span><span>{fmt(detail.vat_rates.tolerance_threshold)}</span>
              </div>
            </div>

            <div className="detail-section">
              <h3>社会保险 (SVS)</h3>
              <div className="detail-grid">
                <span>养老金:</span><span>{fmtPct(detail.svs_rates.pension)}</span>
                <span>医疗保险:</span><span>{fmtPct(detail.svs_rates.health)}</span>
                <span>意外保险:</span><span>{fmt(detail.svs_rates.accident_fixed)}/月</span>
                <span>最低基数:</span><span>{fmt(detail.svs_rates.gsvg_min_base_monthly)}/月</span>
                <span>最高基数:</span><span>{fmt(detail.svs_rates.max_base_monthly)}/月</span>
              </div>
            </div>

            {detail.deduction_config?.self_employed && (
              <div className="detail-section">
                <h3>自雇人士</h3>
                <div className="detail-grid">
                  <span>基本免税率:</span>
                  <span>{fmtPct(detail.deduction_config.self_employed.grundfreibetrag_rate)}</span>
                  <span>基本免税上限:</span>
                  <span>{fmt(detail.deduction_config.self_employed.grundfreibetrag_max)}</span>
                  <span>小企业门槛:</span>
                  <span>{fmt(detail.deduction_config.self_employed.kleinunternehmer_threshold)}</span>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {showCloneModal && selectedYear && (
        <div className="modal-overlay" onClick={() => setShowCloneModal(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <h3>克隆 {selectedYear} 年配置</h3>
            <p>将 {selectedYear} 年的所有税务参数复制到新年份，然后您可以修改具体数值。</p>
            <div className="form-group">
              <label htmlFor="clone-target">目标年份</label>
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
                取消
              </button>
              <button className="btn btn-primary" onClick={() => handleClone(selectedYear)}>
                克隆
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default TaxConfigAdmin;
