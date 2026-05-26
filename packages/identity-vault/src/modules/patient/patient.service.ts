import { Injectable, NotFoundException, ConflictException } from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';
import { Prisma } from '@prisma/client';

@Injectable()
export class PatientService {
  constructor(private readonly prisma: PrismaService) {}

  async create(data: any) {
    try {
      let professionalId = data.professionalId;

      // Se o ID não corresponder a um professional, tenta resolver pelo userId
      const prof = await this.prisma.professionals.findFirst({
        where: { OR: [{ id: professionalId }, { userId: professionalId }] },
        select: { id: true },
      });

      if (!prof) {
        throw new NotFoundException(`Profissional não encontrado para id: ${professionalId}`);
      }

      professionalId = prof.id;

      return await this.prisma.patients.create({
        data: {
          name: data.name,
          cpf: data.cpf,
          birthDate: new Date(data.birthDate),
          phone: data.phone || null,
          email: data.email || null,
          professionalId,
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
    const prof = await this.prisma.professionals.findFirst({
      where: { OR: [{ id: professionalId }, { userId: professionalId }] },
      select: { id: true },
    });

    const resolvedId = prof?.id ?? professionalId;

    return this.prisma.patients.findMany({
      where: {
        professionalId: resolvedId,
        deletedAt: null,
        visibleToProfessionals: true,
      },
      orderBy: { createdAt: 'desc' },
    });
  }

  async findOne(id: string) {
    const patient = await this.prisma.patients.findUnique({
      where: { id },
      include: {
        sessions: true,
        consent_records: true,
      },
    });
    if (!patient) {
      throw new NotFoundException(`Patient ${id} not found`);
    }
    return patient;
  }

  async update(id: string, data: any) {
    return this.prisma.patients.update({
      where: { id },
      data: {
        name: data.name,
        phone: data.phone,
        email: data.email,
      },
    });
  }

  async deactivate(id: string) {
    const patient = await this.prisma.patients.update({
      where: { id },
      data: {
        deletedAt: new Date(),
        visibleToProfessionals: false,
      },
    });
    return { message: 'Patient deactivated', patient };
  }
}
