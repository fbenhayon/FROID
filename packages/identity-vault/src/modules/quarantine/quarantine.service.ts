import { Injectable } from '@nestjs/common';
import { prisma } from '../../prisma/client';

@Injectable()
export class QuarantineService {
  async listPending() {
    return prisma.quarantineRecord.findMany({
      where: { status: 'pending_review' },
      orderBy: { requestedAt: 'asc' },
      include: {
        patient: {
          select: { name: true, cpf: true },
        },
      },
    });
  }

  async approve(id: string, reviewedBy: string, notes?: string) {
    const record = await prisma.quarantineRecord.update({
      where: { id },
      data: {
        status: 'approved',
        reviewedBy,
        reviewedAt: new Date(),
        reviewNotes: notes,
      },
    });

    // Deletar permanentemente o paciente
    await prisma.patient.delete({
      where: { id: record.patientId },
    });

    return { message: 'Patient permanently deleted', record };
  }

  async deny(id: string, reviewedBy: string, notes?: string) {
    const record = await prisma.quarantineRecord.update({
      where: { id },
      data: {
        status: 'denied',
        reviewedBy,
        reviewedAt: new Date(),
        reviewNotes: notes,
      },
    });

    // Restaurar visibilidade do paciente
    await prisma.patient.update({
      where: { id: record.patientId },
      data: {
        deletedAt: null,
        visibleToProfessionals: true,
      },
    });

    return { message: 'Deletion denied, patient restored', record };
  }
}
