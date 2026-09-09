import type { PaymentRecord } from '@/src/domain/types';

const NON_VERIFIABLE_REVIEW_REASONS = new Set([
  'amount_below_expected',
  'amount_above_expected',
  'service_period_already_has_payment',
  'reconciliation_movement_claimed_multiple_times',
  'bank_movement_already_used',
]);

export function canManuallyVerify(payment: PaymentRecord, includeReview = false): boolean {
  const statusAllowed = payment.status === 'PENDIENTE_VERIFICACION' || (includeReview && payment.status === 'EN_REVISION');
  if (!statusAllowed) return false;
  if (payment.reviewReason && NON_VERIFIABLE_REVIEW_REASONS.has(payment.reviewReason)) return false;

  return payment.stage != null
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
