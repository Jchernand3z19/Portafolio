import { describe, expect, it } from 'vitest';
import { DEMO_HOMES, DEMO_PAYMENTS, DEMO_PERIOD } from '@/src/demo/data';
import type { PaymentRecord } from '@/src/domain/types';
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

  it('does not count a payment assigned outside the active housing master as a paid home', async () => {
    const external: PaymentRecord = {
      id: 'pay-external',
      createdAt: '2026-09-08T13:00:00.000Z',
      updatedAt: '2026-09-08T13:00:00.000Z',
      sourceMessageId: 'msg-external',
      phone: '50400000999',
      bank: 'BAC Honduras',
      amount: 150,
      reference: 'DEMOREF-EXTERNAL',
      block: 99,
      house: 99,
      period: DEMO_PERIOD,
      status: 'VERIFICADO',
      fileHash: 'hash-external',
    };
    const store = new MemoryPaymentStore({ homes: DEMO_HOMES, payments: [...DEMO_PAYMENTS, external] });
    const snapshot = await buildDashboardSnapshot(store, DEMO_PERIOD);
    expect(snapshot.totalHomes).toBe(12);
    expect(snapshot.paidHomes).toBeLessThanOrEqual(snapshot.totalHomes);
    expect(snapshot.receivedAmount).toBe(900);
    expect(snapshot.pendingAmount).toBe(1200);
    expect(snapshot.blocks.reduce((total, block) => total + block.collected, 0)).toBe(600);
  });
});
