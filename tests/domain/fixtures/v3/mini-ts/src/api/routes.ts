import { startRun } from '../core/launch';
import { listRuns } from '../core/runs';

export function register(app: any) {
  app.post('/runs', (req: any) => {
    return startRun(req.body);
  });
  app.get('/runs', () => listRuns());
}
