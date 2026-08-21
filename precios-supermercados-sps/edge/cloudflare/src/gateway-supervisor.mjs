import { EdgePolicyError } from "./core.mjs";
import { runExecuteOperation } from "./worker-adapter.mjs";

function failureReason(error) {
  if (error instanceof EdgePolicyError) return error.code;
  return "gateway_execution_failed";
}

function failureTime(clock) {
  try {
    const value = clock();
    if (value instanceof Date && !Number.isNaN(value.getTime())) return value.getTime();
  } catch {
    // El supervisor permanece fail-closed aunque el reloj falle.
  }
  return Date.now();
}

function closeReservationBestEffort(store, reservationId, reason, nowMs) {
  if (!store || typeof store.fail !== "function" || typeof reservationId !== "string" || !reservationId) return;
  try {
    store.fail(reservationId, reason, nowMs);
  } catch {
    // Puede no existir reserva (fallo pre-reserve), estar ya terminal o fallar storage.
    // En todos esos casos se conserva el error primario y nunca se reintenta fetch aquí.
  }
}

export async function runSupervisedExecuteOperation(
  store,
  execution,
  claims,
  env,
  dependencies,
  executeOperation = runExecuteOperation,
) {
  const clock = dependencies?.clock ?? (() => new Date());
  const reservationId = execution?.requestContext?.reservationId;
  try {
    return await executeOperation(store, execution, claims, env, {
      ...dependencies,
      clock,
    });
  } catch (error) {
    closeReservationBestEffort(
      store,
      reservationId,
      failureReason(error),
      failureTime(clock),
    );
    throw error;
  }
}
