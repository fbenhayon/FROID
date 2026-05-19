import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { patientsAPI } from '../api/client';
import { ConsentModal } from '../components/ConsentModal';

export function NewPatient() {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    name: '',
    cpf: '',
    birthDate: '',
    phone: '',
    email: '',
  });
  const [showConsent, setShowConsent] = useState(false);
  const user = JSON.parse(localStorage.getItem('user') || '{}');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setShowConsent(true);
  };

  const handleConsentAccept = async (scopes: any) => {
    try {
      console.log('Consentimento aceito:', scopes);
      const patientData = { ...formData, professionalId: user.id };
      await patientsAPI.create(patientData);
      alert('Paciente cadastrado!');
      navigate('/dashboard');
    } catch (error: any) {
      alert('Erro: ' + (error.response?.data?.message || 'Desconhecido'));
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <h1 className="text-2xl font-bold">Cadastrar Novo Paciente</h1>
        </div>
      </div>
      <div className="max-w-2xl mx-auto px-4 py-8">
        <div className="bg-white rounded-lg shadow p-6">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label className="block text-sm font-medium mb-2">Nome Completo *</label>
              <input type="text" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} className="w-full px-4 py-3 border rounded-lg" required />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">CPF *</label>
              <input type="text" value={formData.cpf} onChange={(e) => setFormData({ ...formData, cpf: e.target.value })} className="w-full px-4 py-3 border rounded-lg" required />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Data de Nascimento *</label>
              <input type="date" value={formData.birthDate} onChange={(e) => setFormData({ ...formData, birthDate: e.target.value })} className="w-full px-4 py-3 border rounded-lg" required />
            </div>
            <div className="flex gap-3 pt-4">
              <button type="button" onClick={() => navigate('/dashboard')} className="px-6 py-3 bg-gray-100 rounded-lg">Cancelar</button>
              <button type="submit" className="flex-1 px-6 py-3 bg-blue-600 text-white rounded-lg">Continuar</button>
            </div>
          </form>
        </div>
      </div>
      <ConsentModal isOpen={showConsent} onClose={() => setShowConsent(false)} onAccept={handleConsentAccept} patientName={formData.name} />
    </div>
  );
}
