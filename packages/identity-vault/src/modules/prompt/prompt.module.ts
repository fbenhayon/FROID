import { Module } from '@nestjs/common';
import { PromptController } from './prompt.controller';
import { PromptService } from './prompt.service';
import { AIComparativePromptController } from './ai-comparative-prompt.controller';
import { AIComparativePromptService } from './ai-comparative-prompt.service';
import { PrismaService } from '../../prisma/prisma.service';

@Module({
  controllers: [
    PromptController,
    AIComparativePromptController,
  ],
  providers: [
    PromptService,
    AIComparativePromptService,
    PrismaService,
  ],
})
export class PromptModule {}
