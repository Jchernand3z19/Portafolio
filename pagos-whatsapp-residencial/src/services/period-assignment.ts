import { isPeriod, periodFromDate, shiftPeriod } from '@/src/domain/periods';
import type { HomeRef, PaymentRecord } from '@/src/domain/types';

export const HISTORY_BASE_PERIOD = '2026-08';
export const HISTORY_BASE_CUTOFF_DATE = '2026-08-15';

const NON_OCCUPYING_STATUSES = new Set<PaymentRecord['status']>(['DUPLICADO', 'RECHAZADO']);

function transactionPeriod(transactionDate: string | undefined, now: Date): string {
  const candidate = transactionDate?.slice(0, 7);
  return candidate && isPeriod(candidate) ? candidate : periodFromDate(now);
}

export function baselinePeriodFromDepositDate(transactionDate: string | undefined, now = new Date()): string {
  const depositPeriod = transactionPeriod(transactionDate, now);
  if (depositPeriod === HISTORY_BASE_PERIOD && transactionDate && transactionDate < HISTORY_BASE_CUTOFF_DATE) return '2026-07';
  return depositPeriod;
}

function sameHome(payment: PaymentRecord, home: HomeRef): boolean {
  return payment.stage === home.stage && payment.block === home.block && payment.house === home.house;
}

function periodsBetween(start: string, end: string): string[] {
  if (start > end) return [];
  const result: string[] = [];
  let current = start;
  while (current <= end && result.length < 240) {
    result.push(current);
    current = shiftPeriod(current, 1);
  }
  return result;
}

/**
 * Business rule:
 * - August 2026 is the baseline month for the historical ledger.
 * - Deposits dated 2026-08-01..14 are treated as July.
 * - Deposits dated 2026-08-15..31 are treated as August.
 * - From September onward, assign the first unpaid service month starting at August.
 * - If every month through the deposit month already has a receipt, keep the deposit in
 *   the deposit month so an extra payment is visible for human review instead of silently
 *   advancing it to a future service month.
 */
export function assignServicePeriod(
  home: HomeRef,
  transactionDate: string | undefined,
  existingPayments: readonly PaymentRecord[],
  now = new Date(),
  excludePaymentId?: string,
): string {
  const depositPeriod = transactionPeriod(transactionDate, now);

  if (depositPeriod < HISTORY_BASE_PERIOD) return depositPeriod;

  if (depositPeriod === HISTORY_BASE_PERIOD) return baselinePeriodFromDepositDate(transactionDate, now);

  const occupied = new Set(
    existingPayments
      .filter((payment) => payment.id !== excludePaymentId)
      .filter((payment) => !NON_OCCUPYING_STATUSES.has(payment.status))
      .filter((payment) => sameHome(payment, home))
      .map((payment) => payment.period),
  );

  const firstPending = periodsBetween(HISTORY_BASE_PERIOD, depositPeriod).find((period) => !occupied.has(period));
  return firstPending ?? depositPeriod;
}

export function hasPeriodConflict(payment: PaymentRecord, existingPayments: readonly PaymentRecord[]): boolean {
  if (payment.stage == null || payment.block == null || payment.house == null) return false;
  return existingPayments.some((other) =>
    other.id !== payment.id
    && !NON_OCCUPYING_STATUSES.has(other.status)
    && other.stage === payment.stage
    && other.block === payment.block
    && other.house === payment.house
    && other.period === payment.period,
  );
}
