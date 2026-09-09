import { describe, expect, it } from 'vitest';
import { DEMO_HOMES, DEMO_PAYMENTS, DEMO_PERIOD } from '@/src/demo/data';
import type { HomeRecord, PaymentRecord } from '@/src/domain/types';
import { buildDashboardSnapshot } from '@/src/services/dashboard';
import { MemoryPaymentStore } from '@/src/storage/memory';

describe('dashboard snapshot', () => {
  it('keeps duplicate payments out of collection totals and only verified homes count as paid', async () => {
    const store = new MemoryPaymentStore({ homes: DEMO_HOMES, payments: DEMO_PAYMENTS });
    const snapshot = await buildDashboardSnapshot(store, DEMO_PERIOD);
    expect(snapshot.totalHomes).toBe(12);
    expect(snapshot.paidHomes).toBe(2);
    expect(snapshot.pendingHomes).toBe(10);
    expect(snapshot.duplicates).toHaveLength(1);
    expect(snapshot.receivedAmount).toBe(750);
    expect(snapshot.verifiedAmount).toBe(300);
    expect(snapshot.pendingAmount).toBe(1500);
    expect(snapshot.unidentifiedAmount).toBe(150);
  });

  it('does not count a payment assigned outside the active EBC master as a paid home', async () => {
    const external: PaymentRecord = {
      id: 'pay-external', createdAt: '2026-09-08T13:00:00.000Z', updatedAt: '2026-09-08T13:00:00.000Z',
      sourceMessageId: 'msg-external', phone: '50400000999', bank: 'BAC Honduras', amount: 150,
      reference: 'DEMOREF-EXTERNAL', stage: 9, block: 99, house: 99, period: DEMO_PERIOD, status: 'VERIFICADO', fileHash: 'hash-external',
    };
    const store = new MemoryPaymentStore({ homes: DEMO_HOMES, payments: [...DEMO_PAYMENTS, external] });
    const snapshot = await buildDashboardSnapshot(store, DEMO_PERIOD);
    expect(snapshot.totalHomes).toBe(12);
    expect(snapshot.paidHomes).toBe(2);
    expect(snapshot.receivedAmount).toBe(900);
    expect(snapshot.pendingAmount).toBe(1500);
    expect(snapshot.blocks.reduce((total, block) => total + block.collected, 0)).toBe(600);
  });

  it('keeps identical block and house numbers separate across stages', async () => {
    const homes: HomeRecord[] = [
      { id: 'e1', stage: 1, block: 4, house: 18, monthlyFee: 150, active: true },
      { id: 'e2', stage: 2, block: 4, house: 18, monthlyFee: 150, active: true },
    ];
    const paid: PaymentRecord = {
      id: 'p1', createdAt: '2026-09-01T00:00:00.000Z', updatedAt: '2026-09-01T00:00:00.000Z', sourceMessageId: 'm1',
      phone: '50400000000', bank: 'BAC Honduras', amount: 150, stage: 1, block: 4, house: 18,
      period: DEMO_PERIOD, status: 'VERIFICADO', fileHash: 'h1',
    };
    const snapshot = await buildDashboardSnapshot(new MemoryPaymentStore({ homes, payments: [paid] }), DEMO_PERIOD);
    expect(snapshot.paidHomes).toBe(1);
    expect(snapshot.blocks).toHaveLength(2);
  });

  it('keeps a received but unverified home pending', async () => {
    const homes: HomeRecord[] = [
      { id: 'e1', stage: 1, block: 1, house: 1, monthlyFee: 150, active: true },
    ];
    const received: PaymentRecord = {
      id: 'p-received', createdAt: '2026-09-01T00:00:00.000Z', updatedAt: '2026-09-01T00:00:00.000Z', sourceMessageId: 'm-received',
      phone: '50400000000', bank: 'BAC Honduras', amount: 150, stage: 1, block: 1, house: 1,
      period: DEMO_PERIOD, status: 'PENDIENTE_VERIFICACION', fileHash: 'h-received',
    };
    const snapshot = await buildDashboardSnapshot(new MemoryPaymentStore({ homes, payments: [received] }), DEMO_PERIOD);
    expect(snapshot.receivedAmount).toBe(150);
    expect(snapshot.verifiedAmount).toBe(0);
    expect(snapshot.paidHomes).toBe(0);
    expect(snapshot.pendingHomes).toBe(1);
    expect(snapshot.pendingAmount).toBe(150);
  });

  it('includes a deactivated home in historical periods covered by its end date', async () => {
    const formerHome: HomeRecord = {
      id: 'home-former', stage: 1, block: 9, house: 1, monthlyFee: 150, active: false,
      startDate: '2026-01-01', endDate: '2026-08-20',
    };
    const store = new MemoryPaymentStore({ homes: [formerHome] });
    expect((await buildDashboardSnapshot(store, '2026-08')).totalHomes).toBe(1);
    expect((await buildDashboardSnapshot(store, '2026-09')).totalHomes).toBe(0);
  });
});
