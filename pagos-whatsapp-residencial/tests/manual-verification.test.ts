import { describe, expect, it } from 'vitest';
import { buildManualVerificationUpdate, canManuallyVerify } from '@/src/services/manual-verification';
import type { PaymentRecord } from '@/src/domain/types';

const payment: PaymentRecord = {
  id: 'pay-demo',
  createdAt: '2026-09-01T00:00:00.000Z',
  updatedAt: '2026-09-01T00:00:00.000Z',
  sourceMessageId: 'msg-demo',
  phone: '+50400000000',
  bank: 'BAC Honduras',
  amount: 150,
  transactionDate: '2026-09-01',
  reference: 'DEMO-REF-001',
  block: 4,
  house: 18,
  period: '2026-08',
  status: 'PENDIENTE_VERIFICACION',
  fileHash: 'demo-hash',
};

describe('manual verification', () => {
  it('allows an identified payment pending bank verification', () => {
    expect(canManuallyVerify(payment)).toBe(true);
  });

  it('records a manual bank check with timestamp and source', () => {
    const updated = buildManualVerificationUpdate(payment, new Date('2026-09-09T20:30:00.000Z'));
    expect(updated.status).toBe('VERIFICADO');
    expect(updated.verificationSource).toBe('manual_admin_bank_check');
    expect(updated.verifiedAt).toBe('2026-09-09T20:30:00.000Z');
  });

  it('does not allow unidentified or already duplicate payments to be verified with one click', () => {
    expect(canManuallyVerify({ ...payment, block: undefined, status: 'ESPERANDO_RESPUESTA' })).toBe(false);
    expect(canManuallyVerify({ ...payment, status: 'DUPLICADO' })).toBe(false);
  });
});
