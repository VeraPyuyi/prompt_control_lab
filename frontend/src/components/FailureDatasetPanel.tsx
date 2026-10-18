import { useEffect, useRef, useState } from 'react';
import { Download } from 'lucide-react';
import { experimentRequest, type Json } from '../experimentApi';
import { PairedRecordsPanel } from './PairedRecordsPanel';

export function FailureDatasetPanel({ jobId, records, language, writeEnabled }: { jobId: string; records: Json; language: 'en' | 'zh'; writeEnabled: boolean }) {
  const t = (en: string, cn: string) => language === 'zh' ? cn : en;
  const [expected, setExpected] = useState(new Map<string, string>());
  const [version, setVersion] = useState('');
  const [reviewed, setReviewed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [download, setDownload] = useState<{ url: string; version: string }>();
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  useEffect(() => () => { if (download) URL.revokeObjectURL(download.url); }, [download]);

  function changeExpected(id: string, value: string | undefined) {
    setExpected(current => {
      const next = new Map(current);
      if (value === undefined) next.delete(id); else next.set(id, value);
      return next;
    });
    setReviewed(false); setDownload(undefined); setError('');
  }
  async function exportDataset() {
    if (!writeEnabled || busy || !reviewed || !expected.size || !version.trim()) return;
    setBusy(true); setError(''); setDownload(undefined);
    try {
      const result = await experimentRequest(`/api/experiments/${jobId}/failure-dataset`, {
        selected_ids: [...expected.keys()], confirmed_expected: Object.fromEntries(expected), version: version.trim(),
      });
      if (alive.current) setDownload({ url: URL.createObjectURL(new Blob([JSON.stringify(result, null, 2) + '\n'], { type: 'application/json' })), version: result.version });
    } catch (reason) {
      if (alive.current) setError(reason instanceof Error ? reason.message : String(reason));
    } finally { if (alive.current) setBusy(false); }
  }

  return <div>
    <PairedRecordsPanel records={records} language={language} review={{ expected, onChange: changeExpected, disabled: busy || !writeEnabled }} />
    <div className="experiment-form">
      <h3>{t('Export reviewed failures', '导出已复核的失败样本')}</h3>
      <p className="field-help">{t('Select examples above and confirm their expected answers. This creates a dataset for follow-up experiments and preserves withheld-data lineage.', '请在上方选择样本并复核期望答案。导出会创建用于后续实验的数据集，并保留留出数据来源。')}</p>
      <label>{t('Dataset version', '数据集版本')}<input value={version} disabled={busy || !writeEnabled} onChange={e => { setVersion(e.target.value); setDownload(undefined); setError(''); }} /></label>
      <label className="checkbox-field"><input type="checkbox" checked={reviewed} disabled={busy || !writeEnabled || !expected.size} onChange={e => { setReviewed(e.target.checked); setDownload(undefined); }} />{t('I have reviewed the expected answers', '我已复核期望答案')}</label>
      {error && <div role="alert" className="experiment-alert error">{error}</div>}
      <div className="experiment-downloads">
        <button className="button" disabled={!writeEnabled || busy || !reviewed || !expected.size || !version.trim()} onClick={() => void exportDataset()}><Download size={15} />{busy ? t('Exporting…', '导出中…') : t('Export failure dataset', '导出失败样本集')}</button>
        {download && <a className="button" href={download.url} download={`${download.version}.json`}><Download size={15} />{t('Download failure dataset', '下载失败样本集')}</a>}
      </div>
    </div>
  </div>;
}
