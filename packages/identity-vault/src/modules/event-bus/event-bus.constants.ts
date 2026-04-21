// packages/identity-vault/src/modules/event-bus/event-bus.constants.ts

export const STREAMS = {
  LEGAL_EVENTS: 'froid:legal-events',       // todos os eventos juridicos
  CONSENT_EVENTS: 'froid:consent-events',   // apenas consentimento (subset)
} as const;

export const CONSUMER_GROUPS = {
  HASH_CHAIN: 'hash-chain-consumer',        // consome para gravar na cadeia
  POLICY_CACHE: 'policy-cache-consumer',    // consome para invalidar cache
  AUDIT_LOG: 'audit-log-consumer',          // consome para log adicional
} as const;
