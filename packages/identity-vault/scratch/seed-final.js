"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@prisma/client");
const prisma = new client_1.PrismaClient();
async function main() {
    const patientId = '66367355-6677-4488-9999-568393847585';
    console.log('Final seeding for E2B tests...');
    await prisma.patient.upsert({
        where: { id: patientId },
        update: {},
        create: {
            id: patientId,
            fullName: 'Titular de Teste E2B',
            cpf: '123.456.789-00',
            email: 'test-e2b@froid.health',
            dateOfBirth: new Date('1990-01-01'),
            gender: 'NB',
            region: 'SP',
        },
    });
    const texts = [
        { id: 'tcle_audio', title: 'Termo de Gravação de Áudio' },
        { id: 'tcle_video', title: 'Termo de Vídeo' },
        { id: 'tcle_ai_report', title: 'Termo de Relatório de IA' }
    ];
    for (const t of texts) {
        await prisma.legalText.upsert({
            where: { legalTextId: t.id },
            update: { effectiveTo: null },
            create: {
                legalTextId: t.id,
                title: t.title,
                type: 'consent',
                audience: 'patient',
                context: 'session',
                shortText: t.title,
                expandedText: t.title,
                version: '1.0.0',
                legalBasis: { chapter: 'I', article: '7', paragraph: 'I', tag: 'consent' },
                uiComponent: 'ConsentComp',
                enforcementRuleId: 'rule'
            },
        });
    }
    console.log('Seeding successful.');
}
main()
    .catch(e => { console.error(e); process.exit(1); })
    .finally(() => prisma.$disconnect());
//# sourceMappingURL=seed-final.js.map