import { homeLabel } from '@/src/domain/housing';
import { homeKey, type DashboardSnapshot, type HomeRecord, type PaymentRecord } from '@/src/domain/types';
import type { PaymentStore } from '@/src/storage/types';

const RECEIVED_STATUSES = new Set<PaymentRecord['status']>([
  'PENDIENTE_VERIFICACION', 'VERIFICADO', 'NO_ENCONTRADO', 'EN_REVISION', 'SIN_IDENTIFICAR', 'ESPERANDO_RESPUESTA',
]);

function isReceived(payment: PaymentRecord): boolean {
  return RECEIVED_STATUSES.has(payment.status) && payment.status !== 'DUPLICADO' && payment.status !== 'RECHAZADO';
}

function accountingPayments(payments: readonly PaymentRecord[]): PaymentRecord[] {
  return payments.filter((payment) => payment.status !== 'DUPLICADO' && payment.status !== 'RECHAZADO');
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
  const homesByKey = new Map(homes.map((home) => [homeKey(home), home]));
  const allPayments = (await store.listPayments()).filter((payment) => payment.period === period);
  const received = accountingPayments(allPayments).filter(isReceived);
  const assigned = received.filter((payment) => payment.stage != null && payment.block != null && payment.house != null);
  const assignedToActiveHomes = assigned.filter((payment) => activeHomeKeys.has(homeKey({ stage: payment.stage!, block: payment.block!, house: payment.house! })));
  const verifiedAssigned = assignedToActiveHomes.filter((payment) => payment.status === 'VERIFICADO');
  const paidKeys = new Set(verifiedAssigned.map((payment) => homeKey({ stage: payment.stage!, block: payment.block!, house: payment.house! })));
  const expectedAmount = homes.reduce((total, home) => total + home.monthlyFee, 0);
  const receivedAmount = received.reduce((total, payment) => total + payment.amount, 0);
  const verifiedAmount = verifiedAssigned.reduce((total, payment) => total + payment.amount, 0);
  const verifiedExpectedAmount = Array.from(paidKeys).reduce((total, key) => total + (homesByKey.get(key)?.monthlyFee ?? 0), 0);
  const unidentifiedAmount = received.filter((payment) => payment.stage == null || payment.block == null || payment.house == null).reduce((total, payment) => total + payment.amount, 0);

  const groups = new Map<string, { stage: number; block: number }>();
  homes.forEach((home) => groups.set(`${home.stage}:${home.block}`, { stage: home.stage, block: home.block }));
  const blocks = Array.from(groups.values())
    .sort((a, b) => a.stage - b.stage || a.block - b.block)
    .map(({ stage, block }) => {
      const blockHomes = homes.filter((home) => home.stage === stage && home.block === block);
      const paidHomes = blockHomes.filter((home) => paidKeys.has(homeKey(home))).length;
      const collected = verifiedAssigned
        .filter((payment) => payment.stage === stage && payment.block === block)
        .reduce((total, payment) => total + payment.amount, 0);
      return {
        stage,
        block,
        totalHomes: blockHomes.length,
        paidHomes,
        pendingHomes: blockHomes.length - paidHomes,
        collected,
        collectionRate: blockHomes.length ? paidHomes / blockHomes.length : 0,
      };
    });

  const toRow = (payment: PaymentRecord) => {
    const ref = payment.stage != null && payment.block != null && payment.house != null
      ? { stage: payment.stage, block: payment.block, house: payment.house }
      : undefined;
    const monthlyFee = ref ? homesByKey.get(homeKey(ref))?.monthlyFee : undefined;
    return {
      ...payment,
      homeLabel: homeLabel(ref),
      monthlyFee,
    };
  };
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
    pendingAmount: Math.max(0, expectedAmount - verifiedExpectedAmount),
    unidentifiedAmount,
    blocks,
    payments: [...allPayments].sort(sortNewest).map(toRow),
    unidentified: allPayments.filter((payment) => payment.status === 'SIN_IDENTIFICAR' || payment.status === 'ESPERANDO_RESPUESTA').sort(sortNewest).map(toRow),
    duplicates: allPayments.filter((payment) => payment.status === 'DUPLICADO').sort(sortNewest).map(toRow),
    review: allPayments.filter((payment) => payment.status === 'EN_REVISION' || payment.status === 'NO_ENCONTRADO').sort(sortNewest).map(toRow),
  };
}
