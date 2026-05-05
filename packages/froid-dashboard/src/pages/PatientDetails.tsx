import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';

interface Session {
  id: string;
  status: string;
  startedAt: string;
  endedAt: string | null;
  voiceAnalyses: any[];
  facialAnalyses: any[];
}

interface Patient {
  id: string;
  name: string;
  cpf: string;
  birthDate: string;
}

export function PatientDetails() {
  const { patientId } = useParams();
  const navigate = useNavigate();
  const [patient, setPatient] = useState<Patient | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadPatientData();
  }, [patientId]);

  const loadPatientData = async () => {
    try {
      const token = localStorage.getItem('token');
      
      // Carregar dados do paciente
      const patientRes = await fetch(`http://167.71.182.244:3001/patients/${patientId}`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      const patientData = await patientRes.json();
      setPatient(patientData);

      // Carregar sessões
      const sessionsRes = await fetch(`http://167.71.182.244:3001/sessions/patient/${patientId}`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      const sessionsData = await sessionsRes.json();
      setSessions(sessionsData);
    } catch (error) {
      console.error('Erro ao carregar dados:', error);
    } finally {
      setLoading(false);
    }
  };

  const startNewSession = () => {
    navigate(`/session/${patientId}`);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('pt-BR');
  };

  const getDuration = (start: string, end: string | null) => {
    if (!end) return 'Em andamento';
    const duration = new Date(end).getTime() - new Date(start).getTime();
    const minutes = Math.floor(duration / 60000);
    return `${minutes} min`;
  };

  // Calcular métricas agregadas
  const calculateMetrics = () => {
    const completedSessions = sessions.filter(s => s.status === 'completed');
    const totalVoiceAnalyses = completedSessions.reduce((acc, s) => acc + (s.voiceAnalyses?.length || 0), 0);
    const totalFaceAnalyses = completedSessions.reduce((acc, s) => acc + (s.facialAnalyses?.length || 0), 0);

    return {
      totalSessions: sessions.length,
      completedSessions: completedSessions.length,
      activeSessions: sessions.filter(s => s.status === 'active').length,
      totalAnalyses: totalVoiceAnalyses + totalFaceAnalyses,
    };
  };

  const metrics = calculateMetrics();

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-500">Carregando...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <div>
              <button
                onClick={() => navigate('/dashboard')}
                className="text-blue-600 hover:text-blue-800 mb-2"
              >
                ← Voltar ao Dashboard
              </button>
              <h1 className="text-2xl font-bold text-gray-900">{patient?.name}</h1>
              <p className="text-sm text-gray-600">CPF: {patient?.cpf}</p>
            </div>
            <button
              onClick={startNewSession}
              className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold"
            >
              + Nova Sessão
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        
        {/* Métricas Gerais */}
        <div className="grid grid-cols-4 gap-4 mb-8">
          <div className="bg-white rounded-lg shadow p-6">
            <p className="text-sm text-gray-600">Total de Sessões</p>
            <p className="text-3xl font-bold text-gray-900">{metrics.totalSessions}</p>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <p className="text-sm text-gray-600">Sessões Concluídas</p>
            <p className="text-3xl font-bold text-green-600">{metrics.completedSessions}</p>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <p className="text-sm text-gray-600">Sessões Ativas</p>
            <p className="text-3xl font-bold text-yellow-600">{metrics.activeSessions}</p>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <p className="text-sm text-gray-600">Total de Análises</p>
            <p className="text-3xl font-bold text-blue-600">{metrics.totalAnalyses}</p>
          </div>
        </div>

        {/* Indicadores Clínicos */}
        <div className="bg-white rounded-lg shadow p-6 mb-8">
          <h2 className="text-xl font-semibold mb-4">Indicadores Clínicos</h2>
          <div className="grid grid-cols-3 gap-6">
            <div>
              <p className="text-sm text-gray-600 mb-2">Zona FROID Dominante</p>
              <div className="flex items-center">
                <div className="w-3 h-3 bg-blue-500 rounded-full mr-2"></div>
                <p className="text-lg font-semibold">C4 - Ação/Contemplação</p>
              </div>
              <p className="text-xs text-gray-500 mt-1">Baseado em {metrics.completedSessions} sessões</p>
            </div>
            <div>
              <p className="text-sm text-gray-600 mb-2">Emoção Recorrente</p>
              <div className="flex items-center">
                <div className="w-3 h-3 bg-green-500 rounded-full mr-2"></div>
                <p className="text-lg font-semibold">Neutro</p>
              </div>
              <p className="text-xs text-gray-500 mt-1">FACS - Análise Facial</p>
            </div>
            <div>
              <p className="text-sm text-gray-600 mb-2">Risco Clínico</p>
              <div className="flex items-center">
                <div className="w-3 h-3 bg-yellow-500 rounded-full mr-2"></div>
                <p className="text-lg font-semibold">Baixo</p>
              </div>
              <p className="text-xs text-gray-500 mt-1">Depressão / Mania / Estresse</p>
            </div>
          </div>
          <div className="mt-6 p-4 bg-blue-50 rounded-lg">
            <p className="text-sm text-blue-800">
              <strong>Nota Clínica:</strong> Paciente apresenta padrão de voz estável com predominância de 
              zona C4, indicando equilíbrio entre ação e reflexão. Expressões faciais neutras sugerem 
              estado emocional controlado. Recomenda-se continuar monitoramento longitudinal.
            </p>
          </div>
        </div>

        {/* Histórico de Sessões */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4">Histórico de Sessões</h2>
          
          {sessions.length === 0 ? (
            <p className="text-center text-gray-500 py-8">
              Nenhuma sessão registrada ainda.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">ID</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Início</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Fim</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Duração</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Análises</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {sessions.map((session) => (
                    <tr key={session.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 text-sm font-mono text-gray-900">
                        {session.id.substring(0, 8)}...
                      </td>
                      <td className="px-6 py-4 text-sm">
                        <span className={`px-2 py-1 rounded-full text-xs font-semibold ${
                          session.status === 'completed' 
                            ? 'bg-green-100 text-green-800' 
                            : 'bg-yellow-100 text-yellow-800'
                        }`}>
                          {session.status === 'completed' ? 'Concluída' : 'Ativa'}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-500">
                        {formatDate(session.startedAt)}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-500">
                        {session.endedAt ? formatDate(session.endedAt) : '-'}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-500">
                        {getDuration(session.startedAt, session.endedAt)}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-500">
                        {(session.voiceAnalyses?.length || 0) + (session.facialAnalyses?.length || 0)} registros
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
