import { Controller, Post, Get, Body, UseGuards, Request, Res } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiResponse, ApiBody } from '@nestjs/swagger';
import { AuthService } from './auth.service';
import { GoogleAuthGuard } from './guards/google-auth.guard';
import { GitHubAuthGuard } from './guards/github-auth.guard';
import { Response } from 'express';

@ApiTags('Auth')
@Controller('auth')
export class AuthController {
  constructor(private authService: AuthService) {}

  @Post('register')
  @ApiOperation({ summary: 'Registrar profissional (cria user + professional juntos)' })
  @ApiResponse({ status: 201, description: 'Usuário e profissional criados com sucesso' })
  @ApiBody({
    schema: {
      required: ['email', 'password', 'name', 'crp', 'specialty'],
      properties: {
        email: { type: 'string', example: 'psicologo@froid.com.br' },
        password: { type: 'string', example: 'Senha123@' },
        name: { type: 'string', example: 'Dr. João Silva' },
        crp: { type: 'string', example: 'CRP-06/12345' },
        specialty: { type: 'string', example: 'Psicologia Clínica' },
        phone: { type: 'string', example: '11999998888' },
      },
    },
  })
  async register(@Body() body: any) {
    return this.authService.register(body);
  }

  @Post('login')
  @ApiOperation({ summary: 'Login com email e senha' })
  @ApiResponse({ status: 200, description: 'Login bem-sucedido, retorna JWT token' })
  @ApiBody({
    schema: {
      properties: {
        email: { type: 'string', example: 'admin@froid.com' },
        password: { type: 'string', example: 'froid123' },
      },
    },
  })
  async login(@Body() body: { email: string; password: string }) {
    return this.authService.login(body);
  }

  @Get('google')
  @UseGuards(GoogleAuthGuard)
  @ApiOperation({ summary: 'Iniciar OAuth com Google' })
  @ApiResponse({ status: 302, description: 'Redireciona para login Google' })
  async googleAuth() {
    // Guard redireciona automaticamente
  }

  @Get('google/callback')
  @UseGuards(GoogleAuthGuard)
  @ApiOperation({ summary: 'Callback OAuth Google' })
  @ApiResponse({ status: 302, description: 'Retorna com JWT token' })
  async googleAuthCallback(@Request() req, @Res() res: Response) {
    const result = await this.authService.oauthLogin(req.user, 'google');
    const frontendUrl = process.env.FRONTEND_URL || 'http://localhost:3000';
    res.redirect(`${frontendUrl}/auth/callback?token=${result.access_token}`);
  }

  @Get('github')
  @UseGuards(GitHubAuthGuard)
  @ApiOperation({ summary: 'Iniciar OAuth com GitHub' })
  @ApiResponse({ status: 302, description: 'Redireciona para login GitHub' })
  async githubAuth() {
    // Guard redireciona automaticamente
  }

  @Get('github/callback')
  @UseGuards(GitHubAuthGuard)
  @ApiOperation({ summary: 'Callback OAuth GitHub' })
  @ApiResponse({ status: 302, description: 'Retorna com JWT token' })
  async githubAuthCallback(@Request() req, @Res() res: Response) {
    const result = await this.authService.oauthLogin(req.user, 'github');
    const frontendUrl = process.env.FRONTEND_URL || 'http://localhost:3000';
    res.redirect(`${frontendUrl}/auth/callback?token=${result.access_token}`);
  }
}
