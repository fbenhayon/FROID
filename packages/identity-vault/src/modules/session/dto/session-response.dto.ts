export interface SessionResponseDto {
  sessionId: string;
  patientId: string;
  professionalId: string;
  status: string;
  legalState: string;
  protocol: string;
  requestedScopes: string[];
  effectiveScopes: string[];
  enabledModules: string[];
  blockedModules: string[];
  blockReason?: string;
  topicsPlanned?: string[];
  topicsCovered?: string[];
  notes?: string;
  metadata?: Record<string, any>;
  consentSnapshotHash?: string;
  startedAt: string;
  endedAt?: string;
  createdAt: string;
  updatedAt: string;
}
