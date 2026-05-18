import { PrismaModule } from '../../prisma/prisma.module';
import { Module } from '@nestjs/common';
import { LegalTextController } from './legal-text.controller';
import { LegalTextService } from './legal-text.service';

@Module({
  imports: [PrismaModule],
  controllers: [LegalTextController],
  providers: [LegalTextService],
})
export class LegalTextModule {}