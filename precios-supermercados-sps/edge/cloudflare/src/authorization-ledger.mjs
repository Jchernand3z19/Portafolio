import {
  completeReservation,
  createAuthorizationState,
  failReservation,
  ledgerSummary,
  rejectAuthorization,
  reserveRequest as reserveBaseRequest,
} from "./ledger.mjs";

/**
 * Frontera productiva del ledger.
 *
 * `ledger.mjs` contiene la máquina de estados pura. Esta envoltura añade la
 * política de concurrencia física = 1: un request distinto no puede obtener
 * una nueva reserva mientras exista otra reserva `reserved` sin cierre.
 *
 * La función base se evalúa primero porque valida fail-closed todo el estado y
 * resuelve replays/expiración/presupuesto. Como es pura, descartar un resultado
 * `RESERVED` no muta el estado persistido de entrada.
 */
export function reserveRequest(stateInput, requestInput, nowInput) {
  const result = reserveBaseRequest(stateInput, requestInput, nowInput);
  if (result.decision !== "RESERVED") return result;

  const inFlight = Object.values(stateInput.reservations ?? {}).find(
    (reservation) => reservation?.status === "reserved",
  );
  if (!inFlight) return result;

  return Object.freeze({
    decision: "WAIT",
    reason: "physical_request_in_flight",
    inFlightReservationId: inFlight.reservationId,
    state: stateInput,
  });
}

export {
  completeReservation,
  createAuthorizationState,
  failReservation,
  ledgerSummary,
  rejectAuthorization,
};
