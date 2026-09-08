import type { PaymentRecord } from '@/src/domain/types';
import type { PaymentStore } from '@/src/storage/types';

export interface BankMovement {
  bank: string;
  reference: string;
  amount: number;
  transactionDate?: string;
}

export interface ReconciliationSummary {
  verified: number;
  notFound: number;
  review: number;
}

function normalized(value: string): string {
  return value.trim().toUpperCase().replace(/\s+/g, '');
}

export async function reconcilePendingPayments(
  store: PaymentStore,
  movements: readonly BankMovement[],
  source: string,
  now = new Date(),
): Promise<ReconciliationSummary> {
  const summary: ReconciliationSummary = { verified: 0, notFound: 0, review: 0 };
  const candidates = (await store.listPayments()).filter((payment) => payment.status === 'PENDIENTE_VERIFICACION' || payment.status === 'NO_ENCONTRADO');

  for (const payment of candidates) {
    let updated: PaymentRecord;
    if (!payment.reference) {
      updated = { ...payment, status: 'EN_REVISION', reviewReason: 'reference_missing_for_reconciliation', updatedAt: now.toISOString() };
      summary.review += 1;
    } else {
      const matches = movements.filter((movement) =>
        normalized(movement.bank) === normalized(payment.bank) &&
        normalized(movement.reference) === normalized(payment.reference!) &&
        movement.amount === payment.amount,
      );

      if (matches.length === 1) {
        const movement = matches[0];
        const dateConflict = payment.transactionDate && movement.transactionDate && payment.transactionDate !== movement.transactionDate;
        if (dateConflict) {
          updated = { ...payment, status: 'EN_REVISION', reviewReason: 'reconciliation_date_conflict', updatedAt: now.toISOString() };
          summary.review += 1;
        } else {
          updated = {
            ...payment,
            status: 'VERIFICADO',
            reviewReason: undefined,
            verificationSource: source,
            verifiedAt: now.toISOString(),
            updatedAt: now.toISOString(),
          };
          summary.verified += 1;
        }
      } else if (matches.length === 0) {
        updated = { ...payment, status: 'NO_ENCONTRADO', reviewReason: 'bank_movement_not_found', updatedAt: now.toISOString() };
        summary.notFound += 1;
      } else {
        updated = { ...payment, status: 'EN_REVISION', reviewReason: 'reconciliation_ambiguous', updatedAt: now.toISOString() };
        summary.review += 1;
      }
    }
    await store.updatePayment(updated);
  }

  return summary;
}
