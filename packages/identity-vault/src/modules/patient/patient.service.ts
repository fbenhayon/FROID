import { Injectable, NotFoundException, ConflictException } from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';
import { CreatePatientDto, UpdatePatientDto } from './patient.dto';
import { Prisma } from '@prisma/client';

@Injectable()
export class PatientService {
  constructor(private readonly prisma: PrismaService) {}

  async create(dto: CreatePatientDto) {
    try {
      return await this.prisma.patient.create({
        data: {
          ...dto,
          dateOfBirth: new Date(dto.dateOfBirth),
        },
      });
    } catch (error) {
      if (
        error instanceof Prisma.PrismaClientKnownRequestError &&
        error.code === 'P2002'
      ) {
        throw new ConflictException('CPF ou e-mail ja cadastrado (conflito)');
      }
      throw error;
    }
  }

  async findOne(id: string) {
    const patient = await this.prisma.patient.findUnique({ where: { id } });
    if (!patient) {
      throw new NotFoundException('Paciente nao encontrado');
    }
    return patient; // dataClassification = "sensitive" retornado por padrao
  }

  async update(id: string, dto: UpdatePatientDto) {
    await this.findOne(id);
    return this.prisma.patient.update({ where: { id }, data: dto });
  }

  async deactivate(id: string) {
    // Entrega 1: apenas sinalizacao. Exclusao permanente = Entrega 9 (LGPD Art. 18)
    await this.findOne(id);
    return {
      message: 'Paciente desativado. A exclusao permanente dos dados requer o processamento da Entrega 9 (LGPD Art. 18).',
      patientId: id,
      status: 'deactivation_flagged',
    };
  }
}