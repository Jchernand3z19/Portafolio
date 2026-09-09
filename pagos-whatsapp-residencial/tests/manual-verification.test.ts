import { describe, expect, it } from 'vitest';
import { buildManualVerificationUpdate, canManuallyVerify } from '@/src/services/manual-verification';
import type { PaymentRecord } from '@/src/domain/types';

const payment: PaymentRecord = {
  id: 'pay-demo', createdAt: '2026-09-01T00:00:00.000Z', updatedAt: '2026-09-01T00:00:00.000Z', sourceMessageId: 'msg-demo',
  phone: '+50400000000', bank: 'BAC Honduras', amount: 150, transactionDate: '2026-09-01', reference: 'DEMO-REF-001',
  stage: 1, block: 4, house: 18, period: '2026-08', status: 'PENDIENTE_VERIFICACION', fileHash: 'demo-hash',
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

  it('requires explicit reviewed mode for an EN_REVISION payment', () => {
    const reviewed = { ...payment, status: 'EN_REVISION' as const, reviewReason: 'bank_reference_reused' };
    expect(canManuallyVerify(reviewed)).toBe(false);
    expect(canManuallyVerify(reviewed, true)).toBe(true);
    expect(buildManualVerificationUpdate(reviewed, new Date('2026-09-09T20:30:00.000Z'), true).verificationSource)
      .toBe('manual_admin_bank_check_after_review');
  });

  it('does not allow incomplete EBC or duplicate payments to be verified', () => {
    expect(canManuallyVerify({ ...payment, stage: undefined, status: 'ESPERANDO_RESPUESTA' })).toBe(false);
    expect(canManuallyVerify({ ...payment, status: 'DUPLICADO' })).toBe(false);
  });
});
