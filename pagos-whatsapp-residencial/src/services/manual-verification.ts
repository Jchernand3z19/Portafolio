import type { PaymentRecord } from '@/src/domain/types';

export function canManuallyVerify(payment: PaymentRecord, includeReview = false): boolean {
  const statusAllowed = payment.status === 'PENDIENTE_VERIFICACION' || (includeReview && payment.status === 'EN_REVISION');
  return statusAllowed
    && payment.stage != null
    && payment.block != null
    && payment.house != null
    && payment.amount > 0;
}

export function buildManualVerificationUpdate(payment: PaymentRecord, now = new Date(), includeReview = false): PaymentRecord {
  if (!canManuallyVerify(payment, includeReview)) {
    throw new Error('payment_not_manually_verifiable');
  }

  const at = now.toISOString();
  return {
    ...payment,
    status: 'VERIFICADO',
    reviewReason: undefined,
    verificationSource: includeReview ? 'manual_admin_bank_check_after_review' : 'manual_admin_bank_check',
    verifiedAt: at,
    updatedAt: at,
  };
}
