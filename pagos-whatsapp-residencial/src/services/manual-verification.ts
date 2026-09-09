import type { PaymentRecord } from '@/src/domain/types';

const MANUAL_VERIFIABLE_STATUSES = new Set<PaymentRecord['status']>([
  'PENDIENTE_VERIFICACION',
]);

export function canManuallyVerify(payment: PaymentRecord): boolean {
  return MANUAL_VERIFIABLE_STATUSES.has(payment.status)
    && payment.stage != null
    && payment.block != null
    && payment.house != null
    && payment.amount > 0;
}

export function buildManualVerificationUpdate(payment: PaymentRecord, now = new Date()): PaymentRecord {
  if (!canManuallyVerify(payment)) {
    throw new Error('payment_not_manually_verifiable');
  }

  const at = now.toISOString();
  return {
    ...payment,
    status: 'VERIFICADO',
    reviewReason: undefined,
    verificationSource: 'manual_admin_bank_check',
    verifiedAt: at,
    updatedAt: at,
  };
}
