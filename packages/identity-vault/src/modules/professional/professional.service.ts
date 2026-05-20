import { Injectable, NotFoundException, ConflictException } from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';
import { CreateProfessionalDto, UpdateProfessionalDto } from './professional.dto';
import { Prisma } from '@prisma/client';

@Injectable()
export class ProfessionalService {
  constructor(private readonly prisma: PrismaService) {}

  async create(dto: CreateProfessionalDto) {
    try {
      return await this.prisma.professionals.create({ data: dto });
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
    const professional = await this.prisma.professionals.findUnique({
      where: { id },
    });
    if (!professional) {
      throw new NotFoundException('Profissional nao encontrado');
    }
    return professional;
  }

  async update(id: string, dto: UpdateProfessionalDto) {
    await this.findOne(id);
    return this.prisma.professionals.update({ where: { id }, data: dto });
  }
}
