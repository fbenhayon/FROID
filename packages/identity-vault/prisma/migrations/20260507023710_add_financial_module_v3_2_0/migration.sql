/*
  Warnings:

  - You are about to drop the column `actionUnits` on the `facial_analyses` table. All the data in the column will be lost.
  - You are about to drop the column `apexConfidence` on the `facial_analyses` table. All the data in the column will be lost.
  - You are about to drop the column `asymmetryFlags` on the `facial_analyses` table. All the data in the column will be lost.
  - You are about to drop the column `asymmetryScores` on the `facial_analyses` table. All the data in the column will be lost.
  - You are about to drop the column `dominantEmotion` on the `facial_analyses` table. All the data in the column will be lost.
  - You are about to drop the column `emotionScores` on the `facial_analyses` table. All the data in the column will be lost.
  - You are about to drop the column `expressionPhase` on the `facial_analyses` table. All the data in the column will be lost.
  - You are about to drop the column `genuineness` on the `facial_analyses` table. All the data in the column will be lost.
  - You are about to drop the column `rawLandmarks` on the `facial_analyses` table. All the data in the column will be lost.
  - You are about to drop the column `timestamp` on the `facial_analyses` table. All the data in the column will be lost.
  - You are about to drop the column `clinicalContext` on the `fusion_analyses` table. All the data in the column will be lost.
  - You are about to drop the column `congruenceScore` on the `fusion_analyses` table. All the data in the column will be lost.
  - You are about to drop the column `facialWeight` on the `fusion_analyses` table. All the data in the column will be lost.
  - You are about to drop the column `fusedConfidence` on the `fusion_analyses` table. All the data in the column will be lost.
  - You are about to drop the column `fusedEmotion` on the `fusion_analyses` table. All the data in the column will be lost.
  - You are about to drop the column `metadata` on the `fusion_analyses` table. All the data in the column will be lost.
  - You are about to drop the column `timestamp` on the `fusion_analyses` table. All the data in the column will be lost.
  - You are about to drop the column `voiceWeight` on the `fusion_analyses` table. All the data in the column will be lost.
  - You are about to drop the column `expiresAt` on the `legal_texts` table. All the data in the column will be lost.
  - You are about to drop the column `deletedAt` on the `patients` table. All the data in the column will be lost.
  - You are about to drop the column `phone` on the `professionals` table. All the data in the column will be lost.
  - You are about to drop the column `notes` on the `sessions` table. All the data in the column will be lost.
  - You are about to drop the column `colorCode` on the `voice_analyses` table. All the data in the column will be lost.
  - You are about to drop the column `depressionRisk` on the `voice_analyses` table. All the data in the column will be lost.
  - You are about to drop the column `dominantZone` on the `voice_analyses` table. All the data in the column will be lost.
  - You are about to drop the column `f0Mean` on the `voice_analyses` table. All the data in the column will be lost.
  - You are about to drop the column `f0Std` on the `voice_analyses` table. All the data in the column will be lost.
  - You are about to drop the column `ipmScore` on the `voice_analyses` table. All the data in the column will be lost.
  - You are about to drop the column `maniaActivation` on the `voice_analyses` table. All the data in the column will be lost.
  - You are about to drop the column `rawFeatures` on the `voice_analyses` table. All the data in the column will be lost.
  - You are about to drop the column `spectralBands` on the `voice_analyses` table. All the data in the column will be lost.
  - You are about to drop the column `speechRate` on the `voice_analyses` table. All the data in the column will be lost.
  - You are about to drop the column `stressCognitive` on the `voice_analyses` table. All the data in the column will be lost.
  - You are about to drop the column `timestamp` on the `voice_analyses` table. All the data in the column will be lost.
  - You are about to drop the column `zonalEnergies` on the `voice_analyses` table. All the data in the column will be lost.
  - You are about to drop the `anonymization_records` table. If the table is not empty, all the data it contains will be lost.
  - You are about to drop the `consent_records` table. If the table is not empty, all the data it contains will be lost.
  - You are about to drop the `deletion_requests` table. If the table is not empty, all the data it contains will be lost.
  - You are about to drop the `hash_chain_blocks` table. If the table is not empty, all the data it contains will be lost.
  - You are about to drop the `legal_events` table. If the table is not empty, all the data it contains will be lost.
  - You are about to drop the `quarantine_records` table. If the table is not empty, all the data it contains will be lost.
  - You are about to drop the `session_consent_snapshots` table. If the table is not empty, all the data it contains will be lost.
  - You are about to drop the `share_records` table. If the table is not empty, all the data it contains will be lost.
  - A unique constraint covering the columns `[googleId]` on the table `users` will be added. If there are existing duplicate values, this will fail.
  - Added the required column `data` to the `facial_analyses` table without a default value. This is not possible if the table is not empty.
  - Added the required column `data` to the `fusion_analyses` table without a default value. This is not possible if the table is not empty.
  - Added the required column `ipmScore` to the `fusion_analyses` table without a default value. This is not possible if the table is not empty.
  - Made the column `startedAt` on table `sessions` required. This step will fail if there are existing NULL values in that column.
  - Added the required column `data` to the `voice_analyses` table without a default value. This is not possible if the table is not empty.

*/
-- DropForeignKey
ALTER TABLE "anonymization_records" DROP CONSTRAINT "anonymization_records_originalPatientId_fkey";

-- DropForeignKey
ALTER TABLE "consent_records" DROP CONSTRAINT "consent_records_legalTextId_fkey";

-- DropForeignKey
ALTER TABLE "consent_records" DROP CONSTRAINT "consent_records_patientId_fkey";

-- DropForeignKey
ALTER TABLE "consent_records" DROP CONSTRAINT "consent_records_professionalId_fkey";

-- DropForeignKey
ALTER TABLE "deletion_requests" DROP CONSTRAINT "deletion_requests_patientId_fkey";

-- DropForeignKey
ALTER TABLE "deletion_requests" DROP CONSTRAINT "deletion_requests_professionalId_fkey";

-- DropForeignKey
ALTER TABLE "hash_chain_blocks" DROP CONSTRAINT "hash_chain_blocks_sessionId_fkey";

-- DropForeignKey
ALTER TABLE "legal_events" DROP CONSTRAINT "legal_events_consentId_fkey";

-- DropForeignKey
ALTER TABLE "patients" DROP CONSTRAINT "patients_professionalId_fkey";

-- DropForeignKey
ALTER TABLE "quarantine_records" DROP CONSTRAINT "quarantine_records_patientId_fkey";

-- DropForeignKey
ALTER TABLE "session_consent_snapshots" DROP CONSTRAINT "session_consent_snapshots_sessionId_fkey";

-- DropForeignKey
ALTER TABLE "sessions" DROP CONSTRAINT "sessions_patientId_fkey";

-- DropForeignKey
ALTER TABLE "sessions" DROP CONSTRAINT "sessions_professionalId_fkey";

-- DropForeignKey
ALTER TABLE "share_records" DROP CONSTRAINT "share_records_patientId_fkey";

-- DropForeignKey
ALTER TABLE "share_records" DROP CONSTRAINT "share_records_professionalId_fkey";

-- DropIndex
DROP INDEX "facial_analyses_sessionId_idx";

-- DropIndex
DROP INDEX "fusion_analyses_sessionId_idx";

-- DropIndex
DROP INDEX "legal_texts_type_version_key";

-- DropIndex
DROP INDEX "patients_deletedAt_visibleToProfessionals_idx";

-- DropIndex
DROP INDEX "patients_professionalId_idx";

-- DropIndex
DROP INDEX "sessions_patientId_idx";

-- DropIndex
DROP INDEX "sessions_professionalId_idx";

-- DropIndex
DROP INDEX "sessions_scheduledFor_idx";

-- DropIndex
DROP INDEX "voice_analyses_sessionId_idx";

-- AlterTable
ALTER TABLE "facial_analyses" DROP COLUMN "actionUnits",
DROP COLUMN "apexConfidence",
DROP COLUMN "asymmetryFlags",
DROP COLUMN "asymmetryScores",
DROP COLUMN "dominantEmotion",
DROP COLUMN "emotionScores",
DROP COLUMN "expressionPhase",
DROP COLUMN "genuineness",
DROP COLUMN "rawLandmarks",
DROP COLUMN "timestamp",
ADD COLUMN     "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
ADD COLUMN     "data" JSONB NOT NULL;

-- AlterTable
ALTER TABLE "fusion_analyses" DROP COLUMN "clinicalContext",
DROP COLUMN "congruenceScore",
DROP COLUMN "facialWeight",
DROP COLUMN "fusedConfidence",
DROP COLUMN "fusedEmotion",
DROP COLUMN "metadata",
DROP COLUMN "timestamp",
DROP COLUMN "voiceWeight",
ADD COLUMN     "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
ADD COLUMN     "data" JSONB NOT NULL,
ADD COLUMN     "ipmScore" DOUBLE PRECISION NOT NULL;

-- AlterTable
ALTER TABLE "legal_texts" DROP COLUMN "expiresAt",
ADD COLUMN     "active" BOOLEAN NOT NULL DEFAULT true,
ADD COLUMN     "updatedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
ADD COLUMN     "visibleToProfessionals" BOOLEAN NOT NULL DEFAULT true,
ALTER COLUMN "effectiveFrom" SET DEFAULT CURRENT_TIMESTAMP,
ALTER COLUMN "audience" DROP NOT NULL,
ALTER COLUMN "context" DROP NOT NULL,
ALTER COLUMN "isBlocking" SET DEFAULT false,
ALTER COLUMN "legalBasis" SET DATA TYPE TEXT,
ALTER COLUMN "requiresAction" SET DEFAULT false,
ALTER COLUMN "shortText" DROP NOT NULL;

-- AlterTable
ALTER TABLE "patients" DROP COLUMN "deletedAt",
ADD COLUMN     "clinicId" TEXT,
ADD COLUMN     "sharedWith" TEXT[] DEFAULT ARRAY[]::TEXT[];

-- AlterTable
ALTER TABLE "professionals" DROP COLUMN "phone",
ADD COLUMN     "bio" TEXT,
ALTER COLUMN "specialty" DROP NOT NULL;

-- AlterTable
ALTER TABLE "sessions" DROP COLUMN "notes",
ADD COLUMN     "clinicId" TEXT,
ADD COLUMN     "clinicalNotes" TEXT,
ADD COLUMN     "creditCharged" BOOLEAN NOT NULL DEFAULT false,
ALTER COLUMN "status" SET DEFAULT 'active',
ALTER COLUMN "startedAt" SET NOT NULL,
ALTER COLUMN "startedAt" SET DEFAULT CURRENT_TIMESTAMP;

-- AlterTable
ALTER TABLE "users" ADD COLUMN     "googleId" TEXT,
ADD COLUMN     "name" TEXT NOT NULL DEFAULT '',
ADD COLUMN     "picture" TEXT;

-- AlterTable
ALTER TABLE "voice_analyses" DROP COLUMN "colorCode",
DROP COLUMN "depressionRisk",
DROP COLUMN "dominantZone",
DROP COLUMN "f0Mean",
DROP COLUMN "f0Std",
DROP COLUMN "ipmScore",
DROP COLUMN "maniaActivation",
DROP COLUMN "rawFeatures",
DROP COLUMN "spectralBands",
DROP COLUMN "speechRate",
DROP COLUMN "stressCognitive",
DROP COLUMN "timestamp",
DROP COLUMN "zonalEnergies",
ADD COLUMN     "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
ADD COLUMN     "data" JSONB NOT NULL;

-- DropTable
DROP TABLE "anonymization_records";

-- DropTable
DROP TABLE "consent_records";

-- DropTable
DROP TABLE "deletion_requests";

-- DropTable
DROP TABLE "hash_chain_blocks";

-- DropTable
DROP TABLE "legal_events";

-- DropTable
DROP TABLE "quarantine_records";

-- DropTable
DROP TABLE "session_consent_snapshots";

-- DropTable
DROP TABLE "share_records";

-- CreateTable
CREATE TABLE "consents" (
    "id" TEXT NOT NULL,
    "patientId" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "legalTextId" TEXT NOT NULL,
    "accepted" BOOLEAN NOT NULL DEFAULT false,
    "ipAddress" TEXT,
    "userAgent" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "consents_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "subscriptions" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "planType" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'active',
    "creditsTotal" INTEGER NOT NULL,
    "creditsUsed" INTEGER NOT NULL DEFAULT 0,
    "creditsRemaining" INTEGER NOT NULL,
    "startDate" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "expiryDate" TIMESTAMP(3),
    "amount" DECIMAL(10,2) NOT NULL,
    "paymentMethod" TEXT NOT NULL,
    "transactionId" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "subscriptions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "transactions" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "type" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'pending',
    "amount" DECIMAL(10,2) NOT NULL,
    "paymentMethod" TEXT NOT NULL,
    "pixQrCode" TEXT,
    "pixQrCodeBase64" TEXT,
    "pixTxId" TEXT,
    "gateway" TEXT,
    "gatewayOrderId" TEXT,
    "gatewayPaymentId" TEXT,
    "metadata" JSONB,
    "paidAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "transactions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "clinics" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "cnpj" TEXT NOT NULL,
    "adminId" TEXT NOT NULL,
    "planType" TEXT NOT NULL,
    "maxProfessionals" INTEGER NOT NULL DEFAULT 3,
    "address" TEXT,
    "phone" TEXT,
    "email" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "clinics_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "clinic_members" (
    "id" TEXT NOT NULL,
    "clinicId" TEXT NOT NULL,
    "professionalId" TEXT NOT NULL,
    "role" TEXT NOT NULL DEFAULT 'professional',
    "canViewAll" BOOLEAN NOT NULL DEFAULT false,
    "joinedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "clinic_members_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "prompts" (
    "id" TEXT NOT NULL,
    "professionalId" TEXT,
    "text" TEXT NOT NULL,
    "category" TEXT NOT NULL,
    "customizable" BOOLEAN NOT NULL DEFAULT false,
    "isDefault" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "prompts_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "consents_patientId_legalTextId_key" ON "consents"("patientId", "legalTextId");

-- CreateIndex
CREATE UNIQUE INDEX "subscriptions_transactionId_key" ON "subscriptions"("transactionId");

-- CreateIndex
CREATE INDEX "subscriptions_userId_status_idx" ON "subscriptions"("userId", "status");

-- CreateIndex
CREATE UNIQUE INDEX "transactions_pixTxId_key" ON "transactions"("pixTxId");

-- CreateIndex
CREATE UNIQUE INDEX "transactions_gatewayOrderId_key" ON "transactions"("gatewayOrderId");

-- CreateIndex
CREATE UNIQUE INDEX "transactions_gatewayPaymentId_key" ON "transactions"("gatewayPaymentId");

-- CreateIndex
CREATE INDEX "transactions_userId_status_idx" ON "transactions"("userId", "status");

-- CreateIndex
CREATE INDEX "transactions_gatewayOrderId_idx" ON "transactions"("gatewayOrderId");

-- CreateIndex
CREATE UNIQUE INDEX "clinics_cnpj_key" ON "clinics"("cnpj");

-- CreateIndex
CREATE UNIQUE INDEX "clinic_members_clinicId_professionalId_key" ON "clinic_members"("clinicId", "professionalId");

-- CreateIndex
CREATE UNIQUE INDEX "users_googleId_key" ON "users"("googleId");

-- AddForeignKey
ALTER TABLE "patients" ADD CONSTRAINT "patients_professionalId_fkey" FOREIGN KEY ("professionalId") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "patients" ADD CONSTRAINT "patients_clinicId_fkey" FOREIGN KEY ("clinicId") REFERENCES "clinics"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "sessions" ADD CONSTRAINT "sessions_patientId_fkey" FOREIGN KEY ("patientId") REFERENCES "patients"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "sessions" ADD CONSTRAINT "sessions_professionalId_fkey" FOREIGN KEY ("professionalId") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "sessions" ADD CONSTRAINT "sessions_clinicId_fkey" FOREIGN KEY ("clinicId") REFERENCES "clinics"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "consents" ADD CONSTRAINT "consents_patientId_fkey" FOREIGN KEY ("patientId") REFERENCES "patients"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "consents" ADD CONSTRAINT "consents_userId_fkey" FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "consents" ADD CONSTRAINT "consents_legalTextId_fkey" FOREIGN KEY ("legalTextId") REFERENCES "legal_texts"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "subscriptions" ADD CONSTRAINT "subscriptions_userId_fkey" FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "subscriptions" ADD CONSTRAINT "subscriptions_transactionId_fkey" FOREIGN KEY ("transactionId") REFERENCES "transactions"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "transactions" ADD CONSTRAINT "transactions_userId_fkey" FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "clinics" ADD CONSTRAINT "clinics_adminId_fkey" FOREIGN KEY ("adminId") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "clinic_members" ADD CONSTRAINT "clinic_members_clinicId_fkey" FOREIGN KEY ("clinicId") REFERENCES "clinics"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "clinic_members" ADD CONSTRAINT "clinic_members_professionalId_fkey" FOREIGN KEY ("professionalId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
