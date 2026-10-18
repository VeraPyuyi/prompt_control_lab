import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ExperimentPage } from './ExperimentPage';
import { experimentRequest } from '../experimentApi';

vi.mock('../experimentApi', () => ({ experimentRequest: vi.fn() }));
const request = vi.mocked(experimentRequest);
const job = { id: 'example-job', name: 'Synthetic comparison', status: 'completed',
  assessment: { comparability: { status: 'declared_only', limitations: [] }, effect: { status: 'uncertain', statistics: { mean_delta: 0, bootstrap_ci: [-.1,.1] } }, coverage: { status: 'complete', total: 10, matched: 10 } } };
beforeEach(() => {
  vi.unstubAllGlobals();
  request.mockReset();
  request.mockImplementation(async (path, payload) => {
    if (path === '/api/experiments') return payload ? job : { experiments: [job] };
    if (path.endsWith('/records.json')) return { baseline: [{ id: 'a', score: 0, output: 'wrong', status: 'completed' }], candidate: [] };
    return job;
  });
});
describe('experiment workspace', () => {
  it('names legacy scoring accurately and offers versioned JSON checks', () => {
    render(<ExperimentPage language="en" />);
    expect(screen.getByRole('option', { name: 'Empty output check · lower is better' })).toHaveValue('format_error');
    expect(screen.getByRole('option', { name: 'Valid JSON · v1' })).toHaveValue('json_valid@1');
    expect(screen.getByRole('option', { name: 'JSON schema · v1' })).toHaveValue('json_schema@1');
  });
  it('offers explicit external score preservation with metric identity', async () => {
    render(<ExperimentPage language="en" />);
    await userEvent.click(screen.getByRole('button', { name: 'Import results' }));
    expect(screen.getByLabelText('Score mode')).toHaveValue('recompute');
    await userEvent.selectOptions(screen.getByLabelText('Score mode'), 'preserve');
    expect(screen.getByLabelText('External metric ID')).toBeInTheDocument();
    expect(screen.getByLabelText('Metric version')).toBeInTheDocument();
    expect(screen.getByLabelText('Reviewer')).toBeInTheDocument();
  });
  it('runs the offline example without collecting a key or calling a model', async () => {
    const user = userEvent.setup();
    render(<ExperimentPage language="en" />);
    expect(screen.getByRole('button', { name: 'Start comparison' })).toBeDisabled();
    await user.click(screen.getByRole('button', { name: /Try the offline example/ }));
    await waitFor(() => expect(request).toHaveBeenCalledWith('/api/experiments', expect.objectContaining({ operation: 'import', synthetic: true })));
    const spec = request.mock.calls.find(([path,payload]) => path === '/api/experiments' && payload)?.[1];
    expect(spec?.data).toHaveLength(10);
    expect(spec?.predictions.candidate).toHaveLength(10);
    expect(request.mock.calls.some(([path]) => path === '/api/credentials')).toBe(false);
    expect(await screen.findByText(/preset outputs, no model calls/)).toBeInTheDocument();
    expect(screen.getByText('0.000')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Portable bundle' })).toHaveAttribute('href', '/api/experiments/example-job/artifacts/experiment.zip');
  });
  it('explains bounded optimization in Chinese and keeps model selection explicit', async () => {
    const user = userEvent.setup();
    render(<ExperimentPage language="zh" />);
    await user.click(screen.getByRole('button', { name: '自动优化' }));
    expect(screen.getByText(/锁定后才在留出数据上比较/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '开始有界搜索' })).toBeDisabled();
    await user.type(screen.getByLabelText('模型名称'), 'chosen-model');
    expect(screen.getByRole('button', { name: '开始有界搜索' })).toBeEnabled();
    expect(screen.getByLabelText('搜索轮数')).toHaveValue(5);
  });
  it('keeps small positive p-values visible and explains the saved metric direction', async () => {
    const response = { ...job, assessment: { ...job.assessment, comparability: { ...job.assessment.comparability, metric: 'format_error' }, effect: { direction: 'lower_is_better', status: 'improved', statistics: { mean_delta: -.1, holm_adjusted_p_value: .00049975 } } } };
    request.mockImplementation(async (path, payload) => path === '/api/experiments' && !payload ? { experiments: [response] } : response);
    render(<ExperimentPage language="en" />);
    await userEvent.click(screen.getByRole('button', { name: /Try the offline example/ }));
    expect(await screen.findByText(/Lower is better; a negative change/)).toBeInTheDocument();
    expect(screen.getByText(/5.00e-4/)).toBeInTheDocument();
  });
  it.each(['completed', 'completed_with_errors', 'stopped', 'cancelled', 'failed'])('exports reviewed examples from a %s experiment without rerunning models', async status => {
    const saved = { ...job, status };
    const records = { baseline: [{ id: 'a', name: 'baseline', input: 'question', expected: 'yes', score: 0, output: 'wrong', status: 'completed' }], candidate: [] };
    const exported = { schema_version: 'experiment-failure-dataset/v1', version: 'failures-v2', source_experiment_id: job.id, usage: 'for_follow_up_experiments_only', records: [{ id: 'a', expected: 'reviewed answer', meta: { not_for_current_withheld_training: true } }] };
    const createUrl = vi.fn((_blob: Blob) => 'blob:failure-dataset');
    vi.stubGlobal('URL', class extends URL { static createObjectURL = createUrl; static revokeObjectURL = vi.fn(); });
    request.mockImplementation(async (path, payload) => {
      if (path === '/api/experiments' && !payload) return { experiments: [saved] };
      if (path.endsWith('/records.json')) return records;
      if (path.endsWith('/failure-dataset')) return exported;
      return saved;
    });
    const user = userEvent.setup();
    render(<ExperimentPage language="en" />);
    await screen.findByRole('option', { name: /Synthetic comparison/ });
    await user.selectOptions(screen.getByLabelText('Select experiment'), job.id);
    const button = await screen.findByRole('button', { name: 'Export failure dataset' });
    expect(button).toBeDisabled();
    await user.click(screen.getByLabelText('Select a for export'));
    const answer = screen.getByLabelText('Expected answer for a');
    expect(answer).toHaveValue('yes');
    await user.clear(answer);
    await user.type(answer, 'reviewed answer');
    await user.type(screen.getByLabelText('Dataset version'), 'failures-v2');
    expect(button).toBeDisabled();
    await user.click(screen.getByLabelText('I have reviewed the expected answers'));
    await user.click(button);
    const link = await screen.findByRole('link', { name: 'Download failure dataset' });
    expect(link).toHaveAttribute('href', 'blob:failure-dataset');
    expect(link).toHaveAttribute('download', 'failures-v2.json');
    expect(request.mock.calls.filter(([, payload]) => payload !== undefined)).toEqual([
      [`/api/experiments/${job.id}/failure-dataset`, { selected_ids: ['a'], confirmed_expected: { a: 'reviewed answer' }, version: 'failures-v2' }],
    ]);
    const blob = createUrl.mock.calls[0][0] as Blob;
    const content = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result));
      reader.onerror = reject;
      reader.readAsText(blob);
    });
    expect(JSON.parse(content)).toEqual(exported);
  });
  it('shows export errors and lets the user retry without rerunning the experiment', async () => {
    const records = { baseline: [{ id: 'a', name: 'baseline', expected: 'yes', output: 'wrong', status: 'completed' }], candidate: [] };
    request.mockImplementation(async (path, payload) => {
      if (path === '/api/experiments' && !payload) return { experiments: [job] };
      if (path.endsWith('/records.json')) return records;
      if (path.endsWith('/failure-dataset')) throw new Error('Dataset export failed');
      return job;
    });
    const user = userEvent.setup();
    render(<ExperimentPage language="en" />);
    await screen.findByRole('option', { name: /Synthetic comparison/ });
    await user.selectOptions(screen.getByLabelText('Select experiment'), job.id);
    const button = await screen.findByRole('button', { name: 'Export failure dataset' });
    await user.click(screen.getByLabelText('Select a for export'));
    await user.type(screen.getByLabelText('Dataset version'), 'failures-v2');
    await user.click(screen.getByLabelText('I have reviewed the expected answers'));
    await user.click(button);
    expect(await screen.findByRole('alert')).toHaveTextContent('Dataset export failed');
    expect(button).toBeEnabled();
    expect(screen.queryByRole('link', { name: 'Download failure dataset' })).not.toBeInTheDocument();
    expect(request.mock.calls.filter(([, payload]) => payload !== undefined).map(([path]) => path)).toEqual([`/api/experiments/${job.id}/failure-dataset`]);
    vi.stubGlobal('URL', class extends URL { static createObjectURL = vi.fn(() => 'blob:retry'); static revokeObjectURL = vi.fn(); });
    request.mockResolvedValueOnce({ version: 'failures-v2', records: [] });
    await user.click(button);
    expect(await screen.findByRole('link', { name: 'Download failure dataset' })).toHaveAttribute('href', 'blob:retry');
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(request.mock.calls.filter(([, payload]) => payload !== undefined).map(([path]) => path)).toEqual(Array(2).fill(`/api/experiments/${job.id}/failure-dataset`));
  });
  it('resets answer confirmation after edits and clears exports when switching experiments', async () => {
    const second = { ...job, id: 'second-job', name: 'Second comparison' };
    const revokeUrl = vi.fn();
    vi.stubGlobal('URL', class extends URL { static createObjectURL = vi.fn(() => 'blob:first'); static revokeObjectURL = revokeUrl; });
    request.mockImplementation(async (path, payload) => {
      if (path === '/api/experiments' && !payload) return { experiments: [job, second] };
      if (path.endsWith('/records.json')) return { baseline: [{ id: 'a', expected: 'yes', output: 'wrong' }], candidate: [] };
      if (path.endsWith('/failure-dataset')) return { version: 'failures-v2' };
      return path.includes(second.id) ? second : job;
    });
    const user = userEvent.setup();
    render(<ExperimentPage language="en" />);
    await screen.findByRole('option', { name: /Synthetic comparison/ });
    await user.selectOptions(screen.getByLabelText('Select experiment'), job.id);
    await user.click(await screen.findByLabelText('Select a for export'));
    await user.type(screen.getByLabelText('Dataset version'), 'failures-v2');
    const confirm = screen.getByLabelText('I have reviewed the expected answers');
    await user.click(confirm);
    await user.type(screen.getByLabelText('Expected answer for a'), '!');
    expect(confirm).not.toBeChecked();
    expect(screen.getByRole('button', { name: 'Export failure dataset' })).toBeDisabled();
    await user.click(confirm);
    await user.click(screen.getByRole('button', { name: 'Export failure dataset' }));
    await screen.findByRole('link', { name: 'Download failure dataset' });
    await user.selectOptions(screen.getByLabelText('Select experiment'), second.id);
    expect(await screen.findByLabelText('Select a for export')).not.toBeChecked();
    expect(screen.getByLabelText('Dataset version')).toHaveValue('');
    expect(screen.queryByRole('link', { name: 'Download failure dataset' })).not.toBeInTheDocument();
    expect(revokeUrl).toHaveBeenCalledWith('blob:first');
    expect(request.mock.calls.filter(([, payload]) => payload !== undefined).map(([path]) => path)).toEqual([`/api/experiments/${job.id}/failure-dataset`]);
  });
  it.each(['queued', 'running'])('does not offer failure export while an experiment is %s', async status => {
    const saved = { ...job, status };
    request.mockImplementation(async (path, payload) => path === '/api/experiments' && !payload ? { experiments: [saved] } : saved);
    render(<ExperimentPage language="en" />);
    await screen.findByRole('option', { name: /Synthetic comparison/ });
    await userEvent.selectOptions(screen.getByLabelText('Select experiment'), job.id);
    expect(await screen.findByRole('button', { name: 'Cancel' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Export failure dataset' })).not.toBeInTheDocument();
  });
  it('disables failure export in the public read-only preview', async () => {
    render(<ExperimentPage language="en" writeEnabled={false} />);
    await screen.findByRole('option', { name: /Synthetic comparison/ });
    await userEvent.selectOptions(screen.getByLabelText('Select experiment'), job.id);
    expect(await screen.findByRole('button', { name: 'Export failure dataset' })).toBeDisabled();
  });
  it('does not allow model actions in the public read-only preview', () => {
    render(<ExperimentPage language="en" writeEnabled={false} />);
    expect(screen.getByRole('button', { name: /Try the offline example/ })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Start comparison' })).toBeDisabled();
    expect(screen.getByText(/public preview is read-only/)).toBeInTheDocument();
  });
});
