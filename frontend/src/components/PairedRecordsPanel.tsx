import { useMemo, useState } from 'react';
import type { Json } from '../experimentApi';

type Pair = { id: string; baseline?: Json; candidate?: Json };
type Review = { expected: Map<string, string>; onChange: (id: string, expected: string | undefined) => void; disabled: boolean };

export function PairedRecordsPanel({ records, language, review }: { records: Json; language: 'en' | 'zh'; review?: Review }) {
  const zh = language === 'zh';
  const t = (en: string, cn: string) => zh ? cn : en;
  const [status, setStatus] = useState('all');
  const [slice, setSlice] = useState('all');
  const [page, setPage] = useState(0);
  const pageSize = 50;
  const pairs = useMemo(() => {
    const map = new Map<string, Pair>();
    for (const arm of ['baseline', 'candidate'] as const) for (const row of (records[arm] ?? []) as Json[]) {
      const current = map.get(String(row.id)) ?? { id: String(row.id) };
      current[arm] = row;
      map.set(String(row.id), current);
    }
    return [...map.values()].sort((a, b) => {
      const left = Number(a.id.split('-').pop());
      const right = Number(b.id.split('-').pop());
      return Number.isFinite(left) && Number.isFinite(right) ? left - right : a.id.localeCompare(b.id);
    });
  }, [records]);
  const filtered = pairs.filter(pair => {
    const left = pair.baseline;
    const right = pair.candidate;
    if (slice !== 'all' && (left?.slice ?? right?.slice) !== slice) return false;
    if (status === 'missing_candidate') return !right;
    if (status !== 'all' && left?.status !== status && right?.status !== status) return false;
    return true;
  });
  const pageRows = filtered.slice(page * pageSize, (page + 1) * pageSize);
  const slices = [...new Set(pairs.map(pair => pair.baseline?.slice ?? pair.candidate?.slice ?? 'default'))];
  return <div className="paired-records">
    <div className="paired-controls">
      <label>{t('Status', '状态')}<select value={status} onChange={e => { setStatus(e.target.value); setPage(0); }}>
        <option value="all">{t('All', '全部')}</option>
        <option value="completed">{t('Completed', '已完成')}</option>
        <option value="service_error">{t('Service error', '服务错误')}</option>
        <option value="missing_candidate">{t('Missing candidate', '候选缺失')}</option>
      </select></label>
      <label>{t('Slice', '切片')}<select value={slice} onChange={e => { setSlice(e.target.value); setPage(0); }}>
        <option value="all">{t('All', '全部')}</option>{slices.map(value => <option key={value} value={value}>{value}</option>)}
      </select></label>
      <span>{t('Showing', '显示')} {pageRows.length} / {filtered.length} · {t('Total pairs', '总配对')} {pairs.length}</span>
      <button disabled={page === 0} onClick={() => setPage(page - 1)}>{t('Previous', '上一页')}</button>
      <button disabled={(page + 1) * pageSize >= filtered.length} onClick={() => setPage(page + 1)}>{t('Next', '下一页')}</button>
    </div>
    <div className="experiment-table-wrap"><table><thead><tr><th>ID</th><th>{t('Original', '原版本')}</th><th>{t('Candidate', '候选版本')}</th>{review && <th>{t('Review for export', '复核导出')}</th>}</tr></thead><tbody>
      {pageRows.map(pair => <tr key={pair.id}><td>{pair.id}</td><td>{pair.baseline?.output ?? '—'}</td><td>{pair.candidate?.output ?? t('Missing', '缺失')}</td>{review && <td>
        <input type="checkbox" aria-label={t(`Select ${pair.id} for export`, `选择 ${pair.id} 导出`)} checked={review.expected.has(pair.id)} disabled={review.disabled} onChange={e => review.onChange(pair.id, e.target.checked ? String(pair.baseline?.expected ?? pair.candidate?.expected ?? '') : undefined)} />
        {review.expected.has(pair.id) && <label>{t(`Expected answer for ${pair.id}`, `${pair.id} 的期望答案`)}<textarea value={review.expected.get(pair.id)} disabled={review.disabled} onChange={e => review.onChange(pair.id, e.target.value)} /></label>}
      </td>}</tr>)}
    </tbody></table></div>
  </div>;
}
