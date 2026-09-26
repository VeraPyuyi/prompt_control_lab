import { useEffect, useState } from 'react';
import { Download, FileArchive, History, Microscope, Play, RefreshCw, Square, Upload } from 'lucide-react';
import { experimentRequest, getSessionToken, type Json } from '../experimentApi';
import type { Language } from '../types';

const tools = [
  { id: 'readout', en: 'Readout & execution', zh: '读出与执行条件', enText: 'Separate answer changes from format and execution differences.', zhText: '分开查看答案、格式和执行条件的变化。' },
  { id: 'response', en: 'Control response', zh: '控制响应画像', enText: 'Inspect response, calibration, rank and label dependencies.', zhText: '检查控制响应、校准、秩与标签依赖。' },
  { id: 'measurement-value', en: 'Measurement value', zh: '测量价值', enText: 'Include the full cost of finding a change.', zhText: '计入发现变化所需的完整成本。' },
  { id: 'transfer', en: 'Transfer prediction', zh: '迁移预测', enText: 'Distinguish new questions from unseen prompts.', zhText: '区分新题迁移与未见提示迁移。' },
  { id: 'replay', en: 'Replay & properties', zh: '重放与性质核对', enText: 'Check integrity, numerical replay and local assumptions separately.', zhText: '分别核对完整性、数值重放与局部前提。' },
];
const suites: Record<string, [string, string]> = {
  independent: ['Independent prompt panel', '独立提示面板'], cross: ['Prompts × questions', '提示词 × 题目'],
  confirmation: ['Same prompts, fresh questions', '同提示、新题'], gsm8k: ['Unseen-prompt transfer', '未见提示迁移'],
  readout: ['Shared readout intervals', '读出共享重采样'],
};
const statuses: Record<string, [string, string]> = {
  queued: ['Queued', '排队中'], running: ['Running', '运行中'], completed: ['Completed', '已完成'],
  cancelled: ['Cancelled', '已取消'], interrupted: ['Interrupted', '已中断'], failed: ['Failed', '失败'],
};

export function ResearchToolsPage({ language, writeEnabled = true }: { language: Language; writeEnabled?: boolean }) {
  const zh = language === 'zh';
  const t = (en: string, cn: string) => zh ? cn : en;
  const [kind, setKind] = useState('readout');
  const [input, setInput] = useState('');
  const [bundle, setBundle] = useState<Json>();
  const [selected, setSelected] = useState<number[]>([]);
  const [job, setJob] = useState<Json>();
  const [jobs, setJobs] = useState<Json[]>([]);
  const [page, setPage] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const active = job?.status === 'queued' || job?.status === 'running';
  const label = (analysis: Json) => {
    if (analysis.kind === 'bootstrap') return suites[analysis.suite]?.[zh ? 1 : 0] ?? analysis.suite;
    const tool = tools.find(item => item.id === (analysis.tool ?? analysis.kind));
    const name = tool ? (zh ? tool.zh : tool.en) : t('Saved material inventory', '已有材料清单');
    return analysis.kind === 'saved-summary' ? `${name} · ${t('saved tables', '已有表格')}` : name;
  };
  const status = (value: string) => statuses[value]?.[zh ? 1 : 0] ?? value;

  async function refreshHistory() {
    const result = await experimentRequest('/api/research-jobs');
    setJobs(result.jobs ?? []);
  }
  useEffect(() => {
    if (writeEnabled) void refreshHistory().catch(reason => setError(String(reason)));
  }, [writeEnabled]);
  useEffect(() => {
    if (!job?.id || !active) return;
    let alive = true;
    const timer = window.setInterval(() => {
      void experimentRequest(`/api/research-jobs/${job.id}`).then(value => {
        if (alive) { setJob(value); if (!['queued', 'running'].includes(value.status)) void refreshHistory(); }
      }).catch(reason => { if (alive) setError(String(reason)); });
    }, 750);
    return () => { alive = false; window.clearInterval(timer); };
  }, [job?.id, active]);
  useEffect(() => {
    let alive = true;
    setPage('');
    if (job?.id && ['completed', 'cancelled', 'failed', 'interrupted'].includes(job.status) && Object.keys(job.completed ?? {}).length) {
      void fetch(`/api/research-jobs/${job.id}/artifacts/report.${language}.html`)
        .then(response => { if (!response.ok) throw new Error(t('Report unavailable', '报告暂不可用')); return response.text(); })
        .then(value => { if (alive) setPage(value); }).catch(reason => { if (alive) setError(String(reason)); });
    }
    return () => { alive = false; };
  }, [job?.id, job?.status, language]);

  async function upload(content: Blob, filename: string) {
    if (content.size > 64 * 1024 * 1024) throw new Error(t('Choose data of at most 64 MiB.', '请选择不超过 64 MiB 的材料。'));
    const token = await getSessionToken();
    const response = await fetch(`/api/research-bundles?filename=${encodeURIComponent(filename)}`, {
      method: 'POST', headers: { 'X-PCL-Session': token, 'Content-Type': 'application/octet-stream' }, body: content,
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail ?? t('Import failed', '导入失败'));
    setBundle(data); setSelected(data.analyses.map((_: Json, index: number) => index)); setJob(undefined); setPage('');
  }
  async function perform(action: () => Promise<void>) {
    setBusy(true); setError('');
    try { await action(); } catch (reason) { setError(String(reason)); } finally { setBusy(false); }
  }
  async function sample() {
    await perform(async () => {
      const data = await experimentRequest(`/api/research-examples/${kind}?version=2`);
      const text = JSON.stringify(data, null, 2); setInput(text);
      if (writeEnabled) await upload(new Blob([text], { type: 'application/json' }), `${kind}.json`);
    });
  }
  async function run() {
    if (!bundle) return;
    await perform(async () => {
      const created = await experimentRequest('/api/research-jobs', {
        schema_version: 'pcl.research-analysis/v1', bundle_id: bundle.id,
        analyses: selected.map(index => bundle.analyses[index]),
      });
      setJob(created); await refreshHistory();
    });
  }
  async function manage(action: 'cancel' | 'resume') {
    if (!job) return;
    await perform(async () => { setJob(await experimentRequest(`/api/research-jobs/${job.id}/${action}`, {})); await refreshHistory(); });
  }

  return <div className="experiment-page research-page">
    <header className="experiment-hero"><span className="eyebrow">PROMPTCONTROLLAB / RESEARCH</span>
      <h1>{t('Understand the conditions behind a result.', '理解结果成立的条件。')}</h1>
      <p>{t('Import evidence, see what can be recomputed, and keep uncertainty and cost visible.', '导入证据，确认能重算什么，同时看清不确定性与成本。')}</p>
    </header>
    <div className="research-tool-grid">{tools.map(item => <button disabled={busy} className={`card research-tool ${kind === item.id ? 'active' : ''}`} key={item.id} onClick={() => { setKind(item.id); setInput(''); }}>
      <Microscope size={20} /><strong>{zh ? item.zh : item.en}</strong><span>{zh ? item.zhText : item.enText}</span>
    </button>)}</div>
    {error && <div role="alert" className="experiment-alert error">{error}</div>}
    {!writeEnabled && <div role="status" className="experiment-alert">{t('This preview is read-only. Run locally to import and analyze your evidence.', '当前预览只读。请在本地导入和分析证据。')}</div>}
    <section className="card experiment-form">
      <div className="section-heading"><h2>{t('1. Bring your evidence', '1. 导入研究材料')}</h2>
        <button className="button" disabled={busy} onClick={() => void sample()}>{t('Load a synthetic example', '载入合成样例')}</button></div>
      <p className="field-help">{t('JSON, CSV, NPZ or ZIP · up to 64 MiB. Analyses use saved data and make no model calls. Uploaded scripts are never run.', '支持 JSON、CSV、NPZ 或 ZIP，最大 64 MiB。分析使用保存的数据，不调用模型，也不执行上传的脚本。')}</p>
      <label className="research-upload"><Upload size={22} /><span>{t('Choose research evidence', '选择研究材料')}</span>
        <input disabled={!writeEnabled || busy} aria-label={t('Upload research evidence', '上传科研证据')} type="file" accept=".json,.csv,.npz,.zip" onChange={event => {
          const file = event.target.files?.[0];
          if (file) void perform(() => upload(file, file.name));
        }} /></label>
      <details className="research-advanced"><summary>{t('Inspect or paste JSON', '查看或粘贴 JSON')}</summary>
        <textarea disabled={busy} aria-label={t('Research input', '科研输入')} value={input} rows={9} spellCheck={false} onChange={event => setInput(event.target.value)} />
        <button className="button" disabled={!writeEnabled || busy || !input.trim()} onClick={() => void perform(() => upload(new Blob([input], { type: 'application/json' }), `${kind}.json`))}>{t('Import this JSON', '导入此 JSON')}</button>
      </details>
    </section>
    {bundle && <section className="card experiment-form" aria-label={t('Evidence capabilities', '材料能力摘要')}>
      <div className="section-heading"><h2>{t('2. Choose what to check', '2. 选择分析项目')}</h2><span className="muted">{bundle.title}</span></div>
      <p>{bundle.synthetic ? t('Synthetic demonstration. Suitable for learning the workflow.', '合成演示材料，适合熟悉流程。') : t('Saved research material. The source and scope of each check stay explicit.', '已保存的研究材料。每项检查都会说明来源与适用范围。')}</p>
      <div className="research-capabilities">{bundle.capabilities.map((item: Json, index: number) => <div className="research-capability" key={index}>
        <strong>{label(item)}</strong><span>{item.level === 'saved_scores' ? t('Recompute statistics from saved scores', '从保存的分数重算统计') : item.level === 'provenance_missing' ? t('Original provenance receipts are needed to certify this declaration.', '认证此来源声明需要原始关联凭证。') : item.level === 'unsupported_protocol' ? t('Protocol version unsupported; inspect saved values only.', '尚不支持此协议版本；仅查看已有数据。') : item.level === 'summary_only' ? t('Display saved summaries only', '仅展示已有汇总') : t('Recompute the supplied measurements', '重算所提供的测量')}</span>
      </div>)}</div>
      <p className="field-help">{t('File integrity does not certify prediction timing, statistical support or practical benefit.', '文件完整性不等于预测时间已认证、统计证据充分或实际收益成立。')}</p>
      <div className="research-selections">{bundle.analyses.map((analysis: Json, index: number) => <label key={index}>
        <input type="checkbox" checked={selected.includes(index)} disabled={busy || active} onChange={event => setSelected(current => event.target.checked ? [...current, index] : current.filter(item => item !== index))} />
        <span>{label(analysis)}{analysis.kind === 'bootstrap' && <small>{t('20,000 shared draws · frozen protocol', '20,000 次共享抽样 · 冻结协议')}</small>}</span>
      </label>)}</div>
      <button className="button primary" disabled={!writeEnabled || busy || active || !selected.length} onClick={() => void run()}><Play size={16} />{t('Run selected analyses', '运行所选分析')}</button>
    </section>}
    {job && <section className="card experiment-results" aria-live="polite">
      <div className="section-heading"><h2>{t('3. Review the evidence', '3. 查看证据与解释')}</h2><span>{status(job.status)}</span></div>
      <progress aria-label={t('Analysis progress', '分析进度')} max={job.progress.total} value={job.progress.completed} />
      <p>{job.progress.completed} / {job.progress.total} {t('analyses complete', '项分析完成')}{active && ` · ${t('Current stage', '当前阶段')}: ${suites[job.progress.phase]?.[zh ? 1 : 0] ?? status(job.progress.phase)}`}</p>
      <p className="field-help">{t('Completed analyses are retained. An interrupted suite restarts from its frozen inputs and seed.', '已完成分析会保留；中断的套件从冻结输入与随机种子重新计算。')}</p>
      {job.error && <div className="experiment-alert error">{job.error}</div>}
      <div className="experiment-downloads">{active ? <button disabled={busy} className="button" onClick={() => void manage('cancel')}><Square size={14} />{t('Cancel', '取消')}</button> : ['cancelled', 'failed', 'interrupted'].includes(job.status) && <button disabled={busy} className="button" onClick={() => void manage('resume')}><RefreshCw size={14} />{t('Resume', '恢复')}</button>}
        {Object.keys(job.completed ?? {}).length > 0 && !active && [[`report.${language}.html`, 'HTML'], ['report.json', 'JSON'], ['metrics.csv', 'CSV'], ['research.zip', t('Replay bundle', '重放包')]].map(([file, name]) => <a className="button" key={file} href={`/api/research-jobs/${job.id}/artifacts/${file}`}><Download size={14} />{name}</a>)}
      </div>
      {page && <iframe className="research-report" sandbox="" title={t('Research report', '科研报告')} srcDoc={page} />}
    </section>}
    <section className="card research-history"><div className="section-heading"><h2><History size={19} /> {t('Analysis history', '分析历史')}</h2><button className="button" disabled={!writeEnabled || busy} onClick={() => void perform(refreshHistory)}>{t('Refresh', '刷新')}</button></div>
      {!jobs.length && <p className="muted">{t('Your completed and interrupted analyses will appear here.', '完成和中断的分析都会保存在这里。')}</p>}
      {jobs.map(item => <button className={`research-history-row ${job?.id === item.id ? 'active' : ''}`} key={item.id} disabled={busy} onClick={() => { setJob(item); setBundle(undefined); }}>
        <FileArchive size={18} /><span>{item.spec.analyses.map(label).join(' · ')}<small>{new Date(item.created_at * 1000).toLocaleString(zh ? 'zh-CN' : 'en-US')}</small></span><strong>{status(item.status)}</strong>
      </button>)}
    </section>
  </div>;
}
