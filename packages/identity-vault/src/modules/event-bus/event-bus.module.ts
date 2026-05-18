import { PrismaModule } from '../../prisma/prisma.module';
import { Module } from '@nestjs/common';
import { EventBusService } from './event-bus.service';
import { HashChainModule } from '../hash-chain/hash-chain.module';
import { PolicyModule } from '../policy/policy.module';

@Module({
  imports: [PrismaModule],
  imports: [
    HashChainModule,
    PolicyModule,
  ],
  providers: [EventBusService],
  exports: [EventBusService],
})
export class EventBusModule {}
