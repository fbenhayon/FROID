import { Injectable, NotFoundException } from '@nestjs/common';
import { prisma } from '../../prisma/client';

@Injectable()
export class SessionService {
  async create(data: any) {
    const session = await prisma.session.create({
      data: {
        patientId: data.patientId,
        professionalId: data.professionalId,
        scheduledFor: new Date(data.scheduledFor || new Date()),
        status: 'active',
        startedAt: new Date(),
      },
    });
    return session;
  }

  async findByPatient(patientId: string) {
    return prisma.session.findMany({
      where: { patientId },
      orderBy: { startedAt: 'desc' },
      include: {
        voiceAnalyses: true,
        facialAnalyses: true,
      },
    });
  }

  async findOne(id: string) {
    const session = await prisma.session.findUnique({
      where: { id },
      include: {
        patient: true,
        professional: true,
        voiceAnalyses: { orderBy: { timestamp: 'desc' }, take: 10 },
        facialAnalyses: { orderBy: { timestamp: 'desc' }, take: 10 },
      },
    });
    
    if (!session) {
      throw new NotFoundException(`Session ${id} not found`);
    }
    
    return session;
  }

  async endSession(id: string) {
    const session = await prisma.session.update({
      where: { id },
      data: {
        status: 'completed',
        endedAt: new Date(),
      },
    });
    
    return session;
  }
}
