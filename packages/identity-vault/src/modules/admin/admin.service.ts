import { Injectable } from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';

@Injectable()
export class AdminService {
  constructor(private prisma: PrismaService) {}

  // Abonar créditos para qualquer usuário
  async grantCredits(userId: string, credits: number, reason: string) {
    const subscription = await this.prisma.subscription.findFirst({
      where: { userId, status: 'active' },
      orderBy: { createdAt: 'desc' },
    });

    if (subscription) {
      return this.prisma.subscription.update({
        where: { id: subscription.id },
        data: {
          creditsTotal: subscription.creditsTotal + credits,
          creditsRemaining: subscription.creditsRemaining + credits,
        },
      });
    }

    // Se não tem subscription, criar uma grátis
    return this.prisma.subscription.create({
      data: {
        userId,
        planType: 'admin_granted',
        status: 'active',
        creditsTotal: credits,
        creditsRemaining: credits,
        amount: 0,
        paymentMethod: 'admin_grant',
      },
    });
  }

  // Cancelar qualquer subscription
  async cancelSubscription(subscriptionId: string, reason: string) {
    return this.prisma.subscription.update({
      where: { id: subscriptionId },
      data: { status: 'cancelled' },
    });
  }

  // Listar TODOS os usuários
  async getAllUsers() {
    return this.prisma.user.findMany({
      include: {
        professional: true,
        subscriptions: { where: { status: 'active' } },
      },
    });
  }

  // Ver TODAS as transações
  async getAllTransactions() {
    return this.prisma.transaction.findMany({
      include: { user: true },
      orderBy: { createdAt: 'desc' },
    });
  }

  // Executar SQL direto (CUIDADO!)
  async executeSQL(query: string) {
    return this.prisma.$queryRawUnsafe(query);
  }

  // Ver logs de qualquer sessão
  async getSessionLogs(sessionId?: string) {
    const where = sessionId ? { id: sessionId } : {};
    return this.prisma.session.findMany({
      where,
      include: {
        patient: true,
        professional: true,
        voiceAnalyses: true,
        facialAnalyses: true,
        fusionAnalyses: true,
      },
    });
  }

  // Estatísticas gerais do sistema
  async getSystemStats() {
    const [
      totalUsers,
      totalProfessionals,
      totalPatients,
      totalSessions,
      activeSubscriptions,
      totalRevenue,
    ] = await Promise.all([
      this.prisma.user.count(),
      this.prisma.professional.count(),
      this.prisma.patient.count(),
      this.prisma.session.count(),
      this.prisma.subscription.count({ where: { status: 'active' } }),
      this.prisma.transaction.aggregate({
        where: { status: 'paid' },
        _sum: { amount: true },
      }),
    ]);

    return {
      totalUsers,
      totalProfessionals,
      totalPatients,
      totalSessions,
      activeSubscriptions,
      totalRevenue: totalRevenue._sum.amount || 0,
    };
  }
}
