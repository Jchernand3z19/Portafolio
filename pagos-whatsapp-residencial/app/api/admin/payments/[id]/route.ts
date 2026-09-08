import { NextResponse } from 'next/server';
import { isAdminAuthenticated, isSameOriginRequest } from '@/src/auth/guard';
import { isPeriod } from '@/src/domain/periods';
import { getPaymentStore } from '@/src/storage';

export const runtime = 'nodejs';

export async function POST(request: Request, { params }: { params: Promise<{ id: string }> }) {
  if (!(await isAdminAuthenticated())) return new NextResponse('Unauthorized', { status: 401 });
  if (!isSameOriginRequest(request)) return new NextResponse('Forbidden', { status: 403 });

  const { id } = await params;
  const store = await getPaymentStore();
  const payment = await store.getPayment(id);
  if (!payment) return new NextResponse('Payment not found', { status: 404 });

  const form = await request.formData();
  const action = String(form.get('action') ?? '');
  const returnPeriod = String(form.get('period') ?? payment.period);

  if (action === 'set-period') {
    const newPeriod = String(form.get('newPeriod') ?? '');
    if (!isPeriod(newPeriod)) return new NextResponse('Invalid period', { status: 400 });
    await store.updatePayment({ ...payment, period: newPeriod, updatedAt: new Date().toISOString() });
    return NextResponse.redirect(new URL(`/admin?period=${encodeURIComponent(returnPeriod)}`, request.url), 303);
  }

  if (action === 'assign-home') {
    const block = Number.parseInt(String(form.get('block') ?? ''), 10);
    const house = Number.parseInt(String(form.get('house') ?? ''), 10);
    if (!Number.isInteger(block) || !Number.isInteger(house) || block <= 0 || house <= 0) return new NextResponse('Invalid home', { status: 400 });

    const homes = await store.listHomes();
    const known = homes.find((home) => home.active && home.block === block && home.house === house);
    if (!known) return new NextResponse('Home not found', { status: 400 });

    const homeOnlyWarnings = new Set(['receipt_home_not_in_master', 'phone_has_multiple_homes']);
    const reviewReason = payment.reviewReason && !homeOnlyWarnings.has(payment.reviewReason) ? payment.reviewReason : undefined;
    await store.updatePayment({
      ...payment,
      block,
      house,
      status: reviewReason ? 'EN_REVISION' : 'PENDIENTE_VERIFICACION',
      reviewReason,
      updatedAt: new Date().toISOString(),
    });
    await store.clearPending(payment.phone);
    return NextResponse.redirect(new URL(`/admin?period=${encodeURIComponent(returnPeriod)}`, request.url), 303);
  }

  return new NextResponse('Unsupported action', { status: 400 });
}
