import { Injectable, NestMiddleware } from '@nestjs/common';
import { Request, Response, NextFunction } from 'express';

export interface RequestContext {
  ipAddress: string;
  userAgent: string;
  geoLocation: string | null;
  timestamp: Date;
}

@Injectable()
export class RequestContextMiddleware implements NestMiddleware {
  use(req: Request, res: Response, next: NextFunction) {
    const ipAddress = (req.headers['x-forwarded-for'] as string) || req.ip || '0.0.0.0';
    const userAgent = req.headers['user-agent'] || 'unknown';
    
    // Injecting RequestContext into the Request object
    (req as any).context = {
      ipAddress,
      userAgent,
      geoLocation: null, // Pode ser adicionado GeoIP depois
      timestamp: new Date(),
    } as RequestContext;

    next();
  }
}
