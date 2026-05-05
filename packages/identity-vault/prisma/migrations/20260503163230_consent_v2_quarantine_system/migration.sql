-- CreateTable
CREATE TABLE "users" (
    "id" TEXT NOT NULL,
    "email" TEXT NOT NULL,
    "password" TEXT NOT NULL,
    "role" TEXT NOT NULL DEFAULT 'professional',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "users_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "professionals" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "crp" TEXT NOT NULL,
    "specialty" TEXT NOT NULL,
    "phone" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "professionals_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "patients" (
    "id" TEXT NOT NULL,
    "professionalId" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "cpf" TEXT NOT NULL,
    "birthDate" TIMESTAMP(3) NOT NULL,
    "phone" TEXT,
    "email" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    "deletedAt" TIMESTAMP(3),
    "visibleToProfessionals" BOOLEAN NOT NULL DEFAULT true,

    CONSTRAINT "patients_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "legal_texts" (
    "id" TEXT NOT NULL,
    "type" TEXT NOT NULL,
    "version" TEXT NOT NULL,
    "content" TEXT NOT NULL,
    "effectiveFrom" TIMESTAMP(3) NOT NULL,
    "expiresAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "legal_texts_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "consent_records" (
    "id" TEXT NOT NULL,
    "patientId" TEXT NOT NULL,
    "professionalId" TEXT NOT NULL,
    "legalTextId" TEXT NOT NULL,
    "version" TEXT NOT NULL DEFAULT '2.0',
    "acceptanceType" TEXT NOT NULL DEFAULT 'general',
    "voiceRecording" BOOLEAN NOT NULL DEFAULT true,
    "facialRecording" BOOLEAN NOT NULL DEFAULT true,
    "biometricAnalysis" BOOLEAN NOT NULL DEFAULT true,
    "clinicalScoring" BOOLEAN NOT NULL DEFAULT true,
    "dataStorage" BOOLEAN NOT NULL DEFAULT true,
    "researchUse" BOOLEAN NOT NULL DEFAULT false,
    "thirdPartySharing" BOOLEAN NOT NULL DEFAULT false,
    "grantedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "appliesFrom" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "expiresAt" TIMESTAMP(3),
    "revokedAt" TIMESTAMP(3),
    "ipAddress" TEXT,
    "userAgent" TEXT,
    "signatureMethod" TEXT NOT NULL DEFAULT 'click',

    CONSTRAINT "consent_records_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "legal_events" (
    "id" TEXT NOT NULL,
    "consentId" TEXT,
    "patientId" TEXT,
    "professionalId" TEXT,
    "eventType" TEXT NOT NULL,
    "description" TEXT,
    "metadata" JSONB,
    "timestamp" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "legal_events_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "quarantine_records" (
    "id" TEXT NOT NULL,
    "patientId" TEXT NOT NULL,
    "professionalId" TEXT NOT NULL,
    "patientSnapshot" JSONB NOT NULL,
    "sessionsSnapshot" JSONB NOT NULL,
    "consentsSnapshot" JSONB NOT NULL,
    "requestedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "requestedBy" TEXT NOT NULL,
    "reason" TEXT,
    "status" TEXT NOT NULL DEFAULT 'pending_review',
    "reviewedBy" TEXT,
    "reviewedAt" TIMESTAMP(3),
    "reviewNotes" TEXT,
    "purgeAt" TIMESTAMP(3) NOT NULL DEFAULT now() + INTERVAL '90 days',

    CONSTRAINT "quarantine_records_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "deletion_requests" (
    "id" TEXT NOT NULL,
    "patientId" TEXT NOT NULL,
    "professionalId" TEXT NOT NULL,
    "requestedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "processedAt" TIMESTAMP(3),
    "status" TEXT NOT NULL DEFAULT 'pending',
    "reason" TEXT,

    CONSTRAINT "deletion_requests_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "sessions" (
    "id" TEXT NOT NULL,
    "patientId" TEXT NOT NULL,
    "professionalId" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'scheduled',
    "scheduledFor" TIMESTAMP(3) NOT NULL,
    "startedAt" TIMESTAMP(3),
    "endedAt" TIMESTAMP(3),
    "notes" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "sessions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "session_consent_snapshots" (
    "id" TEXT NOT NULL,
    "sessionId" TEXT NOT NULL,
    "scopes" JSONB NOT NULL,
    "capturedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "session_consent_snapshots_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "share_records" (
    "id" TEXT NOT NULL,
    "patientId" TEXT NOT NULL,
    "professionalId" TEXT NOT NULL,
    "recipientEmail" TEXT NOT NULL,
    "sharedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "expiresAt" TIMESTAMP(3),
    "accessCount" INTEGER NOT NULL DEFAULT 0,
    "lastAccessedAt" TIMESTAMP(3),

    CONSTRAINT "share_records_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "anonymization_records" (
    "id" TEXT NOT NULL,
    "originalPatientId" TEXT NOT NULL,
    "anonymizedId" TEXT NOT NULL,
    "anonymizedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "retentionUntil" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "anonymization_records_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "hash_chain_blocks" (
    "id" TEXT NOT NULL,
    "sessionId" TEXT NOT NULL,
    "blockIndex" INTEGER NOT NULL,
    "previousHash" TEXT,
    "dataHash" TEXT NOT NULL,
    "timestamp" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "metadata" JSONB,

    CONSTRAINT "hash_chain_blocks_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "voice_analyses" (
    "id" TEXT NOT NULL,
    "sessionId" TEXT NOT NULL,
    "timestamp" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "zonalEnergies" JSONB NOT NULL,
    "dominantZone" TEXT,
    "spectralBands" JSONB NOT NULL,
    "ipmScore" DOUBLE PRECISION,
    "depressionRisk" DOUBLE PRECISION,
    "maniaActivation" DOUBLE PRECISION,
    "stressCognitive" DOUBLE PRECISION,
    "colorCode" TEXT,
    "f0Mean" DOUBLE PRECISION,
    "f0Std" DOUBLE PRECISION,
    "speechRate" DOUBLE PRECISION,
    "rawFeatures" JSONB,

    CONSTRAINT "voice_analyses_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "facial_analyses" (
    "id" TEXT NOT NULL,
    "sessionId" TEXT NOT NULL,
    "timestamp" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "actionUnits" JSONB NOT NULL,
    "dominantEmotion" TEXT,
    "emotionScores" JSONB,
    "expressionPhase" TEXT,
    "apexConfidence" DOUBLE PRECISION,
    "asymmetryScores" JSONB,
    "asymmetryFlags" JSONB,
    "genuineness" DOUBLE PRECISION,
    "rawLandmarks" JSONB,

    CONSTRAINT "facial_analyses_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "fusion_analyses" (
    "id" TEXT NOT NULL,
    "sessionId" TEXT NOT NULL,
    "timestamp" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "congruenceScore" DOUBLE PRECISION,
    "voiceWeight" DOUBLE PRECISION,
    "facialWeight" DOUBLE PRECISION,
    "clinicalContext" TEXT,
    "fusedEmotion" TEXT,
    "fusedConfidence" DOUBLE PRECISION,
    "metadata" JSONB,

    CONSTRAINT "fusion_analyses_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "users_email_key" ON "users"("email");

-- CreateIndex
CREATE UNIQUE INDEX "professionals_userId_key" ON "professionals"("userId");

-- CreateIndex
CREATE UNIQUE INDEX "professionals_crp_key" ON "professionals"("crp");

-- CreateIndex
CREATE UNIQUE INDEX "patients_cpf_key" ON "patients"("cpf");

-- CreateIndex
CREATE INDEX "patients_professionalId_idx" ON "patients"("professionalId");

-- CreateIndex
CREATE INDEX "patients_deletedAt_visibleToProfessionals_idx" ON "patients"("deletedAt", "visibleToProfessionals");

-- CreateIndex
CREATE UNIQUE INDEX "legal_texts_type_version_key" ON "legal_texts"("type", "version");

-- CreateIndex
CREATE INDEX "consent_records_patientId_idx" ON "consent_records"("patientId");

-- CreateIndex
CREATE INDEX "consent_records_professionalId_idx" ON "consent_records"("professionalId");

-- CreateIndex
CREATE INDEX "consent_records_grantedAt_idx" ON "consent_records"("grantedAt");

-- CreateIndex
CREATE INDEX "consent_records_patientId_version_idx" ON "consent_records"("patientId", "version");

-- CreateIndex
CREATE INDEX "legal_events_eventType_idx" ON "legal_events"("eventType");

-- CreateIndex
CREATE INDEX "legal_events_timestamp_idx" ON "legal_events"("timestamp");

-- CreateIndex
CREATE INDEX "legal_events_patientId_idx" ON "legal_events"("patientId");

-- CreateIndex
CREATE INDEX "quarantine_records_status_requestedAt_idx" ON "quarantine_records"("status", "requestedAt");

-- CreateIndex
CREATE INDEX "quarantine_records_purgeAt_idx" ON "quarantine_records"("purgeAt");

-- CreateIndex
CREATE INDEX "quarantine_records_patientId_idx" ON "quarantine_records"("patientId");

-- CreateIndex
CREATE INDEX "deletion_requests_status_idx" ON "deletion_requests"("status");

-- CreateIndex
CREATE INDEX "sessions_patientId_idx" ON "sessions"("patientId");

-- CreateIndex
CREATE INDEX "sessions_professionalId_idx" ON "sessions"("professionalId");

-- CreateIndex
CREATE INDEX "sessions_scheduledFor_idx" ON "sessions"("scheduledFor");

-- CreateIndex
CREATE INDEX "share_records_recipientEmail_idx" ON "share_records"("recipientEmail");

-- CreateIndex
CREATE UNIQUE INDEX "anonymization_records_anonymizedId_key" ON "anonymization_records"("anonymizedId");

-- CreateIndex
CREATE INDEX "hash_chain_blocks_sessionId_idx" ON "hash_chain_blocks"("sessionId");

-- CreateIndex
CREATE UNIQUE INDEX "hash_chain_blocks_sessionId_blockIndex_key" ON "hash_chain_blocks"("sessionId", "blockIndex");

-- CreateIndex
CREATE INDEX "voice_analyses_sessionId_idx" ON "voice_analyses"("sessionId");

-- CreateIndex
CREATE INDEX "facial_analyses_sessionId_idx" ON "facial_analyses"("sessionId");

-- CreateIndex
CREATE INDEX "fusion_analyses_sessionId_idx" ON "fusion_analyses"("sessionId");

-- AddForeignKey
ALTER TABLE "professionals" ADD CONSTRAINT "professionals_userId_fkey" FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "patients" ADD CONSTRAINT "patients_professionalId_fkey" FOREIGN KEY ("professionalId") REFERENCES "professionals"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "consent_records" ADD CONSTRAINT "consent_records_patientId_fkey" FOREIGN KEY ("patientId") REFERENCES "patients"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "consent_records" ADD CONSTRAINT "consent_records_professionalId_fkey" FOREIGN KEY ("professionalId") REFERENCES "professionals"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "consent_records" ADD CONSTRAINT "consent_records_legalTextId_fkey" FOREIGN KEY ("legalTextId") REFERENCES "legal_texts"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "legal_events" ADD CONSTRAINT "legal_events_consentId_fkey" FOREIGN KEY ("consentId") REFERENCES "consent_records"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "quarantine_records" ADD CONSTRAINT "quarantine_records_patientId_fkey" FOREIGN KEY ("patientId") REFERENCES "patients"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "deletion_requests" ADD CONSTRAINT "deletion_requests_patientId_fkey" FOREIGN KEY ("patientId") REFERENCES "patients"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "deletion_requests" ADD CONSTRAINT "deletion_requests_professionalId_fkey" FOREIGN KEY ("professionalId") REFERENCES "professionals"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "sessions" ADD CONSTRAINT "sessions_patientId_fkey" FOREIGN KEY ("patientId") REFERENCES "patients"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "sessions" ADD CONSTRAINT "sessions_professionalId_fkey" FOREIGN KEY ("professionalId") REFERENCES "professionals"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "session_consent_snapshots" ADD CONSTRAINT "session_consent_snapshots_sessionId_fkey" FOREIGN KEY ("sessionId") REFERENCES "sessions"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "share_records" ADD CONSTRAINT "share_records_patientId_fkey" FOREIGN KEY ("patientId") REFERENCES "patients"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "share_records" ADD CONSTRAINT "share_records_professionalId_fkey" FOREIGN KEY ("professionalId") REFERENCES "professionals"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "anonymization_records" ADD CONSTRAINT "anonymization_records_originalPatientId_fkey" FOREIGN KEY ("originalPatientId") REFERENCES "patients"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "hash_chain_blocks" ADD CONSTRAINT "hash_chain_blocks_sessionId_fkey" FOREIGN KEY ("sessionId") REFERENCES "sessions"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "voice_analyses" ADD CONSTRAINT "voice_analyses_sessionId_fkey" FOREIGN KEY ("sessionId") REFERENCES "sessions"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "facial_analyses" ADD CONSTRAINT "facial_analyses_sessionId_fkey" FOREIGN KEY ("sessionId") REFERENCES "sessions"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "fusion_analyses" ADD CONSTRAINT "fusion_analyses_sessionId_fkey" FOREIGN KEY ("sessionId") REFERENCES "sessions"("id") ON DELETE CASCADE ON UPDATE CASCADE;
