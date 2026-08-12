export interface Order {
  status: string;
}

export function describe(o: Order): string {
  return `order:${o.status}`;
}
