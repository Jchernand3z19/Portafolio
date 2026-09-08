import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { resetEnvForTests } from '@/src/config/env';
import { SYNTHETIC_BAC_RECEIPTS } from '@/src/demo/data';
import type { HomeRecord } from '@/src/domain/types';
import { processHomeReply, processReceiptMessage } from '@/src/services/payment-processor';
import { MemoryPaymentStore } from '@/src/storage/memory';

const homes: HomeRecord[] = [
  { id: 'home-4-18', block: 4, house: 18, phone: '+50400000010', monthlyFee: 150, active: true },
  { id: 'home-2-2', block: 2, house: 2, phone: '+50400000020', monthlyFee: 150, active: true },
];

function png(variant: number): Buffer {
  return Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, variant]);
}

const now = () => new Date('2026-09-08T18:00:00.000Z');

beforeEach(() => {
  process.env.APP_MODE = 'demo';
  delete process.env.EXPECTED_BENEFICIARY;
  delete process.env.EXPECTED_ACCOUNT_LAST4;
  resetEnvForTests();
});

afterEach(() => {
  delete process.env.APP_MODE;
  delete process.env.EXPECTED_BENEFICIARY;
  delete process.env.EXPECTED_ACCOUNT_LAST4;
  resetEnvForTests();
});

describe('payment processor', () => {
  it('registers a valid BAC receipt as pending verification', async () => {
    const store = new MemoryPaymentStore({ homes });
    const result = await processReceiptMessage({
      messageId: 'msg-valid', phone: '+50400000999', bytes: png(1), declaredMime: 'image/png', syntheticOcrText: SYNTHETIC_BAC_RECEIPTS.valid,
    }, { store, now });

    expect(result.action).toBe('reply');
    expect(result.status).toBe('PENDIENTE_VERIFICACION');
    const payment = (await store.listPayments())[0];
    expect(payment.block).toBe(4);
    expect(payment.house).toBe(18);
    expect(payment.period).toBe('2026-09');
    expect(payment.status).not.toBe('VERIFICADO');
  });

  it('asks for home, preserves context, and assigns it without rerunning OCR', async () => {
    const store = new MemoryPaymentStore({ homes });
    const received = await processReceiptMessage({
      messageId: 'msg-missing-home', phone: '+50400000999', bytes: png(2), declaredMime: 'image/png', syntheticOcrText: SYNTHETIC_BAC_RECEIPTS.missingHome,
    }, { store, now });

    expect(received.status).toBe('ESPERANDO_RESPUESTA');
    expect(received.reply).toContain('Ejemplo: B4 C18');
    expect(await store.getPendingByPhone('+50400000999')).toBeDefined();

    const assigned = await processHomeReply('msg-home-reply', '+50400000999', 'B4 C18', { store, now });
    expect(assigned.status).toBe('PENDIENTE_VERIFICACION');
    const payment = await store.getPayment(received.paymentId!);
    expect(payment?.block).toBe(4);
    expect(payment?.house).toBe(18);
    expect(await store.getPendingByPhone('+50400000999')).toBeUndefined();
  });

  it('ignores a Meta retry silently and detects a user resend as duplicate', async () => {
    const store = new MemoryPaymentStore({ homes });
    const input = { messageId: 'msg-original', phone: '+50400000010', bytes: png(3), declaredMime: 'image/png', syntheticOcrText: SYNTHETIC_BAC_RECEIPTS.valid } as const;
    await processReceiptMessage(input, { store, now });

    const retry = await processReceiptMessage(input, { store, now });
    expect(retry.action).toBe('silent');
    expect(retry.reason).toBe('technical_retry');

    const resend = await processReceiptMessage({ ...input, messageId: 'msg-resend' }, { store, now });
    expect(resend.status).toBe('DUPLICADO');
    expect(resend.reply).toContain('No se registró un segundo pago');
  });

  it('sends a suspicious destination account to review instead of verifying it', async () => {
    process.env.EXPECTED_ACCOUNT_LAST4 = '9999';
    resetEnvForTests();
    const store = new MemoryPaymentStore({ homes });
    const result = await processReceiptMessage({
      messageId: 'msg-review', phone: '+50400000010', bytes: png(4), declaredMime: 'image/png', syntheticOcrText: SYNTHETIC_BAC_RECEIPTS.valid,
    }, { store, now });
    expect(result.status).toBe('EN_REVISION');
    expect((await store.listPayments())[0].reviewReason).toBe('destination_account_unexpected');
  });

  it('does not create a second ambiguous pending context for the same phone', async () => {
    const store = new MemoryPaymentStore({ homes });
    await processReceiptMessage({
      messageId: 'msg-pending-1', phone: '+50400000999', bytes: png(5), declaredMime: 'image/png', syntheticOcrText: SYNTHETIC_BAC_RECEIPTS.missingHome,
    }, { store, now });
    const secondText = SYNTHETIC_BAC_RECEIPTS.missingHome.replace('DEMOREF000002', 'DEMOREF000099');
    const second = await processReceiptMessage({
      messageId: 'msg-pending-2', phone: '+50400000999', bytes: png(6), declaredMime: 'image/png', syntheticOcrText: secondText,
    }, { store, now });
    expect(second.status).toBe('EN_REVISION');
    expect(second.reason).toBe('pending_context_conflict');
  });
});
