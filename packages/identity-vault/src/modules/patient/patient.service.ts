import { Injectable, NotFoundException, ConflictException } from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';
import { Prisma } from '@prisma/client';

@Injectable()
export class PatientService {
  constructor(private readonly prisma: PrismaService) {}

  async create(data: any) {
    try {
      return await this.prisma.patient.create({
        data: {
          name: data.name,
          cpf: data.cpf,
          birthDate: new Date(data.birthDate),
          phone: data.phone || null,
          email: data.email || null,
          professionalId: data.professionalId,
        },
      });
    } catch (error) {
      if (error instanceof Prisma.PrismaClientKnownRequestError && error.code === 'P2002') {
        throw new ConflictException('CPF já cadastrado');
      }
      throw error;
    }
  }

  async findByProfessional(professionalId: string) {
    return this.prisma.patient.findMany({
      where: {
        professionalId,
        visibleToProfessionals: true,
      },
      orderBy: { createdAt: 'desc' },
    });
  }

  async findOne(id: string) {
    const patient = await this.prisma.patient.findUnique({
      where: { id },
      include: {
        sessions: true,
        consents: true,
      },
    });
    if (!patient) {
      throw new NotFoundException(`Patient ${id} not found`);
    }
    return patient;
  }

  async update(id: string, data: any) {
    return this.prisma.patient.update({
      where: { id },
      data: {
        name: data.name,
        phone: data.phone,
        email: data.email,
      },
    });
  }

  async deactivate(id: string) {
    const patient = await this.prisma.patient.update({
      where: { id },
      data: {
        visibleToProfessionals: false,
      },
    });
    return { message: 'Patient deactivated', patient };
  }
}
