import { homeLabel } from '@/src/domain/housing';
import { homeKey, type DashboardSnapshot, type HomeRecord, type PaymentRecord } from '@/src/domain/types';
import type { PaymentStore } from '@/src/storage/types';

const RECEIVED_STATUSES = new Set<PaymentRecord['status']>([
  'PENDIENTE_VERIFICACION', 'VERIFICADO', 'NO_ENCONTRADO', 'EN_REVISION', 'SIN_IDENTIFICAR', 'ESPERANDO_RESPUESTA',
]);

function isReceived(payment: PaymentRecord): boolean {
  return RECEIVED_STATUSES.has(payment.status) && payment.status !== 'DUPLICADO' && payment.status !== 'RECHAZADO';
}

function canonicalPayments(payments: readonly PaymentRecord[]): PaymentRecord[] {
  const seen = new Set<string>();
  return [...payments]
    .sort((a, b) => a.createdAt.localeCompare(b.createdAt) || a.id.localeCompare(b.id))
    .filter((payment) => {
      if (payment.status === 'DUPLICADO' || payment.status === 'RECHAZADO') return false;
      const key = payment.reference
        ? `ref:${payment.bank.toUpperCase()}:${payment.reference.toUpperCase()}`
        : `hash:${payment.fileHash}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
}

function activeInPeriod(home: HomeRecord, period: string): boolean {
  const monthEnd = `${period}-31`;
  const monthStart = `${period}-01`;
  if (home.startDate && home.startDate > monthEnd) return false;
  if (home.endDate && home.endDate < monthStart) return false;
  if (home.active) return true;
  return Boolean(home.endDate && home.endDate >= monthStart);
}

export async function buildDashboardSnapshot(store: PaymentStore, period: string): Promise<DashboardSnapshot> {
  const homes = (await store.listHomes()).filter((home) => activeInPeriod(home, period));
  const activeHomeKeys = new Set(homes.map(homeKey));
  const allPayments = (await store.listPayments()).filter((payment) => payment.period === period);
  const accountingPayments = canonicalPayments(allPayments).filter(isReceived);
  const assigned = accountingPayments.filter((payment) => payment.block != null && payment.house != null);
  const assignedToActiveHomes = assigned.filter((payment) => activeHomeKeys.has(homeKey({ block: payment.block!, house: payment.house! })));
  const paidKeys = new Set(assignedToActiveHomes.map((payment) => homeKey({ block: payment.block!, house: payment.house! })));
  const expectedAmount = homes.reduce((total, home) => total + home.monthlyFee, 0);
  const receivedAmount = accountingPayments.reduce((total, payment) => total + payment.amount, 0);
  const verifiedAmount = accountingPayments.filter((payment) => payment.status === 'VERIFICADO').reduce((total, payment) => total + payment.amount, 0);
  const unidentifiedAmount = accountingPayments.filter((payment) => payment.block == null || payment.house == null).reduce((total, payment) => total + payment.amount, 0);

  const blocks = Array.from(new Set(homes.map((home) => home.block))).sort((a, b) => a - b).map((block) => {
    const blockHomes = homes.filter((home) => home.block === block);
    const paidHomes = blockHomes.filter((home) => paidKeys.has(homeKey(home))).length;
    const collected = assignedToActiveHomes.filter((payment) => payment.block === block).reduce((total, payment) => total + payment.amount, 0);
    return {
      block,
      totalHomes: blockHomes.length,
      paidHomes,
      pendingHomes: blockHomes.length - paidHomes,
      collected,
      collectionRate: blockHomes.length ? paidHomes / blockHomes.length : 0,
    };
  });

  const toRow = (payment: PaymentRecord) => ({
    ...payment,
    homeLabel: homeLabel(payment.block != null && payment.house != null ? { block: payment.block, house: payment.house } : undefined),
  });
  const sortNewest = (a: PaymentRecord, b: PaymentRecord) => b.createdAt.localeCompare(a.createdAt);

  return {
    period,
    totalHomes: homes.length,
    paidHomes: paidKeys.size,
    pendingHomes: Math.max(0, homes.length - paidKeys.size),
    collectionRate: homes.length ? paidKeys.size / homes.length : 0,
    expectedAmount,
    receivedAmount,
    verifiedAmount,
    pendingAmount: Math.max(0, expectedAmount - assignedToActiveHomes.reduce((total, payment) => total + payment.amount, 0)),
    unidentifiedAmount,
    blocks,
    payments: [...allPayments].sort(sortNewest).map(toRow),
    unidentified: allPayments.filter((payment) => payment.status === 'SIN_IDENTIFICAR' || payment.status === 'ESPERANDO_RESPUESTA').sort(sortNewest).map(toRow),
    duplicates: allPayments.filter((payment) => payment.status === 'DUPLICADO').sort(sortNewest).map(toRow),
    review: allPayments.filter((payment) => payment.status === 'EN_REVISION' || payment.status === 'NO_ENCONTRADO').sort(sortNewest).map(toRow),
  };
}
