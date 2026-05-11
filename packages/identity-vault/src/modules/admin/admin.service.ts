import { Injectable, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';

@Injectable()
export class AdminService {
  constructor(private prisma: PrismaService) {}

  async createPrompt(data: { title: string; category: string; promptText: string; createdBy?: string }) {
    return this.prisma.clinic_prompts.create({ data });
  }

  async getAllPrompts() {
    return this.prisma.clinic_prompts.findMany({ orderBy: { createdAt: 'desc' } });
  }

  async getPromptsByCategory(category: string) {
    return this.prisma.clinic_prompts.findMany({ where: { category, isActive: true }, orderBy: { createdAt: 'desc' } });
  }

  async getPromptById(id: string) {
    const prompt = await this.prisma.clinic_prompts.findUnique({ where: { id } });
    if (!prompt) throw new NotFoundException('Prompt not found');
    return prompt;
  }

  async updatePrompt(id: string, data: any) {
    await this.getPromptById(id);
    return this.prisma.clinic_prompts.update({ where: { id }, data });
  }

  async deletePrompt(id: string) {
    await this.getPromptById(id);
    return this.prisma.clinic_prompts.delete({ where: { id } });
  }

  async togglePromptStatus(id: string) {
    const prompt = await this.getPromptById(id);
    return this.prisma.clinic_prompts.update({ where: { id }, data: { isActive: !prompt.isActive } });
  }
}
