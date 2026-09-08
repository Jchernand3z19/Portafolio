import { describe, expect, it } from 'vitest';
import { SYNTHETIC_BAC_RECEIPTS } from '@/src/demo/data';
import { bacParser } from '@/src/parsers/bac';

describe('BAC parser', () => {
  it('extracts a valid synthetic BAC receipt', () => {
    const result = bacParser.parse(SYNTHETIC_BAC_RECEIPTS.valid);
    expect(bacParser.detect(SYNTHETIC_BAC_RECEIPTS.valid)).toBeGreaterThanOrEqual(0.5);
    expect(result.bank).toBe('BAC Honduras');
    expect(result.depositor).toBe('JUAN PÉREZ DEMO');
    expect(result.transactionDate).toBe('2026-09-07');
    expect(result.transactionTime).toBe('08:12');
    expect(result.amount).toBe(150);
    expect(result.detail).toBe('B4 C18');
    expect(result.reference).toBe('DEMOREF000001');
    expect(result.beneficiary).toBe('RESIDENCIAL DEMO');
    expect(result.destinationAccountMasked).toBe('••••0001');
    expect(result.home).toEqual({ block: 4, house: 18 });
  });

  it('keeps a receipt without block and house as unidentified', () => {
    const result = bacParser.parse(SYNTHETIC_BAC_RECEIPTS.missingHome);
    expect(result.amount).toBe(150);
    expect(result.home).toBeUndefined();
    expect(result.warnings).toContain('home_missing');
  });
});
