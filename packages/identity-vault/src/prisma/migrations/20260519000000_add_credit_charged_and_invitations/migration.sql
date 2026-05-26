-- AlterTable: adicionar creditCharged em sessions
ALTER TABLE "sessions" ADD COLUMN "creditCharged" BOOLEAN NOT NULL DEFAULT false;

-- CreateTable: sistema de convites
CREATE TABLE "invitations" (
    "id" TEXT NOT NULL,
    "professionalId" TEXT NOT NULL,
    "patientEmail" TEXT NOT NULL,
    "token" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'pending',
    "message" TEXT,
    "expiresAt" TIMESTAMP(3) NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "invitations_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "invitations_token_key" ON "invitations"("token");

-- CreateIndex
CREATE INDEX "invitations_token_idx" ON "invitations"("token");

-- CreateIndex
CREATE INDEX "invitations_professionalId_idx" ON "invitations"("professionalId");

-- CreateIndex
CREATE INDEX "invitations_patientEmail_idx" ON "invitations"("patientEmail");

-- AddForeignKey
ALTER TABLE "invitations" ADD CONSTRAINT "invitations_professionalId_fkey" FOREIGN KEY ("professionalId") REFERENCES "professionals"("id") ON DELETE CASCADE ON UPDATE CASCADE;
