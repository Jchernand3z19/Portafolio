import { isAdminAuthenticated } from '@/src/auth/guard';
import { getPaymentStore, getReceiptArchive } from '@/src/storage';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  if (!(await isAdminAuthenticated())) return new Response('Unauthorized', { status: 401 });
  const { id } = await params;
  const store = await getPaymentStore();
  const payment = await store.getPayment(id);
  if (!payment?.receiptFileId) return new Response('Receipt not found', { status: 404 });

  const archive = getReceiptArchive();
  if (!archive) return new Response('Receipt archive unavailable in demo mode', { status: 404 });
  const file = await archive.read(payment.receiptFileId);
  const extension = file.mimeType === 'image/png' ? 'png' : 'jpg';
  const body = Uint8Array.from(file.bytes).buffer;
  return new Response(body, {
    headers: {
      'Content-Type': file.mimeType,
      'Cache-Control': 'private, no-store, max-age=0',
      'Content-Disposition': `inline; filename="comprobante-${payment.id}.${extension}"`,
      'X-Content-Type-Options': 'nosniff',
    },
  });
}
