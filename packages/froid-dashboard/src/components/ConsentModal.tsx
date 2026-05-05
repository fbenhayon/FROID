import { useState } from 'react';

interface ConsentModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAccept: (scopes: ConsentScopes) => void;
  patientName: string;
}

interface ConsentScopes {
  voiceRecording: boolean;
  facialRecording: boolean;
  biometricAnalysis: boolean;
  clinicalScoring: boolean;
  dataStorage: boolean;
  researchUse: boolean;
  thirdPartySharing: boolean;
}

export function ConsentModal({ isOpen, onClose, onAccept, patientName }: ConsentModalProps) {
  const [scopes, setScopes] = useState<ConsentScopes>({
    voiceRecording: true,
    facialRecording: true,
    biometricAnalysis: true,
    clinicalScoring: true,
    dataStorage: true,
    researchUse: true,
    thirdPartySharing: true,
  });
  const [finalConsent, setFinalConsent] = useState(false);

  const updateScope = (key: keyof ConsentScopes, value: boolean) => {
    setScopes({ ...scopes, [key]: value });
  };

  const handleAccept = () => {
    if (!finalConsent) {
      alert('É necessário aceitar o termo final');
      return;
    }
    
    // Validar se pelo menos os essenciais estão marcados
    const essentials = scopes.voiceRecording && scopes.facialRecording && scopes.biometricAnalysis;
    if (!essentials) {
      alert('Gravação de voz, face e processamento biométrico são obrigatórios para uso da plataforma');
      return;
    }
    
    onAccept(scopes);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto p-6">
        <h2 className="text-2xl font-bold mb-4">Termo de Consentimento FROID</h2>
        <p className="text-gray-600 mb-4">Paciente: {patientName}</p>

        {/* Disclaimers LGPD */}
        <div className="bg-gray-50 border border-gray-300 rounded-lg p-4 mb-4 text-xs">
          <p className="font-semibold mb-2">📋 INFORMAÇÕES LGPD (Lei 13.709/2018)</p>
          
          <p className="mb-2"><strong>Controlador:</strong> FROID Inc. | <strong>DPO:</strong> dpo@froid.com</p>
          
          <p className="mb-2"><strong>Finalidade:</strong> Análise clínica multimodal (voz + face) para apoio diagnóstico em psicoterapia.</p>
          
          <p className="mb-2"><strong>Seus Direitos (Art. 18):</strong></p>
          <ul className="list-disc ml-5 mb-2 text-[10px] space-y-0.5">
            <li>Acesso aos dados</li>
            <li>Correção de incorreções</li>
            <li>Anonimização, bloqueio ou eliminação</li>
            <li>Portabilidade</li>
            <li>Informações sobre compartilhamento</li>
            <li>Revogação do consentimento</li>
          </ul>
          
          <p className="mb-1"><strong>Revogação:</strong> A qualquer momento através do profissional responsável.</p>
          
          <p className="mb-1"><strong>Negativa:</strong> Impede uso do FROID, mas não afeta atendimento convencional.</p>
          
          <p><strong>Segurança:</strong> Criptografia AES-256, acesso restrito, logs de auditoria.</p>
        </div>

        {/* Aceites Granulares */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
          <h3 className="font-semibold mb-3">Escolha seus Consentimentos</h3>
          <div className="bg-white rounded p-4 space-y-2 text-sm">
            
            {/* ESSENCIAIS (obrigatórios) */}
            <p className="font-semibold text-red-600 mb-2">Essenciais (Obrigatórios):</p>
            
            <label className="flex items-start cursor-pointer hover:bg-gray-50 p-1 rounded">
              <input
                type="checkbox"
                checked={scopes.voiceRecording}
                onChange={(e) => updateScope('voiceRecording', e.target.checked)}
                className="w-4 h-4 mt-0.5 mr-2 text-blue-600"
              />
              <span>Gravação e análise de voz (12 Zonas FROID)</span>
            </label>
            
            <label className="flex items-start cursor-pointer hover:bg-gray-50 p-1 rounded">
              <input
                type="checkbox"
                checked={scopes.facialRecording}
                onChange={(e) => updateScope('facialRecording', e.target.checked)}
                className="w-4 h-4 mt-0.5 mr-2 text-blue-600"
              />
              <span>Gravação e análise facial (FACS)</span>
            </label>
            
            <label className="flex items-start cursor-pointer hover:bg-gray-50 p-1 rounded">
              <input
                type="checkbox"
                checked={scopes.biometricAnalysis}
                onChange={(e) => updateScope('biometricAnalysis', e.target.checked)}
                className="w-4 h-4 mt-0.5 mr-2 text-blue-600"
              />
              <span>Processamento biométrico</span>
            </label>

            {/* OPCIONAIS CLÍNICOS */}
            <p className="font-semibold text-blue-600 mt-3 mb-2">Opcionais Clínicos:</p>
            
            <label className="flex items-start cursor-pointer hover:bg-gray-50 p-1 rounded">
              <input
                type="checkbox"
                checked={scopes.clinicalScoring}
                onChange={(e) => updateScope('clinicalScoring', e.target.checked)}
                className="w-4 h-4 mt-0.5 mr-2 text-blue-600"
              />
              <span>Scoring clínico para apoio diagnóstico</span>
            </label>
            
            <label className="flex items-start cursor-pointer hover:bg-gray-50 p-1 rounded">
              <input
                type="checkbox"
                checked={scopes.dataStorage}
                onChange={(e) => updateScope('dataStorage', e.target.checked)}
                className="w-4 h-4 mt-0.5 mr-2 text-blue-600"
              />
              <span>Armazenamento seguro com criptografia</span>
            </label>

            {/* OPCIONAIS SENSÍVEIS */}
            <p className="font-semibold text-yellow-600 mt-3 mb-2">Opcionais Sensíveis:</p>
            
            <label className="flex items-start cursor-pointer hover:bg-gray-50 p-1 rounded">
              <input
                type="checkbox"
                checked={scopes.researchUse}
                onChange={(e) => updateScope('researchUse', e.target.checked)}
                className="w-4 h-4 mt-0.5 mr-2 text-blue-600"
              />
              <span>Uso em pesquisa científica (dados agregados k≥50, zero PII)</span>
            </label>

            <label className="flex items-start cursor-pointer hover:bg-gray-50 p-1 rounded">
              <input
                type="checkbox"
                checked={scopes.thirdPartySharing}
                onChange={(e) => updateScope('thirdPartySharing', e.target.checked)}
                className="w-4 h-4 mt-0.5 mr-2 text-blue-600"
              />
              <span>Compartilhamento com parceiros autorizados</span>
            </label>
          </div>
        </div>

        {/* Aceite Final */}
        <div className="bg-yellow-100 border-2 border-yellow-400 rounded-lg p-3 mb-4">
          <label className="flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={finalConsent}
              onChange={(e) => setFinalConsent(e.target.checked)}
              className="w-5 h-5 text-blue-600 rounded mr-3"
            />
            <span className="font-bold">Li e ACEITO os termos selecionados acima para uso da plataforma FROID</span>
          </label>
        </div>

        {/* Botões */}
        <div className="flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg"
          >
            Cancelar
          </button>
          <button
            onClick={handleAccept}
            disabled={!finalConsent}
            className="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg disabled:opacity-50"
          >
            Aceitar e Continuar
          </button>
        </div>
      </div>
    </div>
  );
}
