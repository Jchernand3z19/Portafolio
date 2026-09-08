import { describe, expect, it } from 'vitest';
import type { PaymentRecord } from '@/src/domain/types';
import { reconcilePendingPayments } from '@/src/services/reconciliation';
import { MemoryPaymentStore } from '@/src/storage/memory';

function payment(overrides: Partial<PaymentRecord> = {}): PaymentRecord {
  return {
    id: 'pay-1', createdAt: '2026-09-08T10:00:00.000Z', updatedAt: '2026-09-08T10:00:00.000Z', sourceMessageId: 'msg-1', phone: '+50400000001',
    bank: 'BAC Honduras', amount: 150, transactionDate: '2026-09-08', reference: 'BANKREF001', block: 4, house: 18, period: '2026-09', status: 'PENDIENTE_VERIFICACION', fileHash: 'hash-1',
    ...overrides,
  };
}

describe('bank reconciliation', () => {
  it('verifies only an exact bank + reference + amount match', async () => {
    const store = new MemoryPaymentStore({ payments: [payment()] });
    const result = await reconcilePendingPayments(store, [{ bank: 'BAC Honduras', reference: 'BANKREF001', amount: 150, transactionDate: '2026-09-08' }], 'synthetic-bank-file', new Date('2026-09-08T12:00:00.000Z'));
    expect(result.verified).toBe(1);
    const updated = await store.getPayment('pay-1');
    expect(updated?.status).toBe('VERIFICADO');
    expect(updated?.verificationSource).toBe('synthetic-bank-file');
  });

  it('marks a missing bank movement as not found', async () => {
    const store = new MemoryPaymentStore({ payments: [payment()] });
    const result = await reconcilePendingPayments(store, [], 'synthetic-bank-file');
    expect(result.notFound).toBe(1);
    expect((await store.getPayment('pay-1'))?.status).toBe('NO_ENCONTRADO');
  });

  it('does not verify an ambiguous or date-conflicting transaction', async () => {
    const store = new MemoryPaymentStore({ payments: [payment()] });
    await reconcilePendingPayments(store, [{ bank: 'BAC Honduras', reference: 'BANKREF001', amount: 150, transactionDate: '2026-09-07' }], 'synthetic-bank-file');
    expect((await store.getPayment('pay-1'))?.status).toBe('EN_REVISION');
  });
});
