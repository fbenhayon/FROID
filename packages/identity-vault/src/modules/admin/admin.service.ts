import { Injectable, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';

@Injectable()
export class AdminService {
  constructor(private prisma: PrismaService) {}

  async createPrompt(data: { title?: string; category: string; promptText?: string; text?: string; createdBy?: string; professionalId?: string }) {
    return this.prisma.prompt.create({
      data: {
        text: data.promptText || data.text || '',
        category: data.category,
        professionalId: data.createdBy || data.professionalId || null,
      },
    });
  }

  async getAllPrompts() {
    return this.prisma.prompt.findMany({ orderBy: { createdAt: 'desc' } });
  }

  async getPromptsByCategory(category: string) {
    return this.prisma.prompt.findMany({
      where: { category },
      orderBy: { createdAt: 'desc' },
    });
  }

  async getPromptById(id: string) {
    const prompt = await this.prisma.prompt.findUnique({ where: { id } });
    if (!prompt) throw new NotFoundException('Prompt not found');
    return prompt;
  }

  async updatePrompt(id: string, data: any) {
    await this.getPromptById(id);
    return this.prisma.prompt.update({
      where: { id },
      data: {
        text: data.promptText || data.text,
        category: data.category,
      },
    });
  }

  async deletePrompt(id: string) {
    await this.getPromptById(id);
    return this.prisma.prompt.delete({ where: { id } });
  }

  async togglePromptStatus(id: string) {
    const prompt = await this.getPromptById(id);
    return this.prisma.prompt.update({
      where: { id },
      data: { isDefault: !prompt.isDefault },
    });
  }
}
