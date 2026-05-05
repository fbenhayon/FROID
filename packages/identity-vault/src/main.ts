import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  
  // Habilitar CORS
  app.enableCors({
    origin: ['http://167.71.182.244', 'http://localhost:5173'],
    credentials: true,
  });
  
  await app.listen(3001);
  console.log('🚀 Identity Vault running on http://0.0.0.0:3001');
}
bootstrap();
