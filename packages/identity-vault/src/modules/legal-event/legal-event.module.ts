import { Module, forwardRef } from '@nestjs/common';
import { LegalEventService } from './legal-event.service';
import { PrismaModule } from '../../prisma/prisma.module';
import { EventBusModule } from '../event-bus/event-bus.module';

@Module({
  imports: [
    PrismaModule,
    forwardRef(() => EventBusModule),
  ],
  providers: [LegalEventService],
  exports: [LegalEventService],
})
export class LegalEventModule {}
