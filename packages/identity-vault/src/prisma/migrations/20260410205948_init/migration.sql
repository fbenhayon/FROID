-- CreateTable
CREATE TABLE "Patient" (
    "id" TEXT NOT NULL,
    "fullName" TEXT NOT NULL,
    "cpf" TEXT NOT NULL,
    "email" TEXT NOT NULL,
    "phone" TEXT,
    "dateOfBirth" TIMESTAMP(3) NOT NULL,
    "gender" TEXT NOT NULL,
    "region" TEXT NOT NULL,
    "guardianId" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    "tenantId" TEXT,
    "dataClassification" TEXT NOT NULL DEFAULT 'sensitive',

    CONSTRAINT "Patient_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Professional" (
    "id" TEXT NOT NULL,
    "fullName" TEXT NOT NULL,
    "cpf" TEXT NOT NULL,
    "email" TEXT NOT NULL,
    "registrationNumber" TEXT NOT NULL,
    "registrationType" TEXT NOT NULL,
    "specialty" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    "tenantId" TEXT,

    CONSTRAINT "Professional_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "LegalText" (
    "legalTextId" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "type" TEXT NOT NULL,
    "audience" TEXT NOT NULL,
    "context" TEXT NOT NULL,
    "shortText" TEXT NOT NULL,
    "expandedText" TEXT NOT NULL,
    "version" TEXT NOT NULL,
    "isBlocking" BOOLEAN NOT NULL DEFAULT true,
    "requiresAction" BOOLEAN NOT NULL DEFAULT true,
    "requiresSignature" BOOLEAN NOT NULL DEFAULT false,
    "showCitationInline" BOOLEAN NOT NULL DEFAULT false,
    "showCitationDetails" BOOLEAN NOT NULL DEFAULT true,
    "effectiveFrom" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "effectiveTo" TIMESTAMP(3),
    "supersedes" TEXT,
    "legalBasis" JSONB NOT NULL,
    "uiComponent" TEXT NOT NULL,
    "enforcementRuleId" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "LegalText_pkey" PRIMARY KEY ("legalTextId")
);

-- CreateTable
CREATE TABLE "ConsentRecord" (
    "consentId" TEXT NOT NULL,
    "patientId" TEXT NOT NULL,
    "professionalId" TEXT,
    "sessionId" TEXT,
    "scope" TEXT NOT NULL,
    "purpose" TEXT NOT NULL,
    "status" TEXT NOT NULL,
    "legalTextId" TEXT NOT NULL,
    "legalTextVersion" TEXT NOT NULL,
    "grantedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "revokedAt" TIMESTAMP(3),
    "expiresAt" TIMESTAMP(3),
    "collectionContext" TEXT NOT NULL,
    "ipAddress" TEXT NOT NULL,
    "userAgent" TEXT NOT NULL,
    "geoLocation" TEXT,
    "hash" TEXT NOT NULL,
    "blockchainTxId" TEXT,
    "proofUri" TEXT,
    "createdBy" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    "tenantId" TEXT,
    "dataClassification" TEXT NOT NULL DEFAULT 'sensitive',
    "encryptionKeyId" TEXT,
    "accessLevel" TEXT NOT NULL DEFAULT 'restricted',
    "retentionPolicyId" TEXT,
    "legalBasisSnapshot" JSONB,
    "processingPurpose" TEXT,
    "dataOrigin" TEXT NOT NULL DEFAULT 'user_input',
    "processingType" TEXT NOT NULL DEFAULT 'collection',

    CONSTRAINT "ConsentRecord_pkey" PRIMARY KEY ("consentId")
);

-- CreateTable
CREATE TABLE "LegalEvent" (
    "eventId" TEXT NOT NULL,
    "eventType" TEXT NOT NULL,
    "actorType" TEXT NOT NULL,
    "actorId" TEXT NOT NULL,
    "patientId" TEXT NOT NULL,
    "professionalId" TEXT,
    "sessionId" TEXT,
    "relatedConsentId" TEXT,
    "legalTextId" TEXT NOT NULL,
    "legalTextVersion" TEXT NOT NULL,
    "scope" TEXT,
    "purpose" TEXT,
    "eventContext" TEXT NOT NULL,
    "timestamp" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "hash" TEXT NOT NULL,
    "blockchainTxId" TEXT,
    "integrityStatus" TEXT NOT NULL DEFAULT 'valid',

    CONSTRAINT "LegalEvent_pkey" PRIMARY KEY ("eventId")
);

-- CreateTable
CREATE TABLE "Session" (
    "sessionId" TEXT NOT NULL,
    "patientId" TEXT NOT NULL,
    "professionalId" TEXT NOT NULL,
    "startedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "endedAt" TIMESTAMP(3),
    "requestedScopes" JSONB NOT NULL,
    "effectiveScopes" JSONB NOT NULL,
    "legalState" TEXT NOT NULL DEFAULT 'valid',
    "blockReason" TEXT,
    "consentSnapshot" JSONB NOT NULL,
    "hash" TEXT NOT NULL,
    "blockchainTxId" TEXT,
    "createdBy" TEXT NOT NULL,
    "tenantId" TEXT,
    "dataClassification" TEXT NOT NULL DEFAULT 'sensitive',
    "encryptionKeyId" TEXT,
    "accessLevel" TEXT NOT NULL DEFAULT 'restricted',
    "retentionPolicyId" TEXT,

    CONSTRAINT "Session_pkey" PRIMARY KEY ("sessionId")
);

-- CreateTable
CREATE TABLE "ShareRecord" (
    "shareId" TEXT NOT NULL,
    "reportId" TEXT NOT NULL,
    "patientId" TEXT NOT NULL,
    "professionalId" TEXT NOT NULL,
    "recipient" TEXT NOT NULL,
    "recipientType" TEXT NOT NULL,
    "purpose" TEXT NOT NULL,
    "scope" TEXT NOT NULL,
    "expiresAt" TIMESTAMP(3) NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "hash" TEXT NOT NULL,
    "blockchainTxId" TEXT NOT NULL,

    CONSTRAINT "ShareRecord_pkey" PRIMARY KEY ("shareId")
);

-- CreateTable
CREATE TABLE "DeletionRequest" (
    "requestId" TEXT NOT NULL,
    "patientId" TEXT NOT NULL,
    "requestedBy" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'pending',
    "requestedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "completedAt" TIMESTAMP(3),
    "steps" JSONB NOT NULL,
    "proofHash" TEXT,
    "blockchainTxId" TEXT,

    CONSTRAINT "DeletionRequest_pkey" PRIMARY KEY ("requestId")
);

-- CreateTable
CREATE TABLE "AnonymizationRecord" (
    "recordId" TEXT NOT NULL,
    "sourceSessionId" TEXT NOT NULL,
    "anonymized" BOOLEAN NOT NULL DEFAULT true,
    "riskScore" DOUBLE PRECISION NOT NULL,
    "approved" BOOLEAN NOT NULL,
    "rejectionReason" TEXT,
    "quarantine" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "datasetId" TEXT,

    CONSTRAINT "AnonymizationRecord_pkey" PRIMARY KEY ("recordId")
);

-- CreateIndex
CREATE UNIQUE INDEX "Patient_cpf_key" ON "Patient"("cpf");

-- CreateIndex
CREATE UNIQUE INDEX "Patient_email_key" ON "Patient"("email");

-- CreateIndex
CREATE UNIQUE INDEX "Professional_cpf_key" ON "Professional"("cpf");

-- CreateIndex
CREATE UNIQUE INDEX "Professional_email_key" ON "Professional"("email");

-- CreateIndex
CREATE INDEX "ConsentRecord_patientId_idx" ON "ConsentRecord"("patientId");

-- CreateIndex
CREATE INDEX "ConsentRecord_scope_status_idx" ON "ConsentRecord"("scope", "status");

-- CreateIndex
CREATE INDEX "ConsentRecord_legalTextId_idx" ON "ConsentRecord"("legalTextId");

-- CreateIndex
CREATE INDEX "ConsentRecord_sessionId_idx" ON "ConsentRecord"("sessionId");

-- CreateIndex
CREATE INDEX "LegalEvent_patientId_idx" ON "LegalEvent"("patientId");

-- CreateIndex
CREATE INDEX "LegalEvent_eventType_idx" ON "LegalEvent"("eventType");

-- CreateIndex
CREATE INDEX "LegalEvent_sessionId_idx" ON "LegalEvent"("sessionId");

-- AddForeignKey
ALTER TABLE "ConsentRecord" ADD CONSTRAINT "ConsentRecord_patientId_fkey" FOREIGN KEY ("patientId") REFERENCES "Patient"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ConsentRecord" ADD CONSTRAINT "ConsentRecord_professionalId_fkey" FOREIGN KEY ("professionalId") REFERENCES "Professional"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ConsentRecord" ADD CONSTRAINT "ConsentRecord_legalTextId_fkey" FOREIGN KEY ("legalTextId") REFERENCES "LegalText"("legalTextId") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "LegalEvent" ADD CONSTRAINT "LegalEvent_relatedConsentId_fkey" FOREIGN KEY ("relatedConsentId") REFERENCES "ConsentRecord"("consentId") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Session" ADD CONSTRAINT "Session_patientId_fkey" FOREIGN KEY ("patientId") REFERENCES "Patient"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Session" ADD CONSTRAINT "Session_professionalId_fkey" FOREIGN KEY ("professionalId") REFERENCES "Professional"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "DeletionRequest" ADD CONSTRAINT "DeletionRequest_patientId_fkey" FOREIGN KEY ("patientId") REFERENCES "Patient"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
