/**
 * FROID v3.0 - Shared Utility
 * SHA-256 canonico e deterministico (independente de ordem das chaves)
 * 
 * Teste de aceitacao 17: computeHash({a:1, b:2}) === computeHash({b:2, a:1})
 * Teste de aceitacao 18: qualquer alteracao de campo muda o hash
 */
import { createHash } from 'crypto';

export function computeHash(payload: object): string {
  const canonical = JSON.stringify(payload, Object.keys(payload).sort());
  return createHash('sha256').update(canonical).digest('hex');
}