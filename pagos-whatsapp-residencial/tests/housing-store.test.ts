import { describe, expect, it } from 'vitest';
import { MemoryPaymentStore } from '@/src/storage/memory';

describe('housing master store', () => {
  it('creates and updates homes while preserving unique block+house', async () => {
    const store = new MemoryPaymentStore();
    await store.saveHome({ id: 'home-b4-c18', block: 4, house: 18, phone: '50499999999', monthlyFee: 150, active: true });
    expect((await store.listHomes()).length).toBe(1);
    expect((await store.findHomesByPhone('+504 9999-9999'))[0]?.id).toBe('home-b4-c18');

    await store.updateHome({ id: 'home-b4-c18', block: 4, house: 18, responsible: 'Persona Demo', phone: '50499999999', monthlyFee: 175, active: true });
    expect((await store.listHomes())[0].monthlyFee).toBe(175);

    await expect(store.saveHome({ id: 'another', block: 4, house: 18, monthlyFee: 150, active: true })).rejects.toThrow('home_address_already_exists');
  });
});
