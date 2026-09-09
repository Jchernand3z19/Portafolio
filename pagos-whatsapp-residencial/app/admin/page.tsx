import Link from 'next/link';
import { redirect } from 'next/navigation';
import { isAdminAuthenticated } from '@/src/auth/guard';
import { periodFromDate, isPeriod, periodLabel } from '@/src/domain/periods';
import { buildDashboardSnapshot } from '@/src/services/dashboard';
import { buildHouseHistoryGrid, type HousePeriodState } from '@/src/services/house-history';
import { canManuallyVerify } from '@/src/services/manual-verification';
import { getPaymentStore } from '@/src/storage';

export const dynamic = 'force-dynamic';

const money = (value: number) => `L${value.toLocaleString('es-HN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const pct = (value: number) => `${Math.round(value * 100)}%`;
const HOUSE_STATE_LABEL: Record<HousePeriodState, string> = {
  VERIFICADO: '✅ Verificado',
  RECIBIDO: '✓ Recibido',
  EN_REVISION: '⚠ Revisión',
  NO_ENCONTRADO: '✕ No encontrado',
  PENDIENTE: '— Pendiente',
};
const DUPLICATE_REASON_LABEL: Record<string, string> = {
  file_hash: 'Archivo idéntico',
  exact_file_other_sender: 'Archivo idéntico desde otro remitente',
  bank_reference_reused: 'Referencia bancaria repetida; requiere revisión',
  bank_reference_home_conflict: 'Referencia repetida con otra vivienda',
  bank_reference_data_conflict: 'Referencia repetida con monto o fecha diferente',
  weak_signature: 'Banco, monto y fecha coinciden con otro pago',
  service_period_already_has_payment: 'La vivienda ya tiene un pago asignado a ese mes',
};

export default async function AdminPage({ searchParams }: { searchParams: Promise<{ period?: string }> }) {
  if (!(await isAdminAuthenticated())) redirect('/login');
  const params = await searchParams;
  const period = params.period && isPeriod(params.period) ? params.period : periodFromDate();
  const store = await getPaymentStore();
  const [snapshot, houseGrid] = await Promise.all([
    buildDashboardSnapshot(store, period),
    buildHouseHistoryGrid(store, period, 4),
  ]);

  return (
    <main className="shell">
      <header className="admin-head">
        <div><p className="eyebrow">Panel administrativo</p><h1 style={{ fontSize: 'clamp(2rem,5vw,3.6rem)' }}>Cobranza residencial</h1></div>
        <div className="admin-head-actions">
          <Link className="primary-button" href="/admin/homes">Gestionar viviendas</Link>
          <form method="post" action="/api/admin/logout"><button className="scenario-button" type="submit">Cerrar sesión</button></form>
        </div>
      </header>

      <div className="section-head">
        <div><h2>{periodLabel(period)}</h2><p>Datos operativos privados</p></div>
        <form method="get" action="/admin">
          <label htmlFor="period">Mes pagado </label>
          <input id="period" name="period" type="month" defaultValue={period} />
          <button className="primary-button" type="submit">Ver</button>
        </form>
      </div>

      <section className="kpis">
        <div className="kpi"><span>Viviendas activas</span><strong>{snapshot.totalHomes}</strong><small>{snapshot.paidHomes} con comprobante · {snapshot.pendingHomes} pendientes</small></div>
        <div className="kpi"><span>Cobranza</span><strong>{pct(snapshot.collectionRate)}</strong><small>Por vivienda con comprobante</small></div>
        <div className="kpi"><span>Esperado</span><strong>{money(snapshot.expectedAmount)}</strong><small>Pendiente {money(snapshot.pendingAmount)}</small></div>
        <div className="kpi"><span>Recibido</span><strong>{money(snapshot.receivedAmount)}</strong><small>Comprobantes aceptados</small></div>
        <div className="kpi"><span>Sin identificar</span><strong>{money(snapshot.unidentifiedAmount)}</strong><small>{snapshot.unidentified.length} casos</small></div>
        <div className="kpi"><span>En revisión</span><strong>{snapshot.review.length}</strong><small>Requieren validación humana</small></div>
        <div className="kpi"><span>Duplicados</span><strong>{snapshot.duplicates.length}</strong><small>No suman dos veces</small></div>
        <div className="kpi"><span>Verificado</span><strong>{money(snapshot.verifiedAmount)}</strong><small>Confirmado revisando el banco</small></div>
      </section>

      <div className="section-head"><div><p className="eyebrow">Por etapa y bloque</p><h2>Pagadas y pendientes</h2></div></div>
      <section className="blocks">
        {snapshot.blocks.map((group) => (
          <article className="block-card" key={`${group.stage}-${group.block}`}>
            <div className="block-card__top"><strong>Etapa {group.stage} · Bloque {group.block}</strong><span>{group.paidHomes}/{group.totalHomes}</span></div>
            <div className="progress"><span style={{ width: `${group.collectionRate * 100}%` }} /></div>
            <p className="lead">{group.pendingHomes} pendientes · {money(group.collected)} recibido</p>
          </article>
        ))}
      </section>

      <div className="section-head">
        <div><p className="eyebrow">Por vivienda</p><h2>Historial de los últimos 4 períodos</h2></div>
        <p>La vivienda se identifica exclusivamente por Etapa + Bloque + Casa.</p>
      </div>
      <div className="table-wrap house-history-table">
        <table>
          <thead><tr><th>Vivienda</th>{houseGrid.periods.map((item) => <th key={item}>{periodLabel(item)}</th>)}</tr></thead>
          <tbody>
            {houseGrid.rows.map((row) => (
              <tr key={row.home.id}>
                <td><Link className="admin-link" href={`/admin/homes/${row.home.stage}/${row.home.block}/${row.home.house}`}>E{row.home.stage} · B{row.home.block} · C{row.home.house}</Link></td>
                {row.periods.map((cell) => (
                  <td key={cell.period}>
                    <span className={`status-chip status-chip--${cell.state.toLowerCase()}`}>{HOUSE_STATE_LABEL[cell.state]}</span>
                    {cell.amount != null && <small className="status-amount">{money(cell.amount)}</small>}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="section-head"><div><p className="eyebrow">Sin identificar</p><h2>Asignación de vivienda</h2></div><p>Si falta etapa, bloque o casa, se piden los tres por WhatsApp. Esta asignación no repite OCR.</p></div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Fecha depósito</th><th>Depositante</th><th>Teléfono WhatsApp</th><th>Monto</th><th>Referencia</th><th>Comprobante</th><th>Asignar E/B/C</th></tr></thead>
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
                    <input aria-label="Etapa" name="stage" inputMode="numeric" placeholder="Etapa" required style={{ width: 70 }} />{' '}
                    <input aria-label="Bloque" name="block" inputMode="numeric" placeholder="Bloque" required style={{ width: 70 }} />{' '}
                    <input aria-label="Casa" name="house" inputMode="numeric" placeholder="Casa" required style={{ width: 70 }} />{' '}
                    <button className="primary-button" type="submit">Asignar</button>
                  </form>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="section-head"><div><p className="eyebrow">Pagos</p><h2>Historial del período</h2></div><p>Fecha depósito viene del comprobante; Mes pagado sigue el histórico desde agosto 2026.</p></div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Fecha depósito</th><th>Vivienda</th><th>Depositante</th><th>Teléfono WhatsApp</th><th>Banco</th><th>Cuota/Monto</th><th>Referencia</th><th>Estado</th><th>Mes pagado</th><th>Comprobante</th><th>Verificación</th></tr></thead>
          <tbody>
            {snapshot.payments.map((payment) => (
              <tr key={payment.id}>
                <td>{payment.transactionDate ?? '—'}</td><td>{payment.homeLabel}</td><td>{payment.depositor ?? '—'}</td><td>{payment.phone || '—'}</td><td>{payment.bank || '—'}</td><td>{money(payment.amount)}</td><td>{payment.reference ?? '—'}</td><td>{payment.status.replaceAll('_', ' ')}</td>
                <td>
                  <form method="post" action={`/api/admin/payments/${payment.id}`}>
                    <input type="hidden" name="action" value="set-period" />
                    <input type="month" name="newPeriod" defaultValue={payment.period} required />{' '}
                    <input type="hidden" name="period" value={period} />
                    <button type="submit">Guardar</button>
                  </form>
                </td>
                <td>{payment.receiptFileId ? <a className="admin-link" href={`/api/admin/receipts/${payment.id}`} target="_blank" rel="noreferrer">Ver</a> : '—'}</td>
                <td>
                  {canManuallyVerify(payment) ? (
                    <form method="post" action={`/api/admin/payments/${payment.id}`}>
                      <input type="hidden" name="action" value="verify-manually" />
                      <input type="hidden" name="period" value={period} />
                      <button className="primary-button" type="submit">Verificar</button>
                    </form>
                  ) : payment.status === 'VERIFICADO' ? (
                    <span>✅ Verificado{payment.verifiedAt ? ` · ${new Date(payment.verifiedAt).toLocaleDateString('es-HN')}` : ''}</span>
                  ) : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="section-head"><div><p className="eyebrow">Duplicados confirmados</p><h2>Comprobantes repetidos</h2></div><p>Sólo se marcan automáticamente por reintento técnico o archivo idéntico; una referencia repetida por sí sola no es duplicado.</p></div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Fecha</th><th>Vivienda</th><th>Teléfono WhatsApp</th><th>Monto</th><th>Referencia</th><th>Motivo</th><th>Original relacionado</th></tr></thead>
          <tbody>
            {snapshot.duplicates.length === 0 && <tr><td colSpan={7}>No hay duplicados confirmados en este período.</td></tr>}
            {snapshot.duplicates.map((payment) => (
              <tr key={payment.id}>
                <td>{payment.transactionDate ?? '—'}</td><td>{payment.homeLabel}</td><td>{payment.phone || '—'}</td><td>{money(payment.amount)}</td><td>{payment.reference ?? '—'}</td>
                <td>{DUPLICATE_REASON_LABEL[payment.duplicateReason ?? ''] ?? payment.duplicateReason ?? 'Coincidencia detectada'}</td><td>{payment.duplicateOf ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="section-head"><div><p className="eyebrow">Revisión humana</p><h2>Casos que requieren decisión</h2></div><p>El encargado compara comprobante y movimiento bancario. La referencia es una señal, no una prueba única.</p></div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Fecha</th><th>Vivienda</th><th>Teléfono WhatsApp</th><th>Banco</th><th>Monto</th><th>Referencia</th><th>Motivo</th><th>Comprobante</th><th>Acciones</th></tr></thead>
          <tbody>
            {snapshot.review.length === 0 && <tr><td colSpan={9}>No hay casos en revisión para este período.</td></tr>}
            {snapshot.review.map((payment) => (
              <tr key={payment.id}>
                <td>{payment.transactionDate ?? '—'}</td><td>{payment.homeLabel}</td><td>{payment.phone || '—'}</td><td>{payment.bank || '—'}</td><td>{money(payment.amount)}</td><td>{payment.reference ?? '—'}</td>
                <td>{DUPLICATE_REASON_LABEL[payment.reviewReason ?? ''] ?? payment.reviewReason ?? 'Revisión pendiente'}</td>
                <td>{payment.receiptFileId ? <a className="admin-link" href={`/api/admin/receipts/${payment.id}`} target="_blank" rel="noreferrer">Ver</a> : '—'}</td>
                <td>
                  {canManuallyVerify(payment, true) && (
                    <form method="post" action={`/api/admin/payments/${payment.id}`} style={{ display: 'inline' }}>
                      <input type="hidden" name="action" value="verify-reviewed" /><input type="hidden" name="period" value={period} />
                      <button className="primary-button" type="submit">Verifiqué en banco</button>{' '}
                    </form>
                  )}
                  {payment.duplicateOf && (
                    <form method="post" action={`/api/admin/payments/${payment.id}`} style={{ display: 'inline' }}>
                      <input type="hidden" name="action" value="mark-duplicate" /><input type="hidden" name="period" value={period} />
                      <button type="submit">Marcar duplicado</button>
                    </form>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="section-head"><div><p className="eyebrow">Excepciones</p><h2>Resumen operativo</h2></div></div>
      <section className="queues">
        <article className="queue"><h3>Duplicados</h3><p>Archivo idéntico o decisión humana confirmada.</p><strong>{snapshot.duplicates.length}</strong></article>
        <article className="queue"><h3>En revisión</h3><p>Referencias repetidas, conflictos o datos dudosos.</p><strong>{snapshot.review.length}</strong></article>
        <article className="queue"><h3>Sin identificar</h3><p>Esperando E/B/C por WhatsApp o asignación manual.</p><strong>{snapshot.unidentified.length}</strong></article>
      </section>
    </main>
  );
}
