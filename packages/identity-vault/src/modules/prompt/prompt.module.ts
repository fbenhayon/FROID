import { PrismaModule } from '../../prisma/prisma.module';
import { Module } from '@nestjs/common';
import { PromptController } from './prompt.controller';
import { PromptService } from './prompt.service';
import { PrismaService } from '../../prisma/prisma.service';

@Module({
  imports: [PrismaModule],
  controllers: [PromptController],
  providers: [PromptService, PrismaService],
})
export class PromptModule {}
