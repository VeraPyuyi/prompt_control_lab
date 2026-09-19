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
  request.mockReset();
  request.mockImplementation(async (path, payload) => {
    if (path === '/api/experiments') return payload ? job : { experiments: [job] };
    if (path.endsWith('/records.json')) return { baseline: [{ id: 'a', score: 0, output: 'wrong', status: 'completed' }], candidate: [] };
    return job;
  });
});
describe('experiment workspace', () => {
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
  it('does not allow model actions in the public read-only preview', () => {
    render(<ExperimentPage language="en" writeEnabled={false} />);
    expect(screen.getByRole('button', { name: /Try the offline example/ })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Start comparison' })).toBeDisabled();
    expect(screen.getByText(/public preview is read-only/)).toBeInTheDocument();
  });
});
