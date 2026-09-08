import type { HomeRef } from './types';

const FORWARD = /\bB(?:LOQUE)?\s*[:#.-]?\s*(\d{1,3})\s*(?:[-/|,; ]+)?C(?:ASA)?\s*[:#.-]?\s*(\d{1,4})\b/i;
const REVERSE = /\bC(?:ASA)?\s*[:#.-]?\s*(\d{1,4})\s*(?:[-/|,; ]+)?B(?:LOQUE)?\s*[:#.-]?\s*(\d{1,3})\b/i;

export function parseHomeReference(input: string | undefined | null): HomeRef | undefined {
  if (!input) return undefined;
  const normalized = input
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/\s+/g, ' ')
    .trim();

  const forward = normalized.match(FORWARD);
  if (forward) {
    const block = Number.parseInt(forward[1], 10);
    const house = Number.parseInt(forward[2], 10);
    if (isValidHome(block, house)) return { block, house };
  }

  const reverse = normalized.match(REVERSE);
  if (reverse) {
    const house = Number.parseInt(reverse[1], 10);
    const block = Number.parseInt(reverse[2], 10);
    if (isValidHome(block, house)) return { block, house };
  }

  return undefined;
}

export function isValidHome(block: number, house: number): boolean {
  return Number.isInteger(block) && Number.isInteger(house) && block > 0 && block <= 999 && house > 0 && house <= 9999;
}

export function homeLabel(home: HomeRef | undefined): string {
  return home ? `Bloque ${home.block} · Casa ${home.house}` : 'Sin identificar';
}
