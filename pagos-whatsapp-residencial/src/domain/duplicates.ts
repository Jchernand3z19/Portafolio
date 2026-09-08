import type { HomeRef, PaymentRecord } from './types';

export type DuplicateDecision =
  | { kind: 'none' }
  | { kind: 'retry'; original: PaymentRecord; reason: 'message_id' }
  | { kind: 'duplicate'; original: PaymentRecord; reason: 'file_hash' | 'bank_reference' }
  | { kind: 'conflict'; original: PaymentRecord; reason: 'bank_reference_home_conflict' }
  | { kind: 'review'; original: PaymentRecord; reason: 'weak_signature' };

export interface DuplicateProbe {
  sourceMessageId: string;
  fileHash: string;
  bank: string;
  reference?: string;
  amount?: number;
  transactionDate?: string;
  phone: string;
  home?: HomeRef;
}

function sameHome(record: PaymentRecord, home: HomeRef | undefined): boolean {
  if (!home || record.block == null || record.house == null) return true;
  return record.block === home.block && record.house === home.house;
}

export function decideDuplicate(probe: DuplicateProbe, existing: readonly PaymentRecord[]): DuplicateDecision {
  const byMessage = existing.find((record) => record.sourceMessageId === probe.sourceMessageId);
  if (byMessage) return { kind: 'retry', original: byMessage, reason: 'message_id' };

  const byHash = existing.find((record) => record.fileHash === probe.fileHash);
  if (byHash) return { kind: 'duplicate', original: byHash, reason: 'file_hash' };

  const normalizedReference = probe.reference?.trim().toUpperCase();
  if (normalizedReference) {
    const byReference = existing.find(
      (record) => record.bank.toUpperCase() === probe.bank.toUpperCase() && record.reference?.trim().toUpperCase() === normalizedReference,
    );
    if (byReference) {
      if (!sameHome(byReference, probe.home) || byReference.phone !== probe.phone) {
        return { kind: 'conflict', original: byReference, reason: 'bank_reference_home_conflict' };
      }
      return { kind: 'duplicate', original: byReference, reason: 'bank_reference' };
    }
  }

  if (probe.amount != null && probe.transactionDate) {
    const weak = existing.find(
      (record) =>
        record.bank.toUpperCase() === probe.bank.toUpperCase() &&
        record.phone === probe.phone &&
        record.amount === probe.amount &&
        record.transactionDate === probe.transactionDate,
    );
    if (weak) return { kind: 'review', original: weak, reason: 'weak_signature' };
  }

  return { kind: 'none' };
}
