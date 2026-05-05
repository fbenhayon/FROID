/*
  Warnings:

  - Added the required column `audience` to the `legal_texts` table without a default value. This is not possible if the table is not empty.
  - Added the required column `context` to the `legal_texts` table without a default value. This is not possible if the table is not empty.
  - Added the required column `shortText` to the `legal_texts` table without a default value. This is not possible if the table is not empty.
  - Added the required column `title` to the `legal_texts` table without a default value. This is not possible if the table is not empty.

*/
-- AlterTable
ALTER TABLE "legal_texts" ADD COLUMN     "audience" TEXT NOT NULL,
ADD COLUMN     "context" TEXT NOT NULL,
ADD COLUMN     "isBlocking" BOOLEAN NOT NULL DEFAULT true,
ADD COLUMN     "legalBasis" JSONB,
ADD COLUMN     "requiresAction" BOOLEAN NOT NULL DEFAULT true,
ADD COLUMN     "requiresSignature" BOOLEAN NOT NULL DEFAULT false,
ADD COLUMN     "shortText" TEXT NOT NULL,
ADD COLUMN     "showCitationInline" BOOLEAN NOT NULL DEFAULT false,
ADD COLUMN     "title" TEXT NOT NULL;

-- AlterTable
ALTER TABLE "quarantine_records" ALTER COLUMN "purgeAt" SET DEFAULT now() + INTERVAL '90 days';
