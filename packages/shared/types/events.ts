/**
 * FROID v3.0 - Shared Types
 * LegalEvent interfaces e enums
 * 7 tipos de evento para trilha de auditoria
 */

export type EventType =
  | 'CONSENT_GRANTED'
  | 'CONSENT_REVOKED'
  | 'SESSION_STARTED'
  | 'SESSION_BLOCKED'
  | 'DATA_SHARED'
  | 'DATA_DELETED'
  | 'REPORT_SIGNED';

export type ActorType = 'patient' | 'professional' | 'system' | 'admin';

export type IntegrityStatus = 'valid' | 'tampered' | 'unknown';

export interface LegalEvent {
  eventId: string;
  eventType: EventType;
  actorType: ActorType;
  actorId: string;
  patientId: string;
  professionalId?: string;
  sessionId?: string;
  relatedConsentId?: string;
  legalTextId: string;
  legalTextVersion: string;
  scope?: string;
  purpose?: string;
  eventContext: string;
  timestamp: Date;
  hash: string;
  blockchainTxId?: string;
  integrityStatus: IntegrityStatus;
}