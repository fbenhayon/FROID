/**
 * FROID v3.0 - Shared Types
 * Session interfaces e enums
 */

export type SessionLegalState = 'valid' | 'blocked';

export interface Session {
  sessionId: string;
  patientId: string;
  professionalId: string;
  startedAt: Date;
  endedAt?: Date;
  requestedScopes: string[]; // o que o profissional pediu
  effectiveScopes: string[]; // intersection calculada pelo Policy Engine
  legalState: SessionLegalState;
  blockReason?: string;
  consentSnapshot: Record<string, unknown>;
  hash: string;
  blockchainTxId?: string;
  createdBy: string;
  tenantId?: string;
  dataClassification: string;
  encryptionKeyId?: string;
  accessLevel: string;
  retentionPolicyId?: string;
}