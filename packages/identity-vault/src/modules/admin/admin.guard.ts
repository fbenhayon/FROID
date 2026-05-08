import { Injectable, CanActivate, ExecutionContext, ForbiddenException } from '@nestjs/common';

@Injectable()
export class SuperAdminGuard implements CanActivate {
  canActivate(context: ExecutionContext): boolean {
    const request = context.switchToHttp().getRequest();
    const user = request.user;
    
    // Apenas fbenhayon@froid.com.br com role super_admin
    if (user?.email !== 'fbenhayon@froid.com.br' || user?.role !== 'super_admin') {
      throw new ForbiddenException('Acesso exclusivo do Super Admin (Fabio Benhayon)');
    }
    
    return true;
  }
}
