import { isDemoMode } from '@/src/config/env';
import { DEMO_HOMES, DEMO_PAYMENTS } from '@/src/demo/data';
import { GoogleSheetsPaymentStore } from './google-sheets';
import { MemoryPaymentStore } from './memory';
import { GoogleDriveReceiptArchive, type ReceiptArchive } from './receipts';
import type { PaymentStore } from './types';

let demoStore: MemoryPaymentStore | undefined;
let productionStore: GoogleSheetsPaymentStore | undefined;
let productionSchemaReady: Promise<void> | undefined;
let receiptArchive: GoogleDriveReceiptArchive | undefined;

export async function getPaymentStore(): Promise<PaymentStore> {
  if (isDemoMode()) {
    demoStore ??= new MemoryPaymentStore({ homes: DEMO_HOMES, payments: DEMO_PAYMENTS });
    return demoStore;
  }

  productionStore ??= new GoogleSheetsPaymentStore();
  productionSchemaReady ??= productionStore.ensureSchema();
  await productionSchemaReady;
  return productionStore;
}

export function getReceiptArchive(): ReceiptArchive | undefined {
  if (isDemoMode()) return undefined;
  receiptArchive ??= new GoogleDriveReceiptArchive();
  return receiptArchive;
}
