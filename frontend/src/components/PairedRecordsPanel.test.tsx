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
