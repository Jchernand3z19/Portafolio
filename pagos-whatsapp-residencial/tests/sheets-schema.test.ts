import { describe, expect, it } from 'vitest';
import type { PaymentRecord } from '@/src/domain/types';
import { PAYMENT_HEADERS, paymentFromRow, paymentToRow } from '@/src/storage/sheets-schema';

const payment: PaymentRecord = {
  id: 'pay-demo',
  createdAt: '2026-09-08T12:00:00.000Z',
  updatedAt: '2026-09-08T12:00:00.000Z',
  sourceMessageId: 'msg-demo',
  phone: '50400000001',
  bank: 'BAC Honduras',
  amount: 150,
  reference: 'DEMOREF000001',
  block: 4,
  house: 18,
  period: '2026-09',
  status: 'DUPLICADO',
  fileHash: 'hash-demo',
  duplicateOf: 'pay-original',
  duplicateReason: 'bank_reference',
};

describe('Google Sheets payment schema', () => {
  it('round-trips duplicate trace fields without shifting columns', () => {
    const row = paymentToRow(payment);
    expect(row).toHaveLength(PAYMENT_HEADERS.length);
    expect(PAYMENT_HEADERS[22]).toBe('duplicate_reason');
    expect(paymentFromRow(row)).toMatchObject({
      id: payment.id,
      status: 'DUPLICADO',
      duplicateOf: 'pay-original',
      duplicateReason: 'bank_reference',
    });
  });
});
