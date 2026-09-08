import { DemoWorkbench } from './demo-workbench';
import { DEMO_HOMES, DEMO_PAYMENTS, DEMO_PERIOD } from '@/src/demo/data';
import { periodLabel } from '@/src/domain/periods';
import { buildDashboardSnapshot } from '@/src/services/dashboard';
import { MemoryPaymentStore } from '@/src/storage/memory';

const currency = (value: number) => `L${value.toLocaleString('es-HN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const percent = (value: number) => `${Math.round(value * 100)}%`;

function statusClass(status: string): string {
  if (status === 'VERIFICADO') return 'status status--verified';
  if (status === 'DUPLICADO') return 'status status--duplicate';
  if (status === 'EN_REVISION' || status === 'NO_ENCONTRADO') return 'status status--review';
  return 'status';
}

export default async function HomePage() {
  const store = new MemoryPaymentStore({ homes: DEMO_HOMES, payments: DEMO_PAYMENTS });
  const snapshot = await buildDashboardSnapshot(store, DEMO_PERIOD);

  return (
    <main className="shell">
      <header className="topbar">
        <div className="brand">JC HERNANDEZ · PRODUCT DEMO</div>
        <div className="demo-pill">Demo pública · datos 100% ficticios</div>
      </header>

      <section className="hero">
        <div className="hero__copy">
          <p className="eyebrow">WhatsApp · OCR · conciliación · cartera</p>
          <h1>Pagos residenciales por WhatsApp</h1>
          <p className="lead">
            Plataforma para recibir comprobantes por WhatsApp, extraer datos, identificar vivienda, detectar duplicados,
            separar comprobante de pago verificado y mantener la cobranza mensual bajo control.
          </p>
        </div>
        <div className="hero__flow" aria-label="Flujo del sistema">
          {['WhatsApp', 'Validación de archivo', 'OCR local', 'Parser BAC', 'Bloque + casa', 'Antiduplicados', 'Google Sheets', 'Dashboard'].map((step, index, array) => (
            <div className="flow-step" key={step}><strong>{step}</strong>{index < array.length - 1 && <span className="flow-arrow">↓</span>}</div>
          ))}
        </div>
      </section>

      <div className="notice">
        Un comprobante leído por OCR no demuestra que el dinero exista. Por diseño, el sistema separa <strong>comprobante recibido</strong> de <strong>pago verificado</strong>; la verificación requiere una fuente bancaria confiable.
      </div>

      <div className="section-head"><div><p className="eyebrow">Resumen mensual</p><h2>{periodLabel(snapshot.period)}</h2></div><p>Escenario demostrativo de 12 viviendas</p></div>
      <section className="kpis" aria-label="Indicadores mensuales">
        <div className="kpi"><span>Viviendas activas</span><strong>{snapshot.totalHomes}</strong><small>{snapshot.paidHomes} con comprobante · {snapshot.pendingHomes} pendientes</small></div>
        <div className="kpi"><span>Cobranza</span><strong>{percent(snapshot.collectionRate)}</strong><small>Por vivienda para el período</small></div>
        <div className="kpi"><span>Monto esperado</span><strong>{currency(snapshot.expectedAmount)}</strong><small>Pendiente {currency(snapshot.pendingAmount)}</small></div>
        <div className="kpi"><span>Monto recibido</span><strong>{currency(snapshot.receivedAmount)}</strong><small>Verificado {currency(snapshot.verifiedAmount)}</small></div>
        <div className="kpi"><span>Sin identificar</span><strong>{currency(snapshot.unidentifiedAmount)}</strong><small>Fuera de la recaudación por casa hasta asignar vivienda</small></div>
        <div className="kpi"><span>Duplicados</span><strong>{snapshot.duplicates.length}</strong><small>No vuelven a sumar recaudación</small></div>
        <div className="kpi"><span>En revisión</span><strong>{snapshot.review.length}</strong><small>Casos que necesitan validación</small></div>
        <div className="kpi"><span>Pago verificado</span><strong>{snapshot.payments.filter((payment) => payment.status === 'VERIFICADO').length}</strong><small>Separado del OCR</small></div>
      </section>

      <div className="section-head"><div><p className="eyebrow">Por bloque</p><h2>Avance de cobranza</h2></div><p>Casas pagadas, pendientes y recaudación</p></div>
      <section className="blocks">
        {snapshot.blocks.map((block) => (
          <article className="block-card" key={block.block}>
            <div className="block-card__top"><strong>Bloque {block.block}</strong><span>{block.paidHomes}/{block.totalHomes} pagadas</span></div>
            <div className="progress"><span style={{ width: `${block.collectionRate * 100}%` }} /></div>
            <p className="lead">{percent(block.collectionRate)} · {currency(block.collected)} recibido</p>
          </article>
        ))}
      </section>

      <div className="section-head"><div><p className="eyebrow">Demo interactiva</p><h2>Del comprobante a la respuesta</h2></div><p>Parser real sobre fixtures sintéticos</p></div>
      <DemoWorkbench />

      <div className="section-head"><div><p className="eyebrow">Pagos</p><h2>Movimientos del período</h2></div><p>Referencia, vivienda, banco, monto y estado</p></div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Fecha</th><th>Vivienda</th><th>Depositante</th><th>Monto</th><th>Referencia</th><th>Banco</th><th>Estado</th></tr></thead>
          <tbody>
            {snapshot.payments.map((payment) => (
              <tr key={payment.id}>
                <td>{payment.transactionDate ?? '—'}</td>
                <td>{payment.homeLabel}</td>
                <td>{payment.depositor ?? '—'}</td>
                <td>{currency(payment.amount)}</td>
                <td>{payment.reference ?? '—'}</td>
                <td>{payment.bank}</td>
                <td><span className={statusClass(payment.status)}>{payment.status.replaceAll('_', ' ')}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="section-head"><div><p className="eyebrow">Excepciones</p><h2>Bandejas operativas</h2></div><p>Lo que necesita acción queda separado</p></div>
      <section className="queues">
        <article className="queue"><h3>Sin identificar</h3><p>Comprobantes sin bloque/casa. WhatsApp solicita la vivienda sin repetir OCR.</p><strong>{snapshot.unidentified.length}</strong></article>
        <article className="queue"><h3>Duplicados</h3><p>Reenvíos o referencias repetidas se registran como excepción y no vuelven a sumar.</p><strong>{snapshot.duplicates.length}</strong></article>
        <article className="queue"><h3>En revisión</h3><p>Conflictos de referencia, destino inesperado o validación insuficiente.</p><strong>{snapshot.review.length}</strong></article>
      </section>

      <footer className="footer">
        <span>Next.js · TypeScript · WhatsApp Cloud API · Tesseract.js · Google Sheets API</span>
        <span>Sin credenciales, PII ni comprobantes reales en esta demo.</span>
      </footer>
    </main>
  );
}
