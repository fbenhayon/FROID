# Contratos jurídicos versionados — fornecedor pessoa física

## Escopo

O backend é a fonte autoritativa dos textos, versões e hashes apresentados em:

- Política de Privacidade;
- Termos Gerais de Uso;
- contrato de licença do profissional;
- contrato de clínica ou organização;
- TCLE do paciente;
- resumo comercial de cada checkout.

Os textos não fixam preços, quantidade de sessões ou SLA. O resumo comercial é
calculado no servidor a partir do catálogo vigente e gravado junto ao aceite.

## Privacidade do fornecedor

Nome, CPF, endereço e contatos não pertencem ao Git. Configure-os apenas no
`.env` protegido do servidor:

```dotenv
FROID_LEGAL_SUPPLIER_NAME=
FROID_LEGAL_SUPPLIER_TAX_ID=
FROID_LEGAL_SUPPLIER_ADDRESS=
FROID_LEGAL_CONTACT_EMAIL=
FROID_LEGAL_PRIVACY_EMAIL=
FROID_LEGAL_AUDIT_HMAC_KEY=
FROID_LEGAL_ACCEPTANCE_REQUIRED=false
```

`FROID_LEGAL_AUDIT_HMAC_KEY` deve ser um segredo aleatório independente, com no
mínimo 32 bytes. Ele pseudonimiza a identidade e o fingerprint da requisição na
trilha PostgreSQL. Não reutilize chaves de Stripe, banco ou criptografia clínica.

## Implantação gradual

1. Fazer backup integral e validar restauração.
2. Implantar com `FROID_LEGAL_ACCEPTANCE_REQUIRED=false`.
3. Aplicar a migração `009_legal_acceptance_ledger`.
4. Configurar todos os campos privados e reiniciar somente o backend.
5. Conferir `/api/legal/documents`; `supplier.configured` deve ser `true`.
6. Validar as cinco páginas jurídicas, convite de paciente e checkout em teste.
7. Ativar `FROID_LEGAL_ACCEPTANCE_REQUIRED=true`.
8. Conferir `/ready`; os checks jurídicos devem ser verdadeiros.
9. Repetir um cadastro profissional e um cadastro de clínica em teste.
10. Confirmar eventos append-only em `legal_acceptance_events`.

Perfis existentes continuam acessíveis durante a etapa desligada. Após a
ativação, uma nova compra exige a versão jurídica atual. Novos convites exigem o
TCLE versionado; pacientes já cadastrados podem atualizá-lo no Portal do
Paciente.

## Evidência

A tabela `legal_acceptance_events` não armazena nome, CPF, e-mail ou IP em texto.
Ela guarda documento, versão, SHA-256, contexto, resumo comercial, instante e
referências HMAC. Trigger de banco impede UPDATE e DELETE.

Os documentos são minutas operacionais e devem continuar submetidos a revisão
jurídica especializada antes da ativação comercial definitiva.
