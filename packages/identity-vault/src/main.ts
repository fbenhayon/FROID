import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';
import { DocumentBuilder, SwaggerModule } from '@nestjs/swagger';
import { ValidationPipe } from '@nestjs/common';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);

  // ============================================================================
  // SWAGGER DOCUMENTATION
  // ============================================================================
  const config = new DocumentBuilder()
    .setTitle('FROID API')
    .setDescription('FROID - Frequency Recognition of Internal Dynamics\n\nAPI multimodal para análise clínica de voz e face')
    .setVersion('3.4.0')
    .addTag('Auth', 'Autenticação e OAuth (Google/GitHub)')
    .addTag('Admin', 'Administração de prompts clínicos')
    .addBearerAuth(
      {
        type: 'http',
        scheme: 'bearer',
        bearerFormat: 'JWT',
        name: 'JWT',
        description: 'JWT token obtido via /auth/login',
        in: 'header',
      },
      'JWT-auth',
    )
    .build();

  const document = SwaggerModule.createDocument(app, config);
  SwaggerModule.setup('api/docs', app, document, {
    customSiteTitle: 'FROID API Documentation',
    customCss: '.swagger-ui .topbar { display: none }',
  });

  // ============================================================================
  // CORS CONFIGURATION
  // ============================================================================
  app.enableCors({
    origin: [
      'http://localhost:3000',
      'http://localhost:3001',
      'http://204.168.229.32',
      'http://204.168.229.32:80',
      'https://froid.com.br',
      'https://www.froid.com.br',
      'http://froid.com.br',
      'http://www.froid.com.br',
    ],
    methods: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
    allowedHeaders: ['Content-Type', 'Authorization', 'Accept'],
    credentials: true,
    maxAge: 3600,
  });

  // ============================================================================
  // GLOBAL VALIDATION PIPE
  // ============================================================================
  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      forbidNonWhitelisted: true,
      transform: true,
    }),
  );

  // ============================================================================
  // SECURITY HEADERS
  // ============================================================================
  app.use((req, res, next) => {
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.setHeader('X-Frame-Options', 'DENY');
    res.setHeader('X-XSS-Protection', '1; mode=block');
    next();
  });

  const port = process.env.PORT || 3001;
  await app.listen(port, '0.0.0.0');

  console.log(`🚀 FROID API: http://0.0.0.0:${port}`);
  console.log(`📚 Swagger: http://0.0.0.0:${port}/api/docs`);
  console.log(`🔒 CORS enabled for frontend origins`);
}

bootstrap();
