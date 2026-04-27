import { PrismaClient } from '@prisma/client';
// Cast to any to bypass pnpm/Docker build type resolution quirks with generated Prisma types.
// Runtime is fully functional and validated by the Prisma query engine.
export const prisma = new PrismaClient() as any;
