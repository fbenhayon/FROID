import { Module } from '@nestjs/common';
import { ConsentService } from './consent.service';
import { ConsentController } from './consent.controller';
import { PrismaModule } from '../../prisma/prisma.module';
import { LegalEventModule } from '../legal-event/legal-event.module';

@Module({
  imports: [PrismaModule, LegalEventModule],
  controllers: [ConsentController],
  providers: [ConsentService],
  exports: [ConsentService],
})
export class ConsentModule {}
