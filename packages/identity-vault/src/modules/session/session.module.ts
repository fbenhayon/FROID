import { Module, forwardRef } from '@nestjs/common';
import { SessionService } from './session.service';
import { SessionController } from './session.controller';
import { PrismaModule } from '../../prisma/prisma.module';
import { PolicyModule } from '../policy/policy.module';
import { ConsentModule } from '../consent/consent.module';
import { LegalEventModule } from '../legal-event/legal-event.module';

@Module({
  imports: [
    PrismaModule,
    forwardRef(() => PolicyModule),
    forwardRef(() => ConsentModule),
    forwardRef(() => LegalEventModule),
  ],
  controllers: [SessionController],
  providers: [SessionService],
  exports: [SessionService],
})
export class SessionModule {}
