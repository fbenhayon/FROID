import { Injectable, NotFoundException, BadRequestException } from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';
import { CreateInvitationDto } from './dto/create-invitation.dto';

const INVITE_EXPIRY_DAYS = 7;
const FRONTEND_URL = process.env.FRONTEND_URL || 'http://204.168.229.32';

@Injectable()
export class InvitationService {
  constructor(private prisma: PrismaService) {}

  async create(dto: CreateInvitationDto) {
    const professional = await this.prisma.professionals.findUnique({
      where: { id: dto.professionalId },
    });
    if (!professional) {
      throw new NotFoundException('Profissional não encontrado');
    }

    const existing = await this.prisma.invitations.findFirst({
      where: {
        professionalId: dto.professionalId,
        patientEmail: dto.patientEmail,
        status: 'pending',
        expiresAt: { gt: new Date() },
      },
    });
    if (existing) {
      throw new BadRequestException('Já existe um convite pendente para este email');
    }

    const expiresAt = new Date();
    expiresAt.setDate(expiresAt.getDate() + INVITE_EXPIRY_DAYS);

    const invitation = await this.prisma.invitations.create({
      data: {
        professionalId: dto.professionalId,
        patientEmail: dto.patientEmail,
        message: dto.message,
        expiresAt,
      },
    });

    const inviteUrl = `${FRONTEND_URL}/convite/${invitation.token}`;

    return {
      id: invitation.id,
      token: invitation.token,
      patientEmail: invitation.patientEmail,
      inviteUrl,
      expiresAt: invitation.expiresAt,
      message: invitation.message,
    };
  }

  async accept(token: string) {
    const invitation = await this.prisma.invitations.findUnique({
      where: { token },
      include: { professionals: true },
    });

    if (!invitation) {
      throw new NotFoundException('Convite não encontrado');
    }

    if (invitation.status !== 'pending') {
      throw new BadRequestException(`Convite já foi ${invitation.status}`);
    }

    if (invitation.expiresAt < new Date()) {
      await this.prisma.invitations.update({
        where: { token },
        data: { status: 'expired' },
      });
      throw new BadRequestException('Convite expirado');
    }

    await this.prisma.invitations.update({
      where: { token },
      data: { status: 'accepted' },
    });

    return {
      accepted: true,
      patientEmail: invitation.patientEmail,
      professional: {
        id: invitation.professionals.id,
        name: invitation.professionals.name,
        specialty: invitation.professionals.specialty,
      },
    };
  }

  async findByProfessional(professionalId: string) {
    return this.prisma.invitations.findMany({
      where: { professionalId },
      orderBy: { createdAt: 'desc' },
      select: {
        id: true,
        patientEmail: true,
        status: true,
        expiresAt: true,
        createdAt: true,
        message: true,
      },
    });
  }

  async cancel(id: string, professionalId: string) {
    const invitation = await this.prisma.invitations.findFirst({
      where: { id, professionalId },
    });

    if (!invitation) {
      throw new NotFoundException('Convite não encontrado');
    }

    return this.prisma.invitations.update({
      where: { id },
      data: { status: 'cancelled' },
    });
  }
}
