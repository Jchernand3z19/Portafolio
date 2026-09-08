import Link from 'next/link';
import { redirect } from 'next/navigation';
import { isAdminAuthenticated } from '@/src/auth/guard';
import { getPaymentStore } from '@/src/storage';

export const dynamic = 'force-dynamic';

const money = (value: number) => `L${value.toLocaleString('es-HN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export default async function HomesAdminPage() {
  if (!(await isAdminAuthenticated())) redirect('/login');
  const store = await getPaymentStore();
  const homes = (await store.listHomes()).sort((a, b) => a.block - b.block || a.house - b.house);
  const active = homes.filter((home) => home.active);
  const expected = active.reduce((total, home) => total + home.monthlyFee, 0);

  return (
    <main className="shell">
      <header className="admin-head">
        <div>
          <p className="eyebrow">Base maestra</p>
          <h1 style={{ fontSize: 'clamp(2rem,5vw,3.6rem)' }}>Viviendas</h1>
          <p className="lead">Bloque + casa es el identificador operativo. El teléfono sirve únicamente para ayudar a identificar comprobantes sin detalle.</p>
        </div>
        <Link className="primary-button" href="/admin">Volver al panel</Link>
      </header>

      <section className="kpis" style={{ marginTop: 28 }}>
        <div className="kpi"><span>Viviendas registradas</span><strong>{homes.length}</strong><small>{active.length} activas</small></div>
        <div className="kpi"><span>Cuota esperada activa</span><strong>{money(expected)}</strong><small>Según cuota de cada vivienda</small></div>
        <div className="kpi"><span>Con teléfono</span><strong>{active.filter((home) => home.phone).length}</strong><small>Elegibles para resolución por WhatsApp</small></div>
        <div className="kpi"><span>Sin teléfono</span><strong>{active.filter((home) => !home.phone).length}</strong><small>Se identifican por comprobante o respuesta</small></div>
      </section>

      <div className="section-head"><div><p className="eyebrow">Nueva vivienda</p><h2>Agregar a la base maestra</h2></div><p>No se usan nombres ni teléfonos reales en la demo pública.</p></div>
      <form className="home-form" method="post" action="/api/admin/homes">
        <label>Bloque<input name="block" inputMode="numeric" min="1" type="number" required /></label>
        <label>Casa<input name="house" inputMode="numeric" min="1" type="number" required /></label>
        <label>Responsable opcional<input name="responsible" maxLength={160} /></label>
        <label>Teléfono opcional<input name="phone" inputMode="tel" placeholder="50499999999" /></label>
        <label>Cuota mensual<input name="monthlyFee" min="0.01" step="0.01" type="number" required /></label>
        <label>Fecha de alta<input name="startDate" type="date" /></label>
        <button className="primary-button" type="submit">Agregar vivienda</button>
      </form>

      <div className="section-head"><div><p className="eyebrow">Inventario</p><h2>Editar viviendas</h2></div><p>Bloque y casa permanecen fijos para no romper el historial.</p></div>
      <div className="table-wrap homes-table">
        <table>
          <thead><tr><th>Vivienda</th><th>Responsable</th><th>Teléfono</th><th>Cuota</th><th>Alta</th><th>Baja</th><th>Activa</th><th>Guardar</th></tr></thead>
          <tbody>
            {homes.length === 0 && <tr><td colSpan={8}>No hay viviendas registradas.</td></tr>}
            {homes.map((home) => (
              <tr key={home.id}>
                <td><Link className="admin-link" href={`/admin/homes/${home.block}/${home.house}`}>B{home.block} · C{home.house}</Link></td>
                <td colSpan={7} style={{ padding: 0 }}>
                  <form className="home-row-form" method="post" action={`/api/admin/homes/${encodeURIComponent(home.id)}`}>
                    <input aria-label={`Responsable B${home.block} C${home.house}`} name="responsible" defaultValue={home.responsible ?? ''} maxLength={160} />
                    <input aria-label={`Teléfono B${home.block} C${home.house}`} name="phone" defaultValue={home.phone ?? ''} inputMode="tel" />
                    <input aria-label={`Cuota B${home.block} C${home.house}`} name="monthlyFee" defaultValue={home.monthlyFee} min="0.01" step="0.01" type="number" required />
                    <input aria-label={`Alta B${home.block} C${home.house}`} name="startDate" defaultValue={home.startDate ?? ''} type="date" />
                    <input aria-label={`Baja B${home.block} C${home.house}`} name="endDate" defaultValue={home.endDate ?? ''} type="date" />
                    <label className="checkbox-cell"><input name="active" type="checkbox" defaultChecked={home.active} /><span>Activa</span></label>
                    <button type="submit">Guardar</button>
                  </form>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
