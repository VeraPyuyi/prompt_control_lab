import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ResearchToolsPage } from './ResearchToolsPage';
import { experimentRequest, getSessionToken } from '../experimentApi';

vi.mock('../experimentApi', () => ({ experimentRequest: vi.fn(), getSessionToken: vi.fn() }));
const request = vi.mocked(experimentRequest);
const bundle = { id: 'bundle', title: 'Synthetic readout', synthetic: true,
  analyses: [{ kind: 'readout', input: 'readout.json' }], capabilities: [{ kind: 'readout', level: 'saved_measurements' }] };
const job = { id: 'job', status: 'completed', created_at: 1, spec: { analyses: bundle.analyses },
  progress: { completed: 1, total: 1, phase: 'completed' }, completed: { 'unit-000': {} } };
beforeEach(() => {
  request.mockReset(); vi.mocked(getSessionToken).mockResolvedValue('test-session');
  request.mockImplementation(async (path, payload) => {
    if (path.startsWith('/api/research-examples/')) return { synthetic: true };
    if (path === '/api/research-jobs') return payload ? job : { jobs: [] };
    return job;
  });
  vi.stubGlobal('fetch', vi.fn(async (url: string) => url.startsWith('/api/research-bundles')
    ? { ok: true, json: async () => bundle } : { ok: true, text: async () => '<html>Report</html>' }));
});
afterEach(() => vi.unstubAllGlobals());

describe('guided research workspace', () => {
  it.each(['en', 'zh'] as const)('imports, explains capabilities and runs in %s', async language => {
    const zh = language === 'zh';
    const user = userEvent.setup();
    render(<ResearchToolsPage language={language} />);
    await user.click(screen.getByRole('button', { name: zh ? '载入合成样例' : 'Load a synthetic example' }));
    expect(await screen.findByText(zh ? '重算所提供的测量' : 'Recompute the supplied measurements')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: zh ? '运行所选分析' : 'Run selected analyses' }));
    await waitFor(() => expect(request).toHaveBeenCalledWith('/api/research-jobs', {
      schema_version: 'pcl.research-analysis/v1', bundle_id: 'bundle', analyses: bundle.analyses,
    }));
    expect(await screen.findByRole('link', { name: zh ? '重放包' : 'Replay bundle' })).toHaveAttribute('href', '/api/research-jobs/job/artifacts/research.zip');
    expect(screen.getByText(zh ? /文件完整性不等于/ : /File integrity does not certify/)).toBeInTheDocument();
  });
  it('shows interrupted work and resumes without replacing its specification', async () => {
    request.mockImplementation(async path => path === '/api/research-jobs' ? { jobs: [{ ...job, status: 'interrupted' }] } : { ...job, status: 'queued' });
    render(<ResearchToolsPage language="en" />);
    await userEvent.click(await screen.findByRole('button', { name: /Readout & execution.*Interrupted/ }));
    await userEvent.click(screen.getByRole('button', { name: 'Resume' }));
    expect(request).toHaveBeenCalledWith('/api/research-jobs/job/resume', {});
  });
  it('keeps public preview read-only and avoids private history requests', () => {
    render(<ResearchToolsPage language="zh" writeEnabled={false} />);
    expect(screen.getByLabelText('上传科研证据')).toBeDisabled();
    expect(screen.getByText(/当前预览只读/)).toBeInTheDocument();
    expect(request).not.toHaveBeenCalled();
  });
});
