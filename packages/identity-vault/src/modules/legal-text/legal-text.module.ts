import { Module } from '@nestjs/common';
import { LegalTextController } from './legal-text.controller';
import { LegalTextService } from './legal-text.service';

@Module({
  controllers: [LegalTextController],
  providers: [LegalTextService],
})
export class LegalTextModule {}