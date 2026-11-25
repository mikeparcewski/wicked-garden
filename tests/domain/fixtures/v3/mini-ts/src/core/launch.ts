import { launchPosture } from './launch-posture';

export function startRun(spec: { power?: boolean }) {
  const posture = launchPosture(spec);
  return { started: true, posture };
}
