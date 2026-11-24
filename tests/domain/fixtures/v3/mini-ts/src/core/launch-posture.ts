const PHASED = 'phased';

export function launchPosture(spec: { power?: boolean }): string {
  if (spec.power && process.env.WICKED_POWER === '1') {
    return 'power';
  }
  return PHASED;
}
