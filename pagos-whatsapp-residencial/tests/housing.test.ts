import { describe, expect, it } from 'vitest';
import { parseHomeReference } from '@/src/domain/housing';

describe('parseHomeReference', () => {
  it.each([
    ['B4 C18', { block: 4, house: 18 }],
    ['Bloque 4 Casa 18', { block: 4, house: 18 }],
    ['B4-C18', { block: 4, house: 18 }],
    ['B 4 C 18', { block: 4, house: 18 }],
    ['bloque 12 casa 103', { block: 12, house: 103 }],
    ['Casa 18 Bloque 4', { block: 4, house: 18 }],
  ])('parses %s', (input, expected) => {
    expect(parseHomeReference(input)).toEqual(expected);
  });

  it('rejects missing or invalid values', () => {
    expect(parseHomeReference('Cuota septiembre')).toBeUndefined();
    expect(parseHomeReference('B0 C18')).toBeUndefined();
  });
});
