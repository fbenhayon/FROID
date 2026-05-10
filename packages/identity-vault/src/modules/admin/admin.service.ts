import { Injectable, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';

@Injectable()
export class AdminService {
  constructor(private prisma: PrismaService) {}

  async createPrompt(data: { title: string; category: string; promptText: string; createdBy?: string }) {
    return this.prisma.clinicPrompt.create({ data });
  }

  async getAllPrompts() {
    return this.prisma.clinicPrompt.findMany({ orderBy: { createdAt: 'desc' } });
  }

  async getPromptsByCategory(category: string) {
    return this.prisma.clinicPrompt.findMany({ where: { category, isActive: true }, orderBy: { createdAt: 'desc' } });
  }

  async getPromptById(id: string) {
    const prompt = await this.prisma.clinicPrompt.findUnique({ where: { id } });
    if (!prompt) throw new NotFoundException('Prompt not found');
    return prompt;
  }

  async updatePrompt(id: string, data: any) {
    await this.getPromptById(id);
    return this.prisma.clinicPrompt.update({ where: { id }, data });
  }

  async deletePrompt(id: string) {
    await this.getPromptById(id);
    return this.prisma.clinicPrompt.delete({ where: { id } });
  }

  async togglePromptStatus(id: string) {
    const prompt = await this.getPromptById(id);
    return this.prisma.clinicPrompt.update({ where: { id }, data: { isActive: !prompt.isActive } });
  }
}
