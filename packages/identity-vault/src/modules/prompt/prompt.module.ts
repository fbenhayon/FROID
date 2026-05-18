import { Module } from '@nestjs/common';
import { PromptController } from './prompt.controller';
import { PromptService } from './prompt.service';
import { PrismaService } from '../../prisma/prisma.service';

@Module({
  controllers: [PromptController],
  providers: [PromptService, PrismaService],
})
export class PromptModule {}
