import { MiddlewareConsumer, Module, NestModule } from '@nestjs/common';
import { PrismaModule } from './prisma/prisma.module';
import { PatientModule } from './modules/patient/patient.module';
import { ProfessionalModule } from './modules/professional/professional.module';
import { LegalTextModule } from './modules/legal-text/legal-text.module';

import { ConsentModule } from './modules/consent/consent.module';
import { LegalEventModule } from './modules/legal-event/legal-event.module';
import { PolicyModule } from './modules/policy/policy.module';
import { EventBusModule } from './modules/event-bus/event-bus.module';
import { HashChainModule } from './modules/hash-chain/hash-chain.module';
import { SessionModule } from './modules/session/session.module';
import { RequestContextMiddleware } from './middleware/request-context.middleware';

@Module({
  imports: [
    PrismaModule, 
    PatientModule, 
    ProfessionalModule, 
    LegalTextModule, 
    ConsentModule, 
    LegalEventModule,
    PolicyModule,
    EventBusModule,
    HashChainModule,
    SessionModule,
  ],
})
export class AppModule implements NestModule {
  configure(consumer: MiddlewareConsumer) {
    consumer.apply(RequestContextMiddleware).forRoutes('consents', 'policy', 'sessions');
  }
}