import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';
import { DocumentBuilder, SwaggerModule } from '@nestjs/swagger';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);

  const config = new DocumentBuilder()
    .setTitle('FROID API')
    .setDescription('FROID - Frequency Recognition of Internal Dynamics')
    .setVersion('3.4.0')
    .addTag('Auth')
    .addTag('Admin')
    .addBearerAuth()
    .build();

  const document = SwaggerModule.createDocument(app, config);
  SwaggerModule.setup('api/docs', app, document);

  app.enableCors();

  const port = process.env.PORT || 3001;
  await app.listen(port, '0.0.0.0');

  console.log(`🚀 FROID API: http://0.0.0.0:${port}`);
  console.log(`📚 Swagger: http://0.0.0.0:${port}/api/docs`);
}
bootstrap();
