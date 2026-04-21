import { Module } from '@nestjs/common';
import { HashChainService } from './hash-chain.service';
import { AuditController } from './audit.controller';
import { PrismaModule } from '../../prisma/prisma.module';
import { PolicyModule } from '../policy/policy.module';

@Module({
  imports: [
    PrismaModule,
    PolicyModule,
  ],
  providers: [HashChainService],
  controllers: [AuditController],
  exports: [HashChainService],
})
export class HashChainModule {}
