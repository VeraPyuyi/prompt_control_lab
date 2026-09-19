import { useEffect, useState } from 'react';
import { Download, Microscope, Play } from 'lucide-react';
import { experimentRequest, type Json } from '../experimentApi';
import type { Language } from '../types';

const tools = [
  { id: 'readout', en: 'Readout sensitivity', zh: '行为读出敏感性', enText: 'Check whether parsing, output limits and decoding change your findings.', zhText: '检查解析规则、输出预算与解码条件是否改变了结论。' },
  { id: 'response', en: 'Control response profile', zh: '控制响应画像', enText: 'Relate control movement to loss, response, alignment and local approximation.', zhText: '从已保存的测量中计算损失变化、控制位移、读出对齐与近似残差。' },
  { id: 'measurement-value', en: 'Value of measurement', zh: '测量价值分析', enText: 'Compare changes found under equal budgets, including the cost of diagnostics.', zhText: '计入诊断成本，比较相同预算下能发现多少变化。' },
  { id: 'transfer', en: 'Transfer prediction', zh: '迁移预测检验', enText: 'Compare locked forecasts against simple baselines and grouped uncertainty.', zhText: '将锁定预测与简单基线对照，并检查分组统计的不确定性。' },
  { id: 'replay', en: 'Replay and property checks', zh: '结果重放与性质核对', enText: 'Separate file integrity, numerical reproduction and local theoretical assumptions.', zhText: '分别核对文件完整性、数值复算与局部理论前提。' },
];

export function ResearchToolsPage({ language, writeEnabled = true }: { language: Language; writeEnabled?: boolean }) {
  const zh = language === 'zh';
  const t = (en: string, cn: string) => zh ? cn : en;
  const [kind, setKind] = useState('readout');
  const [input, setInput] = useState('');
  const [result, setResult] = useState<Json>();
  const [page, setPage] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const tool = tools.find(item => item.id === kind)!;
  useEffect(() => {
    let alive = true;
    setPage('');
    if (result?.id) void fetch(`/api/research/${result.id}/artifacts/report.${language}.html`)
      .then(response => { if (!response.ok) throw new Error('Report unavailable'); return response.text(); })
      .then(html => { if (alive) setPage(html); })
      .catch(reason => { if (alive) setError(String(reason)); });
    return () => { alive = false; };
  }, [result, language]);
  async function sample() {
    setBusy(true);
    try {
      const data = await experimentRequest(`/api/research-examples/${kind}`);
      setInput(JSON.stringify(data, null, 2)); setError(''); setResult(undefined);
    } catch (reason) { setError(String(reason)); }
    finally { setBusy(false); }
  }
  async function run() {
    setBusy(true); setError(''); setResult(undefined);
    try { setResult(await experimentRequest(`/api/research/${kind}`, JSON.parse(input))); }
    catch (reason) { setError(String(reason)); }
    finally { setBusy(false); }
  }
  return <div className="experiment-page research-page">
    <header className="experiment-hero"><span className="eyebrow">PROMPTCONTROLLAB / RESEARCH</span>
      <h1>{t('Understand the conditions behind a result.', '理解结果成立的条件。')}</h1>
      <p>{t('Five tools for saved research evidence. Each keeps its source, assumptions and uncertainty visible.', '五类工具处理已保存的科研证据，同时呈现来源、假设与不确定性。')}</p>
    </header>
    <div className="research-tool-grid">{tools.map(item => <button disabled={busy} className={`card research-tool ${kind === item.id ? 'active' : ''}`} key={item.id} onClick={() => { setKind(item.id); setInput(''); setResult(undefined); setError(''); }}>
      <Microscope size={20} /><strong>{zh ? item.zh : item.en}</strong><span>{zh ? item.zhText : item.enText}</span>
    </button>)}</div>
    {error && <div role="alert" className="experiment-alert error">{error}</div>}
    {!writeEnabled && <div role="status" className="experiment-alert">{t('This public preview is read-only. Run PromptControlLab locally to analyze your evidence.', '当前公开预览只读。请在本地运行 PromptControlLab 分析证据。')}</div>}
    <section className="card experiment-form"><div className="section-heading"><h2>{zh ? tool.zh : tool.en}</h2><button className="button" disabled={busy} onClick={() => void sample()}>{t('Load a synthetic example', '载入合成样例')}</button></div>
      <p className="field-help">{t('Upload saved measurements or inspect the example format. This analysis makes no model calls.', '上传已保存的测量，或通过样例了解输入格式。本分析不调用模型。')}</p>
      <input disabled={busy} aria-label={t('Upload research evidence', '上传科研证据')} type="file" accept=".json" onChange={e => {
        const file = e.target.files?.[0];
        if (file && file.size <= 5_000_000) { setResult(undefined); setBusy(true); void file.text().then(setInput).finally(() => setBusy(false)); }
        else if (file) setError(t('Choose a file smaller than 5 MB.', '请选择小于 5 MB 的文件。'));
      }} />
      <textarea disabled={busy} aria-label={t('Research input', '科研输入')} value={input} rows={12} spellCheck={false} onChange={e => { setInput(e.target.value); setResult(undefined); }} placeholder={t('Load an example or paste your JSON evidence.', '载入样例或粘贴 JSON 证据。')} />
      <button className="button primary" disabled={!writeEnabled || busy || !input.trim()} onClick={() => void run()}><Play size={16} />{busy ? t('Computing…', '计算中…') : t('Recompute and explain', '复算并解释')}</button>
    </section>
    {result && <section className="card experiment-results"><div className="section-heading"><h2>{t('Diagnostic report', '诊断报告')}</h2><div className="experiment-downloads">{[[`report.${language}.html`, 'HTML'], ['report.json', 'JSON'], ['metrics.csv', 'CSV']].map(([file, label]) => <a className="button" key={file} href={`/api/research/${result.id}/artifacts/${file}`}><Download size={14} />{label}</a>)}</div></div>
      <iframe className="research-report" sandbox="" title={t('Research report', '科研报告')} srcDoc={page} />
    </section>}
  </div>;
}
