import { Injectable, NotFoundException } from '@nestjs/common';
import { prisma } from '../../prisma/client';

@Injectable()
export class PatientService {
  async create(data: any) {
    const patient = await prisma.patient.create({
      data: {
        name: data.name,
        cpf: data.cpf,
        birthDate: new Date(data.birthDate),
        phone: data.phone || null,
        email: data.email || null,
        professionalId: data.professionalId,
      },
    });
    return patient;
  }

  async findByProfessional(professionalId: string) {
    return prisma.patient.findMany({
      where: { 
        professionalId,
        deletedAt: null,
        visibleToProfessionals: true,
      },
      orderBy: { createdAt: 'desc' },
    });
  }

  async findOne(id: string) {
    const patient = await prisma.patient.findUnique({
      where: { id },
      include: {
        sessions: true,
        consentRecords: true,
      },
    });
    
    if (!patient) {
      throw new NotFoundException(`Patient ${id} not found`);
    }
    
    return patient;
  }

  async update(id: string, data: any) {
    const patient = await prisma.patient.update({
      where: { id },
      data: {
        name: data.name,
        phone: data.phone,
        email: data.email,
        updatedAt: new Date(),
      },
    });
    
    return patient;
  }

  async deactivate(id: string) {
    // Soft delete
    const patient = await prisma.patient.update({
      where: { id },
      data: {
        deletedAt: new Date(),
        visibleToProfessionals: false,
      },
    });
    
    return { message: 'Patient deactivated', patient };
  }
}
