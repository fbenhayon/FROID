export type SessionLegalState = 'valid' | 'blocked';
export interface Session {
    sessionId: string;
    patientId: string;
    professionalId: string;
    startedAt: Date;
    endedAt?: Date;
    requestedScopes: string[];
    effectiveScopes: string[];
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
