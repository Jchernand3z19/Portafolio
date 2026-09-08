import { redirect } from 'next/navigation';
import { isAdminAuthenticated } from '@/src/auth/guard';
import { periodFromDate, isPeriod, periodLabel } from '@/src/domain/periods';
import { buildDashboardSnapshot } from '@/src/services/dashboard';
import { getPaymentStore } from '@/src/storage';

export const dynamic = 'force-dynamic';

const money = (value: number) => `L${value.toLocaleString('es-HN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const pct = (value: number) => `${Math.round(value * 100)}%`;

export default async function AdminPage({ searchParams }: { searchParams: Promise<{ period?: string }> }) {
  if (!(await isAdminAuthenticated())) redirect('/login');
  const params = await searchParams;
  const period = params.period && isPeriod(params.period) ? params.period : periodFromDate();
  const store = await getPaymentStore();
  const snapshot = await buildDashboardSnapshot(store, period);

  return (
    <main className="shell">
      <header className="admin-head">
        <div><p className="eyebrow">Panel administrativo</p><h1 style={{ fontSize: 'clamp(2rem,5vw,3.6rem)' }}>Cobranza residencial</h1></div>
        <form method="post" action="/api/admin/logout"><button className="scenario-button" type="submit">Cerrar sesión</button></form>
      </header>

      <div className="section-head">
        <div><h2>{periodLabel(period)}</h2><p>Datos operativos privados</p></div>
        <form method="get" action="/admin">
          <label htmlFor="period">Período </label>
          <input id="period" name="period" type="month" defaultValue={period} />
          <button className="primary-button" type="submit">Ver</button>
        </form>
      </div>

      <section className="kpis">
        <div className="kpi"><span>Viviendas activas</span><strong>{snapshot.totalHomes}</strong><small>{snapshot.paidHomes} con pago · {snapshot.pendingHomes} pendientes</small></div>
        <div className="kpi"><span>Cobranza</span><strong>{pct(snapshot.collectionRate)}</strong><small>Por vivienda</small></div>
        <div className="kpi"><span>Esperado</span><strong>{money(snapshot.expectedAmount)}</strong><small>Pendiente {money(snapshot.pendingAmount)}</small></div>
        <div className="kpi"><span>Recibido</span><strong>{money(snapshot.receivedAmount)}</strong><small>Verificado {money(snapshot.verifiedAmount)}</small></div>
        <div className="kpi"><span>Sin identificar</span><strong>{money(snapshot.unidentifiedAmount)}</strong><small>{snapshot.unidentified.length} casos</small></div>
        <div className="kpi"><span>En revisión</span><strong>{snapshot.review.length}</strong><small>Requieren validación</small></div>
        <div className="kpi"><span>Duplicados</span><strong>{snapshot.duplicates.length}</strong><small>No suman dos veces</small></div>
        <div className="kpi"><span>Verificado</span><strong>{money(snapshot.verifiedAmount)}</strong><small>Confirmado por fuente confiable</small></div>
      </section>

      <div className="section-head"><div><p className="eyebrow">Por bloque</p><h2>Pagadas y pendientes</h2></div></div>
      <section className="blocks">
        {snapshot.blocks.map((block) => (
          <article className="block-card" key={block.block}>
            <div className="block-card__top"><strong>Bloque {block.block}</strong><span>{block.paidHomes}/{block.totalHomes}</span></div>
            <div className="progress"><span style={{ width: `${block.collectionRate * 100}%` }} /></div>
            <p className="lead">{block.pendingHomes} pendientes · {money(block.collected)} recibido</p>
          </article>
        ))}
      </section>

      <div className="section-head"><div><p className="eyebrow">Sin identificar</p><h2>Asignación de vivienda</h2></div><p>La asignación actualiza cartera y período sin repetir OCR.</p></div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Fecha</th><th>Depositante</th><th>Teléfono</th><th>Monto</th><th>Referencia</th><th>Comprobante</th><th>Asignar</th></tr></thead>
          <tbody>
            {snapshot.unidentified.length === 0 && <tr><td colSpan={7}>No hay comprobantes sin identificar para este período.</td></tr>}
            {snapshot.unidentified.map((payment) => (
              <tr key={payment.id}>
                <td>{payment.transactionDate ?? '—'}</td><td>{payment.depositor ?? '—'}</td><td>{payment.phone}</td><td>{money(payment.amount)}</td><td>{payment.reference ?? '—'}</td>
                <td>{payment.receiptFileId ? <a className="admin-link" href={`/api/admin/receipts/${payment.id}`} target="_blank" rel="noreferrer">Ver</a> : 'No archivado'}</td>
                <td>
                  <form method="post" action={`/api/admin/payments/${payment.id}`}>
                    <input type="hidden" name="action" value="assign-home" />
                    <input type="hidden" name="period" value={period} />
                    <input aria-label="Bloque" name="block" inputMode="numeric" placeholder="Bloque" required style={{ width: 75 }} />{' '}
                    <input aria-label="Casa" name="house" inputMode="numeric" placeholder="Casa" required style={{ width: 75 }} />{' '}
                    <button className="primary-button" type="submit">Asignar</button>
                  </form>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="section-head"><div><p className="eyebrow">Pagos</p><h2>Historial del período</h2></div><p>El período se puede corregir manualmente para atrasos o anticipos.</p></div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Fecha</th><th>Vivienda</th><th>Depositante</th><th>Monto</th><th>Referencia</th><th>Estado</th><th>Período</th><th>Comprobante</th></tr></thead>
          <tbody>
            {snapshot.payments.map((payment) => (
              <tr key={payment.id}>
                <td>{payment.transactionDate ?? '—'}</td><td>{payment.homeLabel}</td><td>{payment.depositor ?? '—'}</td><td>{money(payment.amount)}</td><td>{payment.reference ?? '—'}</td><td>{payment.status.replaceAll('_', ' ')}</td>
                <td>
                  <form method="post" action={`/api/admin/payments/${payment.id}`}>
                    <input type="hidden" name="action" value="set-period" />
                    <input type="month" name="newPeriod" defaultValue={payment.period} required />{' '}
                    <input type="hidden" name="period" value={period} />
                    <button type="submit">Guardar</button>
                  </form>
                </td>
                <td>{payment.receiptFileId ? <a className="admin-link" href={`/api/admin/receipts/${payment.id}`} target="_blank" rel="noreferrer">Ver</a> : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="section-head"><div><p className="eyebrow">Excepciones</p><h2>Duplicados y revisión</h2></div></div>
      <section className="queues">
        <article className="queue"><h3>Duplicados</h3><p>Se conserva trazabilidad del original relacionado.</p><strong>{snapshot.duplicates.length}</strong></article>
        <article className="queue"><h3>En revisión</h3><p>Conflictos, destino inesperado o conciliación insuficiente.</p><strong>{snapshot.review.length}</strong></article>
        <article className="queue"><h3>Sin identificar</h3><p>Esperando vivienda por WhatsApp o asignación manual.</p><strong>{snapshot.unidentified.length}</strong></article>
      </section>
    </main>
  );
}
