import { Injectable } from '@nestjs/common';
import { prisma } from '../../prisma/client';

@Injectable()
export class PromptService {
  
  // Prompts default do sistema
  private defaultPrompts = [
    { id: '1', template: 'Como este paciente se compara à média populacional em Zonas FROID?', category: 'populacional' },
    { id: '2', template: 'Identificar padrões atípicos comparados à base de dados', category: 'populacional' },
    { id: '3', template: 'Este paciente está acima ou abaixo da média em riscos clínicos?', category: 'populacional' },
    { id: '4', template: 'Progresso do paciente nas últimas {weeks} semanas vs população', category: 'temporal', customizable: true },
    { id: '5', template: 'Velocidade de melhora comparada a casos similares', category: 'temporal' },
    { id: '6', template: 'Perfil vocal/facial similar a quais condições na base?', category: 'diagnostico' },
    { id: '7', template: 'Casos mais parecidos com este paciente (top 5)', category: 'diagnostico' },
    { id: '8', template: 'Intervenções mais eficazes para perfis similares', category: 'recomendacoes' },
    { id: '9', template: 'Predição de resposta terapêutica baseada em casos análogos', category: 'recomendacoes' },
    { id: '10', template: 'Alertas: padrões de risco identificados na base populacional', category: 'recomendacoes' },
  ];

  async executePrompt(data: any) {
    const { promptId, patientId, parameters } = data;
    
    // TODO: Integração com base anonimizada e IA
    // Por enquanto retorna mock
    
    return {
      promptId,
      patientId,
      executedAt: new Date(),
      result: {
        summary: 'Análise comparativa em processamento. Integração com base anonimizada será implementada na próxima fase.',
        insights: [
          'Paciente apresenta Zona C4 dominante (62% das sessões)',
          'Valor 15% acima da média populacional para esta faixa etária',
          'Padrão similar a 127 casos na base (congruência 78%)',
        ],
        recommendations: [
          'Continuar monitoramento longitudinal',
          'Considerar abordagem similar a caso #AI-4521 (melhora de 34% em 8 semanas)',
        ],
      },
    };
  }

  async findByProfessional(professionalId: string) {
    // Retornar prompts default + prompts customizados do profissional
    // TODO: Buscar prompts customizados no banco
    
    return {
      default: this.defaultPrompts,
      custom: [], // Prompts criados pelo profissional
    };
  }

  async create(data: any) {
    // TODO: Salvar prompt customizado no banco
    return {
      id: 'custom-' + Date.now(),
      ...data,
      createdAt: new Date(),
    };
  }

  async update(id: string, data: any) {
    // TODO: Atualizar prompt no banco
    return {
      id,
      ...data,
      updatedAt: new Date(),
    };
  }

  async delete(id: string) {
    // TODO: Deletar prompt do banco
    return { id, deleted: true };
  }
}
