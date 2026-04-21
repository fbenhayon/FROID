export const EVENT_TYPES = [
  'CONSENT_GRANTED',
  'CONSENT_REVOKED',
  'CONSENT_DENIED',
  'SESSION_STARTED',     // usado a partir da Entrega 4A
  'SESSION_BLOCKED',     // usado a partir da Entrega 4A
  'SESSION_ENDED',       // usado a partir da Entrega 4A
  'DATA_SHARED',         // usado a partir da Entrega 6
  'DATA_DELETED',        // usado a partir da Entrega 9
  'REPORT_SIGNED',       // usado a partir da Entrega 6
] as const;

export type EventType = typeof EVENT_TYPES[number];
