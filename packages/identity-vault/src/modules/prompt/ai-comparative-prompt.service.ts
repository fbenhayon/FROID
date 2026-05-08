import { Injectable, ForbiddenException, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';

@Injectable()
export class AIComparativePromptService {
  constructor(private prisma: PrismaService) {}

  // Listar prompts (populacionais + do profissional)
  async listPrompts(userId: string) {
    return this.prisma.aIComparativePrompt.findMany({
      where: {
        OR: [
          { userId: null }, // Prompts populacionais
          { userId }, // Prompts do profissional
          { isPublic: true }, // Prompts públicos de outros
        ],
        isActive: true,
      },
      orderBy: { createdAt: 'desc' },
    });
  }

  // Ver prompt específico
  async getPrompt(id: string, userId: string) {
    const prompt = await this.prisma.aIComparativePrompt.findUnique({
      where: { id },
    });

    if (!prompt) {
      throw new NotFoundException('Prompt não encontrado');
    }

    // Verificar permissão
    if (prompt.userId && prompt.userId !== userId && !prompt.isPublic) {
      throw new ForbiddenException('Acesso negado a este prompt');
    }

    return prompt;
  }

  // Criar prompt
  async createPrompt(userId: string, data: any) {
    return this.prisma.aIComparativePrompt.create({
      data: {
        userId,
        promptType: data.promptType || 'custom',
        demographicFilter: data.demographicFilter,
        promptTemplate: data.promptTemplate,
        description: data.description,
        isPublic: data.isPublic || false,
      },
    });
  }

  // Clonar prompt populacional para editar
  async clonePrompt(id: string, userId: string) {
    const original = await this.prisma.aIComparativePrompt.findUnique({
      where: { id },
    });

    if (!original) {
      throw new NotFoundException('Prompt não encontrado');
    }

    return this.prisma.aIComparativePrompt.create({
      data: {
        userId,
        promptType: 'custom',
        demographicFilter: original.demographicFilter,
        promptTemplate: original.promptTemplate,
        description: `${original.description} (customizado)`,
        isPublic: false,
      },
    });
  }

  // Atualizar prompt (só se owner)
  async updatePrompt(id: string, userId: string, data: any) {
    const prompt = await this.prisma.aIComparativePrompt.findUnique({
      where: { id },
    });

    if (!prompt) {
      throw new NotFoundException('Prompt não encontrado');
    }

    if (prompt.userId !== userId) {
      throw new ForbiddenException('Você não pode editar este prompt');
    }

    return this.prisma.aIComparativePrompt.update({
      where: { id },
      data: {
        promptTemplate: data.promptTemplate,
        description: data.description,
        isPublic: data.isPublic,
        demographicFilter: data.demographicFilter,
      },
    });
  }

  // Deletar prompt (só se owner)
  async deletePrompt(id: string, userId: string) {
    const prompt = await this.prisma.aIComparativePrompt.findUnique({
      where: { id },
    });

    if (!prompt) {
      throw new NotFoundException('Prompt não encontrado');
    }

    if (prompt.userId !== userId) {
      throw new ForbiddenException('Você não pode deletar este prompt');
    }

    return this.prisma.aIComparativePrompt.delete({
      where: { id },
    });
  }
}
