import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { patientsAPI } from '../api/client';

interface Patient {
  id: string;
  name: string;
  cpf: string;
  birthDate: string;
  sessions?: Array<{
    id: string;
    status: string;
    startedAt: string;
    endedAt: string | null;
  }>;
}

export function Dashboard() {
  const navigate = useNavigate();
  const [patients, setPatients] = useState<Patient[]>([]);
  const [loading, setLoading] = useState(true);

  const userStr = localStorage.getItem('user');
  const user = userStr ? JSON.parse(userStr) : { id: '', name: 'Usuário' };

  useEffect(() => {
    if (user.id) {
      loadPatientsWithSessions();
    } else {
      setLoading(false);
    }
  }, []);

  const loadPatientsWithSessions = async () => {
    try {
      const token = localStorage.getItem('token');

      // Carregar pacientes
      const response = await patientsAPI.list(user.professionalId || user.id);
      const patientsData = response.data;

      // Carregar últimas 3 sessões de cada paciente
      const patientsWithSessions = await Promise.all(
        patientsData.map(async (patient: Patient) => {
          try {
            const sessionsRes = await fetch(
              `http://204.168.229.32:8001/sessions/patient/${patient.id}`,
              { headers: { Authorization: `Bearer ${token}` } }
            );
            
            if (!sessionsRes.ok) {
              console.warn(`Falha ao buscar sessões: ${sessionsRes.status}`);
              return { ...patient, sessions: [] };
            }
            
            const sessions = await sessionsRes.json();
            console.log(`${patient.name}: ${sessions.length} sessões`, sessions);
            
            return {
              ...patient,
              sessions: Array.isArray(sessions) ? sessions.slice(0, 3) : [],
            };
          } catch (error) {
            console.error(`Erro sessões ${patient.name}:`, error);
            return { ...patient, sessions: [] };
          }
        })
      );

      setPatients(patientsWithSessions);
    } catch (error) {
      console.error('Erro ao carregar pacientes:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.clear();
    window.location.href = '/';
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('pt-BR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">FROID Dashboard</h1>
              <p className="text-sm text-gray-600">Bem-vindo, {user.name}</p>
            </div>
            <button
              onClick={handleLogout}
              className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg"
            >
              Sair
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-xl font-semibold">Meus Pacientes</h2>
            <button
              onClick={() => navigate('/patients/new')}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg"
            >
              + Novo Paciente
            </button>
          </div>

          {loading ? (
            <p className="text-center text-gray-500 py-8">Carregando...</p>
          ) : patients.length === 0 ? (
            <p className="text-center text-gray-500 py-8">
              Nenhum paciente cadastrado.
            </p>
          ) : (
            <div className="space-y-6">
              {patients.map((patient) => (
                <div key={patient.id} className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow">
                  <div className="flex justify-between items-start mb-4">
                    <div>
                      <h3 className="text-lg font-semibold text-gray-900">{patient.name}</h3>
                      <p className="text-sm text-gray-500">CPF: {patient.cpf}</p>
                    </div>
                    <button
                      onClick={() => navigate(`/patients/${patient.id}`)}
                      className="px-4 py-2 text-blue-600 hover:bg-blue-50 rounded-lg font-medium"
                    >
                      Ver Detalhes
                    </button>
                  </div>

                  <div className="bg-gray-50 rounded-lg p-3">
                    <h4 className="text-sm font-semibold text-gray-700 mb-3">
                      📊 Últimas 3 Sessões
                    </h4>

                    {!patient.sessions || patient.sessions.length === 0 ? (
                      <p className="text-xs text-gray-500 text-center py-2">
                        Nenhuma sessão realizada ainda
                      </p>
                    ) : (
                      <div className="space-y-2">
                        {patient.sessions.map((session) => (
                          <div
                            key={session.id}
                            className="bg-white rounded p-2 flex justify-between items-center text-xs"
                          >
                            <div className="flex items-center space-x-3">
                              <span className={`px-2 py-1 rounded font-semibold ${
                                session.status === 'completed'
                                  ? 'bg-green-100 text-green-800'
                                  : 'bg-yellow-100 text-yellow-800'
                              }`}>
                                {session.status === 'completed' ? '✓ Concluída' : '⏳ Ativa'}
                              </span>
                              <span className="text-gray-600">
                                {formatDate(session.startedAt)}
                              </span>
                            </div>
                            <div className="text-gray-500">
                              ID: {session.id.substring(0, 8)}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
