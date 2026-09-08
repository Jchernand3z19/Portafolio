import { describe, expect, it } from 'vitest';
import { DEMO_HOMES, DEMO_PAYMENTS, DEMO_PERIOD } from '@/src/demo/data';
import { buildDashboardSnapshot } from '@/src/services/dashboard';
import { MemoryPaymentStore } from '@/src/storage/memory';

describe('dashboard snapshot', () => {
  it('keeps duplicate payments out of collection totals', async () => {
    const store = new MemoryPaymentStore({ homes: DEMO_HOMES, payments: DEMO_PAYMENTS });
    const snapshot = await buildDashboardSnapshot(store, DEMO_PERIOD);
    expect(snapshot.totalHomes).toBe(12);
    expect(snapshot.duplicates).toHaveLength(1);
    expect(snapshot.receivedAmount).toBe(750);
    expect(snapshot.verifiedAmount).toBe(300);
    expect(snapshot.unidentifiedAmount).toBe(150);
  });
});
