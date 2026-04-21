"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@prisma/client");
const prisma = new client_1.PrismaClient();
async function main() {
    const patientId = '66367355-6677-4488-9999-568393847585';
    const profId = '98854322-8765-4321-bbbb-cccdddeeefff';
    console.log('Seeding database for E2B tests...');
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
    await prisma.professional.upsert({
        where: { id: profId },
        update: {},
        create: {
            id: profId,
            fullName: 'Dr. Auditor',
            cpf: '000.000.000-00',
            email: 'auditor@froid.health',
            registrationNumber: '12345',
            registrationType: 'CRM',
        },
    });
    const legalTexts = [
        {
            id: '809b43e6-1234-45aa-99aa-8888dddd0001',
            title: 'Termo de Gravação de Áudio',
            scope: 'audio_recording'
        },
        {
            id: '809b43e6-1234-45aa-99aa-8888dddd0005',
            title: 'Termo de IA',
            scope: 'ai_report'
        }
    ];
    for (const lt of legalTexts) {
        await prisma.legalText.upsert({
            where: { legalTextId: lt.id },
            update: {
                effectiveTo: null
            },
            create: {
                legalTextId: lt.id,
                title: lt.title,
                type: 'consent',
                audience: 'patient',
                context: lt.scope === 'audio_recording' ? 'pre_session' : 'report',
                shortText: lt.title,
                expandedText: `Texto expandido para ${lt.title}`,
                version: '1.0.0',
                legalBasis: { chapter: 'I', article: '7', paragraph: 'I', tag: 'consent' },
                uiComponent: 'ConsentComponent',
                enforcementRuleId: `rule_${lt.scope}`,
            },
        });
    }
    console.log('Seed completed successfully.');
}
main()
    .catch((e) => {
    console.error(e);
    process.exit(1);
})
    .finally(async () => {
    await prisma.$disconnect();
});
//# sourceMappingURL=seed-e2b.js.map