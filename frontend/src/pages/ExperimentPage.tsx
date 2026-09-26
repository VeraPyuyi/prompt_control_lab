import { useEffect, useState } from 'react';
import { ArrowRight, Download, FlaskConical, Play, Square, WandSparkles } from 'lucide-react';
import type { Language } from '../types';
import { experimentRequest, type Json } from '../experimentApi';

const sampleData = [
  ['A wonderful service.', 'positive'], ['This is a terrible product.', 'negative'],
  ['Everything worked beautifully.', 'positive'], ['I regret buying this.', 'negative'],
  ['Really helpful and friendly.', 'positive'], ['The service was disappointing.', 'negative'],
  ['It made my day!', 'positive'], ['It broke on the first day.', 'negative'],
  ['Excellent quality and value.', 'positive'], ['It was a waste of money.', 'negative'],
].map(([input, expected], i) => ({ id: `example-${i + 1}`, input, expected }));
const initialPrompt = 'Tell me whether the customer is happy or unhappy.';
const improvedPrompt = 'Classify the sentiment of the text. Reply with exactly one lowercase word: positive or negative.';
const finalStates = new Set(['completed', 'completed_with_errors', 'stopped', 'cancelled', 'failed']);

export function ExperimentPage({ language, writeEnabled = true, active = true }: { language: Language; writeEnabled?: boolean; active?: boolean }) {
  const zh = language === 'zh';
  const t = (en: string, cn: string) => zh ? cn : en;
  const [operation, setOperation] = useState('run');
  const [name, setName] = useState('My prompt comparison');
  const [dataText, setDataText] = useState(sampleData.map(row => JSON.stringify(row)).join('\n'));
  const [format, setFormat] = useState('jsonl');
  const [mapping, setMapping] = useState({ id: 'id', input: 'input', expected: 'expected' });
  const [baseline, setBaseline] = useState(initialPrompt);
  const [candidate, setCandidate] = useState(improvedPrompt);
  const [provider, setProvider] = useState('openai-compatible');
  const [model, setModel] = useState('');
  const [candidateModel, setCandidateModel] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [key, setKey] = useState('');
  const [keyEnv, setKeyEnv] = useState('');
  const [authScheme, setAuthScheme] = useState('api_key');
  const [thinking, setThinking] = useState('');
  const [syntheticData, setSyntheticData] = useState(true);
  const [reflectionModel, setReflectionModel] = useState('');
  const [inputPrice, setInputPrice] = useState('');
  const [outputPrice, setOutputPrice] = useState('');
  const [maxCost, setMaxCost] = useState('');
  const [metric, setMetric] = useState('exact_match');
  const [calls, setCalls] = useState(200);
  const [tokens, setTokens] = useState(20000);
  const [seconds, setSeconds] = useState(900);
  const [outputLimit, setOutputLimit] = useState(128);
  const [rounds, setRounds] = useState(5);
  const [imports, setImports] = useState<{ baseline?: Json; candidate?: Json }>({});
  const [importText, setImportText] = useState({ baseline: '', candidate: '' });
  const [importPrompt, setImportPrompt] = useState({ baseline: '', candidate: '' });
  const [jobs, setJobs] = useState<Json[]>([]);
  const [selected, setSelected] = useState('');
  const [job, setJob] = useState<Json>();
  const [records, setRecords] = useState<Json>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  useEffect(() => {
    if (!active) return;
    let alive = true;
    const refresh = async () => {
      try {
        const list = await experimentRequest('/api/experiments');
        if (alive) setJobs(Array.isArray(list.experiments) ? list.experiments : []);
        if (selected) {
          const current = await experimentRequest(`/api/experiments/${selected}`);
          if (alive) setJob(current);
          if (finalStates.has(current.status)) {
            const rows = await experimentRequest(`/api/experiments/${selected}/artifacts/records.json`).catch(() => undefined);
            if (alive) setRecords(rows);
          }
        }
      } catch { /* The first action presents a localized, actionable error. */ }
    };
    void refresh(); const timer = window.setInterval(() => void refresh(), 1500);
    return () => { alive = false; window.clearInterval(timer); };
  }, [selected, active]);

  async function readFile(file: File | undefined, apply: (text: string, format: string) => void) {
    if (!file) return;
    if (file.size > 5_000_000) { setError(t('Choose a file smaller than 5 MB.', '请选择小于 5 MB 的文件。')); return; }
    apply(await file.text(), file.name.endsWith('.csv') ? 'csv' : file.name.endsWith('.jsonl') ? 'jsonl' : 'json');
  }
  async function normalize(arm: 'baseline' | 'candidate', text = importText[arm], fileFormat = 'json') {
    try {
      const result = await experimentRequest('/api/experiments/normalize-import', { text, format: fileFormat, arm, ...(importPrompt[arm] ? { prompt_id: importPrompt[arm] } : {}) });
      setImports(current => ({ ...current, [arm]: result }));
      if (result.kind === 'assets') {
        const content = result.assets?.[0]?.content;
        if (content) (arm === 'baseline' ? setBaseline : setCandidate)(content);
        setNotice('asset_loaded');
      }
      return result;
    } catch (reason) { setError(String(reason)); return undefined; }
  }
  async function start(demo = false) {
    setBusy(true); setError(''); setNotice(''); setRecords(undefined);
    try {
      const data = demo ? sampleData : (await experimentRequest('/api/experiments/parse-data', { text: dataText, format, mapping })).data;
      let reference = keyEnv;
      if (!demo && operation !== 'import' && key.trim()) {
        reference = (await experimentRequest('/api/credentials', { key })).api_key_env;
        setKey(''); setKeyEnv(reference);
      }
      const config: Json = { provider: demo || operation === 'import' ? 'imported' : provider, model: demo || operation === 'import' ? 'declared-import' : model, max_output_tokens: outputLimit };
      if (baseUrl && !demo && operation !== 'import') config.base_url = baseUrl;
      if (reference && !demo && operation !== 'import') config.api_key_env = reference;
      if (provider === 'anthropic' && !demo && operation !== 'import') config.auth_scheme = authScheme;
      if (provider === 'deepseek' && thinking && !demo && operation !== 'import') config.thinking = thinking;
      const spec: Json = { schema_version: 'experiment/v1', name: demo ? 'Offline example — preset synthetic outputs' : name,
        synthetic: demo || syntheticData, operation: demo ? 'import' : operation, data, metric: demo ? 'exact_match' : metric,
        baseline: { ...config, prompt: demo ? initialPrompt : baseline }, candidate: { ...config, model: demo || operation === 'import' ? config.model : candidateModel || config.model, prompt: demo ? improvedPrompt : candidate },
        budget: { max_calls: calls, max_output_tokens: tokens, max_seconds: seconds }, seed: 0,
        optimization: { max_rounds: rounds, patience: 2 }, max_concurrency: 2 };
      if (!demo && operation === 'optimize') {
        spec.candidate = { ...spec.baseline };
        spec.optimization.reflection = { ...config, model: reflectionModel || config.model, prompt: '', max_output_tokens: 512 };
      }
      if (!demo) for (const [field, value] of [['input_cost_per_million', inputPrice], ['output_cost_per_million', outputPrice], ['max_cost', maxCost]]) {
        if (value !== '') spec.budget[field] = Number(value);
      }
      if (demo) spec.predictions = {
        baseline: data.map((row: Json, i: number) => ({ id: row.id, output: i % 3 === 0 ? 'uncertain' : row.expected })),
        candidate: data.map((row: Json) => ({ id: row.id, output: row.expected })),
      };
      else if (operation === 'import') {
        const left = imports.baseline ?? await normalize('baseline');
        const right = imports.candidate ?? await normalize('candidate');
        if (left?.kind !== 'predictions' || right?.kind !== 'predictions') throw new Error(t('Paired evaluation needs per-item outputs for both prompts.', '成对比较需要两组逐条输出；资产或汇总指标可在上方查看。'));
        spec.predictions = { baseline: left.predictions, candidate: right.predictions };
      }
      const created = await experimentRequest('/api/experiments', spec);
      setSelected(created.id); setJob(created);
      if (demo) setNotice('offline_demo');
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setBusy(false); }
  }
  async function manage(action: string, retryFailed = false) {
    try { setJob(await experimentRequest(`/api/experiments/${selected}/${action}`, { retry_failed: retryFailed })); setError(''); }
    catch (reason) { setError(String(reason)); }
  }
  const assessment = job?.assessment;
  const coverage = assessment?.coverage;
  const stats = assessment?.effect?.statistics;
  const practical = assessment?.practical;
  const number = (value: unknown) => typeof value === 'number' && Number.isFinite(value) ? value !== 0 && Math.abs(value) < 0.001 ? value.toExponential(2) : value.toFixed(3) : '—';
  const allRows = records ? [...(records.baseline ?? []).map((row: Json) => ({ ...row, arm: 'baseline' })), ...(records.candidate ?? []).map((row: Json) => ({ ...row, arm: 'candidate' }))] : [];
  const labels: Record<string, string> = zh ? { comparable: '条件一致', confounded: '多项条件同时变化', declared_only: '来源由导入者声明', improved: '支持提升', regressed: '发现退步', uncertain: '提升尚不明确', no_observed_change: '未观察到变化', insufficient_data: '样本不足', completed: '已完成', completed_with_errors: '完成，部分样本出错', queued: '排队中', running: '运行中', stopped: '已停止', cancelled: '已取消', failed: '运行失败', unknown: '未确定', known: '已记录', complete: '完整', partial: '不完整' } : {};
  Object.assign(labels, zh ? { preparing: '准备中', evaluation: '评估', withheld: '留出比较', search: '搜索', validation: '验证', training: '训练', final: '最终比较', cancelling: '正在取消', import: '导入', imported: '已导入', baseline: '原版本', candidate: '候选版本', parse_error: '解析失败', format_error: '格式错误', empty_output: '空输出', model_error: '模型输出错误', service_error: '服务错误', timeout: '超时', max_rounds: '达到轮数上限', patience: '连续验证无提升', max_calls: '达到调用上限', max_output_tokens: '达到输出预算', max_seconds: '达到时间上限' } : {});
  const label = (value: unknown) => typeof value === 'string' ? labels[value] ?? value.replaceAll('_', ' ') : '—';
  const limitation = (message: string) => !zh ? message : ({
    'Imported model and prompt provenance is user-declared': '导入结果的模型与提示词来源由提供者声明。',
    'Different model or decoding settings prevent isolating prompt effects': '模型或解码条件也发生了变化，无法单独归因于提示词。',
    'Evaluation-only comparison; no untouched generalization claim': '这是评估数据上的比较，尚不能说明在全新数据上同样有效。',
    'Effect estimates use only successfully matched pairs; missingness may bias them': '效果仅使用成功配对的样本；缺失结果可能带来偏差。',
    'Matched rows share inputs or sample/group metadata; inferential claims are disabled': '样本共享输入或分组信息，当前仅展示描述性变化。',
  }[message] ?? message);
  const nextAction = assessment?.next_action?.[language] ?? (assessment?.comparability?.status === 'confounded'
    ? t('Compare again with the same model and decoding settings before attributing the change to the prompt.', '请在相同模型与解码条件下再比较，再判断差异是否由提示词引起。')
    : coverage?.status !== 'complete'
    ? t('Inspect failed and missing outputs before relying on the comparison. Uncertain requests are retained for review.', '先查看失败与缺失输出，再据此判断。结果不明的请求会保留待核对。')
    : assessment?.effect?.status === 'improved'
    ? t('Review the changed examples and costs before adopting the candidate. Your original prompt is preserved.', '结合变化样本与成本决定是否采用候选；原提示词已保存。')
    : t('The evidence does not yet establish an improvement. Inspect the examples, revise the prompt, or evaluate more independent items.', '现有证据尚不能确定改进有效。可查看样本、修改提示词，或增加独立评估题。'));

  return <div className="experiment-page">
    <header className="experiment-hero"><span className="eyebrow">PROMPTCONTROLLAB / EXPERIMENTS</span>
      <h1>{t('A better prompt starts with evidence.', '让提示词的改进有据可依。')}</h1>
      <p>{t('Compare versions, explore improvements, and understand what changed.', '比较版本、探索改进，并理解结果为什么发生变化。')}</p>
      <button className="button demo-button" onClick={() => void start(true)} disabled={busy || !writeEnabled}><FlaskConical size={17} />{t('Try the offline example', '先体验离线样例')}<ArrowRight size={16} /></button>
    </header>
    {error && <div role="alert" className="experiment-alert error">{error}</div>}
    {!writeEnabled && <div role="status" className="experiment-alert">{t('This public preview is read-only. Install PromptControlLab locally to run, import, or optimize your prompts.', '当前公开预览只读。请在本地安装 PromptControlLab，运行评测、导入结果或优化提示词。')}</div>}
    {notice && <div role="status" className="experiment-alert">{notice === 'offline_demo' ? t('Offline demonstration: preset outputs, no model calls. These scores illustrate the workflow.', '离线演示使用预置输出，没有调用模型；分数仅用于展示流程。') : t('Prompt asset loaded. Add evaluation data and run a comparison.', '提示词资产已载入。请配置任务数据并进行实际评测。')}</div>}
    <div className="experiment-tabs" aria-label={t('Workflow', '工作方式')}>{[['run', 'Run evaluation', '实际评测'], ['import', 'Import results', '导入结果'], ['optimize', 'Find a better prompt', '自动优化']].map(([id, en, cn]) => <button key={id} className={operation === id ? 'active' : ''} onClick={() => { setOperation(id); setError(''); }}>{t(en, cn)}</button>)}</div>
    <div className="experiment-columns">
      <section className="card experiment-form"><h2><span className="step-number">1</span>{t('Your task and prompts', '任务与提示词')}</h2>
        <label>{t('Experiment name', '实验名称')}<input value={name} onChange={e => setName(e.target.value)} /></label>
        <div className="prompt-pair"><label>{t('Original prompt', '原提示词')}<textarea rows={5} value={baseline} onChange={e => setBaseline(e.target.value)} /></label>
        {operation !== 'optimize' && <label>{t('Candidate prompt', '候选提示词')}<textarea rows={5} value={candidate} onChange={e => setCandidate(e.target.value)} /></label>}</div>
        {operation === 'optimize' && <p className="field-help">{t('Search develops candidates on training data, selects on validation data, then compares the locked best on withheld data.', '搜索使用训练数据生成候选、验证数据选择候选，锁定后才在留出数据上比较。')}</p>}
        <label>{t('Scoring', '评分方式')}<select value={metric} onChange={e => setMetric(e.target.value)}>{[['exact_match', 'Exact answer', '精确答案'], ['contains', 'Contains answer', '包含答案'], ['numeric_tolerance:0.001', 'Numeric tolerance · 0.001', '数值容差 · 0.001'], ['classification_accuracy', 'Classification accuracy', '分类准确率'], ['format_error', 'Format errors · lower is better', '格式错误 · 越低越好']].map(([value,en,cn]) => <option key={value} value={value}>{t(en,cn)}</option>)}</select></label>
        <details><summary>{t('Dataset · CSV / JSONL / JSON', '任务数据 · CSV / JSONL / JSON')}</summary>
          <input aria-label={t('Upload dataset', '上传任务数据')} type="file" accept=".csv,.json,.jsonl" onChange={e => void readFile(e.target.files?.[0], (text, fmt) => { setDataText(text); setFormat(fmt); setSyntheticData(false); })} />
          <select aria-label={t('Dataset format', '数据格式')} value={format} onChange={e => setFormat(e.target.value)}><option>jsonl</option><option>csv</option><option>json</option></select>
          <textarea aria-label={t('Dataset content', '任务数据内容')} rows={7} value={dataText} onChange={e => setDataText(e.target.value)} spellCheck={false} />
          <div className="three-fields">{(['id', 'input', 'expected'] as const).map(field => <label key={field}>{field}<input value={mapping[field]} onChange={e => setMapping({ ...mapping, [field]: e.target.value })} /></label>)}</div>
          <p className="field-help">{t('Map your ID, input and expected-answer columns. The starter data is a synthetic example.', '映射编号、输入与期望答案列。初始数据为合成示例。')}</p>
          <label className="checkbox-field"><input type="checkbox" checked={syntheticData} onChange={e => setSyntheticData(e.target.checked)} />{t('Mark dataset as synthetic / teaching example', '将数据标记为合成／教学样例')}</label>
        </details>
      </section>
      <section className="card experiment-form"><h2><span className="step-number">2</span>{operation === 'import' ? t('Existing outputs', '已有输出') : t('Model and budget', '模型与预算')}</h2>
      {operation === 'import' ? (['baseline', 'candidate'] as const).map(arm => <div key={arm} className="import-arm"><label>{arm === 'baseline' ? t('Original outputs', '原版本输出') : t('Candidate outputs', '候选版本输出')}
        <input type="file" accept=".json,.jsonl,.csv" onChange={e => void readFile(e.target.files?.[0], (text, fmt) => { setImportText(current => ({ ...current, [arm]: text })); void normalize(arm, text, fmt); })} />
        <textarea rows={3} value={importText[arm]} onChange={e => { setImportText(current => ({ ...current, [arm]: e.target.value })); setImports(current => ({ ...current, [arm]: undefined })); }} placeholder={'[{"id":"example-1","output":"positive"}]'} /></label>
        <label>{t('Prompt ID in export · optional', '导出中的提示词 ID · 可选')}<input value={importPrompt[arm]} onChange={e => { setImportPrompt(current => ({ ...current, [arm]: e.target.value })); setImports(current => ({ ...current, [arm]: undefined })); }} /></label>
        <button className="button" disabled={!writeEnabled} onClick={() => void normalize(arm)}>{t('Read import', '读取导入')}</button>
        {imports[arm] && <p className="field-help">{imports[arm]?.kind === 'predictions' ? `${imports[arm]?.predictions.length} ${t('outputs ready', '条输出已就绪')}` : imports[arm]?.kind === 'assets' ? t('Prompt asset — evaluation required', '提示词资产：需要评测') : t('Aggregate metrics — descriptive only', '汇总指标：仅描述性比较')}</p>}
        {imports[arm]?.warnings?.map((warning: string) => <p className="field-help" key={warning}>{warning.startsWith('Spreadsheet-safe CSV') ? t(warning, '为防止电子表格执行公式，CSV 可能对文本加了转义。需要精确重放时请导入 records.json。') : warning}</p>)}
        {imports[arm]?.kind === 'aggregate' && <pre>{JSON.stringify(imports[arm]?.metrics, null, 2)}</pre>}
        {imports[arm]?.kind === 'assets' && <><select aria-label={t('Choose prompt asset', '选择提示词资产')} onChange={e => { const content = imports[arm]?.assets?.[Number(e.target.value)]?.content; if (typeof content === 'string') (arm === 'baseline' ? setBaseline : setCandidate)(content); }}>{imports[arm]?.assets?.map((asset: Json, i: number) => <option key={asset.id ?? i} value={i}>{asset.title || asset.id || `${i + 1}`}</option>)}</select><button className="button" onClick={() => setOperation('run')}>{t('Evaluate this prompt', '配置此提示词的评测')}</button></>}
      </div>) : <>
        <div className="two-fields"><label>{t('Provider', '提供方')}<select value={provider} onChange={e => setProvider(e.target.value)}>{['openai-compatible', 'openai', 'anthropic', 'gemini', 'deepseek', 'qwen', 'kimi'].map(value => <option key={value}>{value}</option>)}</select></label>
        <label>{t('Model ID', '模型名称')}<input value={model} onChange={e => setModel(e.target.value)} placeholder={t('Enter your model ID', '填写明确的模型名称')} /></label></div>
        <label>{t('API key · this session only', 'API 密钥 · 仅当前会话')}<input type="password" autoComplete="off" value={key} onChange={e => setKey(e.target.value)} placeholder={t('Leave empty to use an environment variable', '已有环境变量时可留空')} /></label>
        <details><summary>{t('Endpoint and advanced model settings', '端点与模型高级设置')}</summary>
          <label>{t('Base URL', 'API 地址')}<input value={baseUrl} onChange={e => setBaseUrl(e.target.value)} placeholder="https://…/v1" /></label>
          <label>{t('Credential environment variable', '凭据环境变量名')}<input value={keyEnv} onChange={e => setKeyEnv(e.target.value)} /></label>
          {provider === 'anthropic' && <label>{t('Authentication', '鉴权方式')}<select value={authScheme} onChange={e => setAuthScheme(e.target.value)}><option value="api_key">API key</option><option value="bearer">Bearer token</option></select></label>}
          {provider === 'deepseek' && <label>{t('Thinking mode', '思考模式')}<select value={thinking} onChange={e => setThinking(e.target.value)}><option value="">{t('Provider default', '提供方默认')}</option><option value="disabled">{t('Disabled', '关闭')}</option><option value="enabled">{t('Enabled · included in output budget', '开启 · 计入输出预算')}</option></select></label>}
          <label>{t('Candidate model · blank uses same model', '候选模型 · 留空使用同一模型')}<input value={candidateModel} onChange={e => setCandidateModel(e.target.value)} /></label>
          <label>{t('Output tokens per call', '单次输出 token 上限')}<input type="number" min={1} value={outputLimit} onChange={e => setOutputLimit(+e.target.value)} /></label>
          {operation === 'optimize' && <label>{t('Reflection model · blank uses same model', '反思模型 · 留空使用同一模型')}<input value={reflectionModel} onChange={e => setReflectionModel(e.target.value)} /></label>}
        </details>
        <div className="three-fields"><label>{t('Max calls', '调用次数上限')}<input type="number" min={1} value={calls} onChange={e => setCalls(+e.target.value)} /></label><label>{t('Output tokens', '总输出 token')}<input type="number" min={1} value={tokens} onChange={e => setTokens(+e.target.value)} /></label><label>{t('Time · seconds', '时间 · 秒')}<input type="number" min={1} value={seconds} onChange={e => setSeconds(+e.target.value)} /></label></div>
        {operation === 'optimize' && <label>{t('Search rounds', '搜索轮数')}<input type="number" min={1} max={5} value={rounds} onChange={e => setRounds(+e.target.value)} /></label>}
        <details><summary>{t('Optional prices and amount limit', '可选单价与金额上限')}</summary><div className="three-fields"><label>{t('Input / million tokens', '输入／百万 token')}<input type="number" min={0} value={inputPrice} onChange={e => setInputPrice(e.target.value)} /></label><label>{t('Output / million tokens', '输出／百万 token')}<input type="number" min={0} value={outputPrice} onChange={e => setOutputPrice(e.target.value)} /></label><label>{t('Amount limit', '金额上限')}<input type="number" min={0} value={maxCost} onChange={e => setMaxCost(e.target.value)} /></label></div><p className="field-help">{t('Use one currency for every value. Prices apply to task and reflection calls; use conservative rates when models differ.', '所有金额使用同一币种。单价同时适用于评测与反思调用；模型不同时请使用保守单价。')}</p></details>
        <p className="field-help">{t('Task and reflection calls share these limits. Final comparison capacity is reserved. Currency costs stay unknown until prices are configured.', '评测与反思共用预算，并预留最终比较额度。未配置价格时，金额费用显示为未知。')}</p>
      </>}
        <button className="button primary experiment-start" disabled={!writeEnabled || busy || (operation !== 'import' && !model.trim())} onClick={() => void start()}>{operation === 'optimize' ? <WandSparkles size={18} /> : <Play size={18} />}{busy ? t('Preparing…', '准备中…') : operation === 'optimize' ? t('Start bounded search', '开始有界搜索') : t('Start comparison', '开始比较')}<ArrowRight size={17} /></button>
      </section>
    </div>
    <section className="card experiment-results"><div className="section-heading"><div><span className="eyebrow">RESULTS</span><h2>{t('What does the evidence say?', '证据说明了什么？')}</h2></div>
      <select aria-label={t('Select experiment', '选择实验')} value={selected} onChange={e => { setSelected(e.target.value); setJob(undefined); setRecords(undefined); }}><option value="">{t('Choose an experiment', '选择一个实验')}</option>{jobs.map(item => <option key={item.id} value={item.id}>{item.name || item.id} · {label(item.status)}</option>)}</select></div>
      {!job ? <div className="experiment-empty"><FlaskConical size={30} /><p>{t('Your first comparison will appear here.', '第一次比较的结果会显示在这里。')}</p><span>{t('Start with the offline example to explore without an API key.', '可以先体验离线样例，无需 API 密钥。')}</span></div> : <>
        <div className="experiment-jobbar"><strong>{job.name}</strong><span className="badge">{label(job.status)}</span>{!finalStates.has(job.status) ? <button className="button" onClick={() => void manage('cancel')}><Square size={14} />{t('Cancel', '取消')}</button> : !['completed', 'completed_with_errors'].includes(job.status) && <button className="button" onClick={() => void manage('resume')}>{t('Resume unfinished work', '恢复未完成部分')}</button>}</div>
        {job.stop_reason && <p className="field-help">{label(job.stop_reason)}</p>}
        {job.progress && <div className="experiment-progress"><span>{t('Stage', '阶段')}: {label(job.progress.stage)} · {t('Finished samples', '已完成样本')}: {job.progress.completed} / {job.progress.expected_total ?? '—'} · {t('Errors', '错误')}: {job.progress.errors} · {t('In flight', '请求中')}: {job.progress.in_flight}</span></div>}
        {job.status === 'completed_with_errors' && <button className="button" onClick={() => void manage('resume', true)}>{t('Retry safely rejected requests', '重试明确被拒绝的请求')}</button>}
        {job.budget && <div className="experiment-progress"><span>{t('Calls', '调用')}: {job.budget.calls} / {job.budget.limits?.max_calls} · {t('Output tokens charged', '计入预算的输出 token')}: {job.budget.charged_output_tokens} / {job.budget.limits?.max_output_tokens} · {t('Amount', '金额')}: {assessment?.cost?.status === 'known' ? number(job.budget.known_cost) : t('Unknown', '未知')}</span><progress value={job.budget.calls ?? 0} max={job.budget.limits?.max_calls || 1} /></div>}
        <div className="experiment-metrics">{[
          [t('Comparison conditions', '比较条件'), label(assessment?.comparability?.status)],
          [t('Effect', '效果判断'), label(assessment?.effect?.status)],
          [t('Matched items', '配对完成'), coverage ? `${coverage.matched} / ${coverage.total}` : '—'],
          [t('Mean change', '平均变化'), number(stats?.mean_delta)],
        ].map(([title, value]) => <div key={title}><span>{title}</span><strong>{value}</strong></div>)}</div>
        {assessment && <p className="field-help">{t('Saved metric', '本次评分方式')}: {label(assessment.comparability?.metric)} · {assessment.effect?.direction === 'lower_is_better' ? t('Lower is better; a negative change favors the candidate.', '越低越好；负向变化有利于候选。') : t('Higher is better; a positive change favors the candidate.', '越高越好；正向变化有利于候选。')}</p>}
        {stats?.bootstrap_ci && <p>{t('95% interval', '95% 区间')}: [{stats.bootstrap_ci.map(number).join(', ')}]</p>}
        {stats?.holm_adjusted_p_value != null && <p className="field-help">{t('Adjusted p-value', '校正后 p 值')}: {number(stats.holm_adjusted_p_value)} · {t('An improvement requires a favorable interval and a supported paired test; a small sample can remain uncertain.', '支持提升需要区间方向支持改进且成对检验通过；样本较少时仍可能无法确定。')}</p>}
        {practical && <div className="experiment-practical"><h3>{t('Quality, time and cost', '质量、耗时与成本')}</h3><p className="field-help">{practical.evidence_range?.[language]}</p><div className="experiment-table-wrap"><table><thead><tr><th>{t('Measure', '指标')}</th><th>{t('Original', '原版本')}</th><th>{t('Candidate', '候选版本')}</th><th>{t('Change', '变化')}</th></tr></thead><tbody>{[
          ['score_mean', t('Mean score', '平均分数')], ['mean_latency_ms', t('Mean latency · ms', '平均耗时 · 毫秒')], ['mean_input_tokens', t('Input tokens / item', '每题输入 token')], ['mean_output_tokens', t('Output tokens / item', '每题输出 token')],
        ].map(([field, title]) => <tr key={field}><th>{title}</th><td>{number(practical.baseline?.[field])}</td><td>{number(practical.candidate?.[field])}</td><td>{number(practical.delta?.[field])}</td></tr>)}<tr><th>{t('Known amount', '已知金额')}</th>{['baseline', 'candidate'].map(arm => <td key={arm}>{practical[arm]?.cost_status === 'known' ? number(practical[arm]?.known_cost) : t('Unknown / partial', '未知／不完整')}</td>)}<td>{number(practical.delta?.cost)}</td></tr></tbody></table></div><p className="field-help">{t('Quality errors (parse / format / empty)', '输出错误（解析／格式／空输出）')}: {['baseline', 'candidate'].map(arm => `${label(arm)} ${practical[arm]?.parse_error_count ?? 0} / ${practical[arm]?.format_error_count ?? 0} / ${practical[arm]?.empty_output_count ?? 0}`).join(' · ')}. {t('Missing observations stay unknown; zero is a recorded value.', '缺失观测保留为未知，零值按实际记录展示。')}</p></div>}
        {assessment?.comparability?.limitations?.map((message: string) => <p key={message} className="field-help">{limitation(message)}</p>)}
        {assessment && <p className="experiment-next"><strong>{t('Next step', '下一步')}</strong> · {nextAction}</p>}
        {job.optimization && <details open><summary>{t('Search history and selected candidate', '搜索记录与选中候选')}</summary><p className="field-help">{t('Validation selects the candidate. The effect above is the separate withheld comparison; completion alone does not establish an improvement.', '验证集用于选候选，上方效果来自单独的留出比较；搜索完成本身不代表改进有效。')}</p><table><thead><tr><th>{t('Round', '轮次')}</th><th>{t('Validation score', '验证分数')}</th><th>{t('Selection', '选择')}</th></tr></thead><tbody>{job.optimization.history?.map((entry: Json) => <tr key={entry.id}><td>{entry.round}</td><td>{number(entry.validation_score)}</td><td>{entry.id === job.optimization.best_id ? t('Selected', '已选中') : entry.validation_complete ? t('Compared', '已比较') : t('Incomplete', '未完成')}</td></tr>)}</tbody></table><pre>{job.optimization.candidate?.prompt}</pre><p className="field-help">{t('Stop reason', '停止原因')}: {label(job.optimization.stop_reason)}</p></details>}
        <div className="experiment-downloads">{finalStates.has(job.status) && [['experiment.zip', t('Portable bundle', '完整结果包')], [`report.${language}.html`, t('Readable report', '可读报告')], ['records.csv', 'CSV']].map(([file, title]) => <a key={file} className="button" href={`/api/experiments/${selected}/artifacts/${file}`}><Download size={15} />{title}</a>)}</div>
        {allRows.length > 0 && <details><summary>{t('Inspect individual outputs', '查看逐条输出')} ({allRows.length})</summary><div className="experiment-table-wrap"><table><thead><tr>{['ID', t('Version', '版本'), t('Status', '状态'), t('Score', '分数'), t('Output', '输出')].map(item => <th key={item}>{item}</th>)}</tr></thead><tbody>{allRows.slice(0,200).map((row: Json) => <tr key={`${row.arm}-${row.id}`}><td>{row.id}</td><td>{row.arm}</td><td>{label(row.status)}</td><td>{row.score ?? '—'}</td><td>{row.output}</td></tr>)}</tbody></table></div></details>}
      </>}
    </section>
  </div>;
}
