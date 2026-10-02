/**
 * scripts/qe/lib/crew-run.mjs — the crew run a QE ledger row belongs to (WT-G4).
 *
 * A governed worker (a unit of a wicked-crew run) gets `WICKED_RUN_ID` on its
 * environment. Every `runs` and `verdicts` row garden's QE writes inside such a
 * run carries it as a top-level `crew_run_id`, so crew's acceptance reader
 * (`packages/crew/src/qe/ledger.ts`, `stampedCrewRun`) attributes the QE run to
 * the crew run by stamp (`kind: 'stamped'`) instead of inferring it from the run's
 * lifetime. wicked-ledger keeps the key in the record's canonical JSON.
 * Outside a governed run nothing is stamped.
 */

export const CREW_RUN_ID_FIELD = "crew_run_id";
export const GOVERNED_RUN_ENV = "WICKED_RUN_ID";

/** `{ crew_run_id }` to spread into a ledger row, or `{}` outside a governed run. */
export function crewRunStamp(env = process.env) {
  const id = env[GOVERNED_RUN_ENV];
  return typeof id === "string" && id !== "" ? { [CREW_RUN_ID_FIELD]: id } : {};
}
