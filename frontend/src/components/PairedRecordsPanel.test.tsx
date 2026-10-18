import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { PairedRecordsPanel } from './PairedRecordsPanel';

function records(count: number) {
  const baseline = Array.from({ length: count }, (_, i) => ({ id: `task-${i + 1}`, name: 'baseline', status: 'completed', output: `b${i + 1}`, slice: i === count - 1 ? 'tail' : 'default' }));
  const candidate = Array.from({ length: count - 1 }, (_, i) => ({ id: `task-${i + 1}`, name: 'candidate', status: 'completed', output: `c${i + 1}`, slice: 'default' }));
  return { baseline, candidate };
}

describe('paired records panel', () => {
  it('filters by candidate score without treating missing scores as zero', async () => {
    const user = userEvent.setup();
    render(<PairedRecordsPanel language="en" records={{
      baseline: [],
      candidate: [
        { id: 'fail', output: 'failed output', score: 0, status: 'completed' },
        { id: 'partial', output: 'partial output', score: 0.25, status: 'completed' },
        { id: 'pass', output: 'passed output', score: 1, status: 'completed' },
        { id: 'unknown', score: null, status: 'missing' },
      ],
    }} />);
    await user.type(screen.getByLabelText('Candidate score at most'), '0.25');
    expect(screen.getByText('failed output')).toBeInTheDocument();
    expect(screen.getByText('partial output')).toBeInTheDocument();
    expect(screen.queryByText('passed output')).not.toBeInTheDocument();
    expect(screen.queryByText('unknown')).not.toBeInTheDocument();
    await user.clear(screen.getByLabelText('Candidate score at most'));
    expect(screen.getByText('passed output')).toBeInTheDocument();
    expect(screen.getByText('unknown')).toBeInTheDocument();
  });
  it('keeps paired rows aligned and can reach the last item beyond 200 records', async () => {
    const user = userEvent.setup();
    render(<PairedRecordsPanel language="en" records={records(500)} />);
    expect(screen.getByText(/Total pairs 500/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(screen.getByText('task-500')).toBeInTheDocument();
    expect(screen.getByText('b500')).toBeInTheDocument();
    expect(screen.getByText('Missing')).toBeInTheDocument();
  });
});
