import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Bar } from 'react-chartjs-2';
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, PointElement, Title, Tooltip, Legend } from 'chart.js';

ChartJS.register(CategoryScale, LinearScale, BarElement, PointElement, Title, Tooltip, Legend);

interface Session { id: string; patientId: string; professionalId: string; status: string; createdAt: string; }
interface Note { text: string; timestamp: string; }
interface RiskScores { 
  depression: number; 
  mania: number; 
  stress: number; 
  anxiety: number;
  psychosis: number;
  trauma: number;
  suicide: number;
  bipolar: number;
  schizophrenia: number;
}

export default function LiveSession() {
  const { patientId } = useParams<{ patientId: string }>();
  const navigate = useNavigate();
  const videoRef = useRef<HTMLVideoElement>(null);
  const voiceWsRef = useRef<WebSocket | null>(null);
  const faceWsRef = useRef<WebSocket | null>(null);
  const cleanupFnRef = useRef<(() => void) | null>(null);

  const [session, setSession] = useState<Session | null>(null);
  const [voiceStatus, setVoiceStatus] = useState<'connecting' | 'connected' | 'disconnected' | 'error'>('connecting');
  const [faceStatus, setFaceStatus] = useState<'connecting' | 'connected' | 'disconnected' | 'error'>('connecting');
  const [currentZone, setCurrentZone] = useState('Aguardando...');
  const [zoneData, setZoneData] = useState<number[]>(Array(12).fill(0));
  const [bandData, setBandData] = useState<number[]>(Array(7).fill(0));
  const [colorimetryLevel, setColorimetryLevel] = useState(0);
  const [riskScores, setRiskScores] = useState<RiskScores>({ depression: 0, mania: 0, stress: 0, anxiety: 0, psychosis: 0, trauma: 0, suicide: 0, bipolar: 0, schizophrenia: 0 });
  const [currentEmotion, setCurrentEmotion] = useState('Aguardando...');
  const [ipmScore, setIpmScore] = useState(0);
  const [notes, setNotes] = useState<Note[]>([]);
  const [currentNote, setCurrentNote] = useState('');
  const [prompts, setPrompts] = useState<any[]>([]);
  const [selectedPrompt, setSelectedPrompt] = useState('');
  const [promptResult, setPromptResult] = useState('');
  const [showPromptModal, setShowPromptModal] = useState(false);
  const [loadingPrompt, setLoadingPrompt] = useState(false);

  useEffect(() => { 
    console.log('🎬 LiveSession montado - iniciando sessão');
    initializeSession(); 
    loadPrompts(); 
    return () => cleanup(); 
  }, []);

  const initializeSession = async () => {
    console.log('📋 initializeSession iniciado');
    try {
      const user = JSON.parse(localStorage.getItem('user') || '{}');
      console.log('👤 User:', user);
      const res = await fetch('https://froid.com.br/api/sessions', { 
        method: 'POST', 
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${localStorage.getItem('token')}` }, 
        body: JSON.stringify({ patientId, professionalId: user.professionalId, scheduledFor: new Date().toISOString() }) 
      });
      const data = await res.json();
      console.log('✅ Session criada:', data.id);
      setSession(data);
      connectVoiceWebSocket(data.id);
      connectFaceWebSocket(data.id);
      startCamera();
    } catch (e) { 
      console.error('❌ Erro ao inicializar sessão:', e); 
      alert('Erro ao iniciar sessão'); 
    }
  };

  const loadPrompts = async () => {
    try {
      const res = await fetch('https://froid.com.br/api/prompts', { 
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` } 
      });
      if (res.ok) { 
        const data = await res.json(); 
        setPrompts(Array.isArray(data) ? data : []); 
      } else { 
        setPrompts([]); 
      }
    } catch (e) { 
      console.error(e); 
      setPrompts([]); 
    }
  };

  const connectVoiceWebSocket = (sid: string) => {
    console.log('🔊 Conectando Voice WebSocket para sessão:', sid);
    const ws = new WebSocket(`wss://froid.com.br/ws/voice/${sid}`);
    ws.onopen = () => { 
      console.log('✅ Voice WebSocket CONECTADO'); 
      setVoiceStatus('connected'); 
    };
    ws.onmessage = (e) => { 
      const d = JSON.parse(e.data); 
      console.log('📨 Voice dados recebidos:', d);
      if (d.dominant_zone) setCurrentZone(d.dominant_zone); 
      if (d.zones) setZoneData(d.zones.map((z: any) => z.energy_normalized * 100)); 
      if (d.spectral_bands) setBandData(d.spectral_bands.map((b: any) => b.energy_normalized * 100)); 
      if (d.clinical_scores) {
        const scores = Array.isArray(d.clinical_scores) ? d.clinical_scores : [];
        const scoreMap: any = {};
        scores.forEach((s: any) => {
          if (s.construct === 'depression_risk') scoreMap.depression = Math.round(s.score * 100);
          if (s.construct === 'mania_activation') scoreMap.mania = Math.round(s.score * 100);
          if (s.construct === 'stress_cognitive') scoreMap.stress = Math.round(s.score * 100);
          if (s.construct === 'anxiety_generalized') scoreMap.anxiety = Math.round(s.score * 100);
          if (s.construct === 'psychosis_risk') scoreMap.psychosis = Math.round(s.score * 100);
          if (s.construct === 'trauma_ptsd') scoreMap.trauma = Math.round(s.score * 100);
          if (s.construct === 'suicide_risk') scoreMap.suicide = Math.round(s.score * 100);
          if (s.construct === 'bipolar_pattern') scoreMap.bipolar = Math.round(s.score * 100);
          if (s.construct === 'schizophrenia_markers') scoreMap.schizophrenia = Math.round(s.score * 100);
        });
        setRiskScores({
          depression: scoreMap.depression || 0,
          mania: scoreMap.mania || 0,
          stress: scoreMap.stress || 0,
          anxiety: scoreMap.anxiety || 0,
          psychosis: scoreMap.psychosis || 0,
          trauma: scoreMap.trauma || 0,
          suicide: scoreMap.suicide || 0,
          bipolar: scoreMap.bipolar || 0,
          schizophrenia: scoreMap.schizophrenia || 0,
        });
      }
      if (d.colorimetry_level !== undefined) setColorimetryLevel(d.colorimetry_level); 
      if (d.ipm_score !== undefined) setIpmScore(d.ipm_score); 
    };
    ws.onerror = (err) => { 
      console.error('❌ Voice WebSocket erro:', err); 
      setVoiceStatus('error'); 
    };
    ws.onclose = () => { 
      console.log('🔴 Voice WebSocket fechado'); 
      setVoiceStatus('disconnected'); 
    };
    voiceWsRef.current = ws;
    (window as any).voiceWs = ws;
  };

  const connectFaceWebSocket = (sid: string) => {
    console.log('📹 Conectando Face WebSocket para sessão:', sid);
    const ws = new WebSocket(`wss://froid.com.br/ws/face/${sid}`);
    ws.onopen = () => { 
      console.log('✅ Face WebSocket CONECTADO'); 
      setFaceStatus('connected'); 
    };
    ws.onmessage = (e) => { 
      const d = JSON.parse(e.data); 
      console.log('📨 Face dados recebidos:', d);
      if (d.dominant_emotion) setCurrentEmotion(d.dominant_emotion); 
    };
    ws.onerror = (err) => { 
      console.error('❌ Face WebSocket erro:', err); 
      setFaceStatus('error'); 
    };
    ws.onclose = () => { 
      console.log('🔴 Face WebSocket fechado'); 
      setFaceStatus('disconnected'); 
    };
    faceWsRef.current = ws;
    (window as any).faceWs = ws;
  };

  const startCamera = async () => {
    console.log('🎬 startCamera INICIADO');
    try {
      console.log('🎤 Solicitando getUserMedia...');
      const s = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 }, audio: true });
      console.log('✅ getUserMedia OK! Tracks:', s.getTracks().map(t => `${t.kind}:${t.readyState}`).join(', '));
      
      if (videoRef.current) {
        videoRef.current.srcObject = s;
        console.log('✅ Video srcObject definido');
      }
      
      console.log('🔊 Criando AudioContext (16kHz)...');
      const ac = new AudioContext({ sampleRate: 16000 });
      const src = ac.createMediaStreamSource(s);
      const proc = ac.createScriptProcessor(4096, 1, 1);
      src.connect(proc); 
      proc.connect(ac.destination);
      console.log('✅ AudioContext criado e pipeline conectado');
      
      let audioChunksSent = 0;
      proc.onaudioprocess = (e) => { 
        if (voiceWsRef.current?.readyState === WebSocket.OPEN) { 
          const inp = e.inputBuffer.getChannelData(0); 
          const pcm = new Int16Array(inp.length); 
          for (let i = 0; i < inp.length; i++) {
            pcm[i] = Math.max(-32768, Math.min(32767, inp[i] * 32768)); 
          }
          voiceWsRef.current.send(pcm.buffer);
          audioChunksSent++;
          if (audioChunksSent % 50 === 0) {
            console.log(`📤 Áudio: ${audioChunksSent} chunks enviados (${(audioChunksSent * 4096 / 16000).toFixed(1)}s)`);
          }
        } else {
          if (audioChunksSent === 0) {
            console.warn('⚠️ Voice WS não está OPEN:', voiceWsRef.current?.readyState);
          }
        }
      };
      console.log('✅ onaudioprocess configurado');
      
      console.log('📹 Criando canvas para captura de frames...');
      const canvas = document.createElement('canvas'); 
      canvas.width = 640; 
      canvas.height = 480; 
      const ctx = canvas.getContext('2d');
      console.log('✅ Canvas criado (640x480)');
      
      let framesSent = 0;
      const sendF = () => { 
        if (faceWsRef.current?.readyState === WebSocket.OPEN && videoRef.current) { 
          ctx?.drawImage(videoRef.current, 0, 0, 640, 480); 
          canvas.toBlob((b) => { 
            if (b) {
              faceWsRef.current?.send(b);
              framesSent++;
              if (framesSent % 10 === 0) {
                console.log(`📤 Frames: ${framesSent} enviados (${(framesSent / 10).toFixed(1)}s @ 10fps)`);
              }
            }
          }, 'image/jpeg', 0.8); 
        }
      };
      
      const fi = setInterval(sendF, 100);
      console.log('✅ Intervalo de frames iniciado (100ms = 10 FPS)');
      
      cleanupFnRef.current = () => { 
        console.log('🧹 Cleanup: parando transmissão');
        clearInterval(fi); 
        proc.disconnect(); 
        src.disconnect(); 
        ac.close(); 
        s.getTracks().forEach(t => t.stop()); 
        console.log('✅ Cleanup concluído');
      };
      
      console.log('✅✅✅ startCamera CONCLUÍDO COM SUCESSO! ✅✅✅');
    } catch (e) { 
      console.error('❌❌❌ ERRO em startCamera:', e); 
      alert('Erro ao acessar câmera/microfone: ' + e); 
    }
  };

  const cleanup = () => { 
    console.log('🧹 cleanup() chamado');
    if (voiceWsRef.current) voiceWsRef.current.close(); 
    if (faceWsRef.current) faceWsRef.current.close(); 
    if (cleanupFnRef.current) cleanupFnRef.current(); 
    if (videoRef.current?.srcObject) { 
      const s = videoRef.current.srcObject as MediaStream; 
      s.getTracks().forEach(t => t.stop()); 
    } 
  };
  
  const handleEndSession = async () => { 
    if (!session) return; 
    try { 
      await fetch(`https://froid.com.br/api/sessions/${session.id}`, { 
        method: 'PATCH', 
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${localStorage.getItem('token')}` }, 
        body: JSON.stringify({ status: 'completed' }) 
      }); 
      cleanup(); 
      navigate('/dashboard'); 
    } catch (e) { 
      console.error(e); 
    } 
  };
  
  const addNote = () => { 
    if (!currentNote.trim()) return; 
    setNotes([...notes, { text: currentNote, timestamp: new Date().toLocaleTimeString('pt-BR') }]); 
    setCurrentNote(''); 
  };
  
  const executePrompt = async () => { 
    if (!selectedPrompt) return; 
    setLoadingPrompt(true); 
    try { 
      const res = await fetch('https://froid.com.br/api/prompts/execute', { 
        method: 'POST', 
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${localStorage.getItem('token')}` }, 
        body: JSON.stringify({ promptId: selectedPrompt, patientId }) 
      }); 
      const d = await res.json(); 
      setPromptResult(d.result); 
      setShowPromptModal(true); 
    } catch (e) { 
      console.error(e); 
      alert('Erro'); 
    } finally { 
      setLoadingPrompt(false); 
    } 
  };

  const zd = { labels: ['C2','C#2','C3','C#3','C4','C#4','C5','C#5','C6','C#6','C7','C#7'], datasets: [{ label: 'I', data: zoneData, backgroundColor: 'rgba(59,130,246,0.5)', borderColor: 'rgb(59,130,246)', borderWidth: 1 }] };
  const bd = { labels: ['Sub','Delta','Theta','Alpha','Beta','Gamma','High-G'], datasets: [{ label: 'E', data: bandData, backgroundColor: 'rgba(16,185,129,0.5)', borderColor: 'rgb(16,185,129)', borderWidth: 1 }] };
  const opts = { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, max: 100 } } };
  const cols = [{name:'Vermelho',color:'#dc2626'},{name:'Laranja',color:'#f97316'},{name:'Amarelo',color:'#facc15'},{name:'Verde',color:'#22c55e'},{name:'Azul',color:'#3b82f6'},{name:'Índigo',color:'#4f46e5'},{name:'Violeta',color:'#9333ea'}];

  return <div className="min-h-screen bg-gray-50 p-6"><div className="max-w-7xl mx-auto"><div className="bg-white rounded-lg shadow p-4 mb-6 flex justify-between"><h1 className="text-2xl font-bold flex items-center gap-2"><span className="w-3 h-3 bg-red-500 rounded-full animate-pulse"></span>Sessão ao Vivo</h1><button onClick={handleEndSession} className="px-6 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700">Finalizar</button></div><div className="grid grid-cols-3 gap-6"><div className="space-y-6"><div className="bg-white rounded-lg shadow p-4"><h2 className="text-lg font-semibold mb-3">📹 Vídeo</h2><video ref={videoRef} autoPlay muted playsInline className="w-full rounded-lg bg-black"/></div><div className="bg-white rounded-lg shadow p-4"><h2 className="text-lg font-semibold mb-3">📝 Anotações</h2><textarea value={currentNote} onChange={(e)=>setCurrentNote(e.target.value)} className="w-full p-3 border rounded-lg mb-2 min-h-[100px]" placeholder="Registre..."/><button onClick={addNote} className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">Adicionar</button><div className="mt-4 space-y-2 max-h-64 overflow-y-auto">{notes.length===0?<p className="text-gray-400 text-center py-4">Sem anotações</p>:notes.map((n,i)=><div key={i} className="p-3 bg-gray-50 rounded-lg"><p className="text-sm">{n.text}</p><p className="text-xs text-gray-400 mt-1">{n.timestamp}</p></div>)}</div></div><div className="bg-white rounded-lg shadow p-4"><h2 className="text-lg font-semibold mb-3">🤖 IA</h2><select value={selectedPrompt} onChange={(e)=>setSelectedPrompt(e.target.value)} className="w-full p-2 border rounded-lg mb-3"><option value="">Selecione...</option>{prompts.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select><button onClick={executePrompt} disabled={!selectedPrompt||loadingPrompt} className="w-full px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:bg-gray-300">{loadingPrompt?'⏳':'🔍'} Executar</button></div></div><div className="space-y-6"><div className="bg-white rounded-lg shadow p-4"><h2 className="text-lg font-semibold mb-3">🎵 12 Zonas</h2><div className="h-48"><Bar data={zd} options={opts}/></div><div className="mt-3 p-3 bg-gray-50 rounded-lg"><p className="text-sm text-gray-600">Zona:</p><p className="text-xl font-bold text-blue-600">{currentZone}</p></div></div><div className="bg-white rounded-lg shadow p-4"><h2 className="text-lg font-semibold mb-3">📊 7 Bandas</h2><div className="h-48"><Bar data={bd} options={opts}/></div></div><div className="bg-white rounded-lg shadow p-4"><h2 className="text-lg font-semibold mb-3">🎨 Colorimetria</h2><p className="text-2xl font-bold">{cols[colorimetryLevel].name}</p><div className="flex gap-1 mt-2">{cols.map((c,i)=><div key={i} style={{flex:1,height:'2rem',backgroundColor:c.color,borderRadius:'0.25rem',opacity:i===colorimetryLevel?1:0.3,border:i===colorimetryLevel?'3px solid #1f2937':'none'}}/>)}</div></div></div><div className="space-y-6"><div className="bg-white rounded-lg shadow p-4"><h2 className="text-lg font-semibold mb-3">🔗 IPM</h2><div className="text-center"><p className="text-4xl font-bold text-purple-600">{ipmScore}%</p><p className="text-sm text-gray-500">Incongruência</p></div></div><div className="bg-white rounded-lg shadow p-4"><h2 className="text-lg font-semibold mb-3">⚡ Status</h2><div className="space-y-2"><div className="flex justify-between"><span className="text-sm">Voice:</span><span style={{padding:'0.25rem 0.5rem',fontSize:'0.75rem',borderRadius:'9999px',backgroundColor:voiceStatus==='connected'?'#dcfce7':'#fef9c3',color:voiceStatus==='connected'?'#166534':'#854d0e'}}>{voiceStatus}</span></div><div className="flex justify-between"><span className="text-sm">Face:</span><span style={{padding:'0.25rem 0.5rem',fontSize:'0.75rem',borderRadius:'9999px',backgroundColor:faceStatus==='connected'?'#dcfce7':'#fef9c3',color:faceStatus==='connected'?'#166534':'#854d0e'}}>{faceStatus}</span></div></div></div><div className="bg-white rounded-lg shadow p-4"><h2 className="text-lg font-semibold mb-3">⚠️ Riscos</h2><div className="space-y-3"><div><div className="flex justify-between text-sm mb-1"><span>Depressão</span><span className="font-bold">{riskScores.depression}%</span></div><div className="w-full bg-gray-200 rounded-full h-2"><div className="bg-blue-600 h-2 rounded-full" style={{width:`${riskScores.depression}%`}}/></div></div><div><div className="flex justify-between text-sm mb-1"><span>Mania</span><span className="font-bold">{riskScores.mania}%</span></div><div className="w-full bg-gray-200 rounded-full h-2"><div className="bg-red-600 h-2 rounded-full" style={{width:`${riskScores.mania}%`}}/></div></div><div><div className="flex justify-between text-sm mb-1"><span>Estresse</span><span className="font-bold">{riskScores.stress}%</span></div><div className="w-full bg-gray-200 rounded-full h-2"><div className="bg-yellow-600 h-2 rounded-full" style={{width:`${riskScores.stress}%`}}/></div></div><div><div className="flex justify-between text-sm mb-1"><span>Ansiedade</span><span className="font-bold">{riskScores.anxiety}%</span></div><div className="w-full bg-gray-200 rounded-full h-2"><div className="bg-orange-600 h-2 rounded-full" style={{width:`${riskScores.anxiety}%`}}/></div></div><div><div className="flex justify-between text-sm mb-1"><span>Psicose</span><span className="font-bold">{riskScores.psychosis}%</span></div><div className="w-full bg-gray-200 rounded-full h-2"><div className="bg-purple-600 h-2 rounded-full" style={{width:`${riskScores.psychosis}%`}}/></div></div><div><div className="flex justify-between text-sm mb-1"><span>Trauma</span><span className="font-bold">{riskScores.trauma}%</span></div><div className="w-full bg-gray-200 rounded-full h-2"><div className="bg-indigo-600 h-2 rounded-full" style={{width:`${riskScores.trauma}%`}}/></div></div><div><div className="flex justify-between text-sm mb-1"><span>Suicídio</span><span className="font-bold text-red-700">{riskScores.suicide}%</span></div><div className="w-full bg-gray-200 rounded-full h-2"><div className="bg-red-800 h-2 rounded-full" style={{width:`${riskScores.suicide}%`}}/></div></div><div><div className="flex justify-between text-sm mb-1"><span>Bipolar</span><span className="font-bold">{riskScores.bipolar}%</span></div><div className="w-full bg-gray-200 rounded-full h-2"><div className="bg-pink-600 h-2 rounded-full" style={{width:`${riskScores.bipolar}%`}}/></div></div><div><div className="flex justify-between text-sm mb-1"><span>Esquizofrenia</span><span className="font-bold">{riskScores.schizophrenia}%</span></div><div className="w-full bg-gray-200 rounded-full h-2"><div className="bg-gray-700 h-2 rounded-full" style={{width:`${riskScores.schizophrenia}%`}}/></div></div></div></div><div className="bg-white rounded-lg shadow p-4"><h2 className="text-lg font-semibold mb-3">😊 Emoções</h2><p className="text-sm text-gray-600">Atual:</p><p className="text-xl font-bold text-green-600">{currentEmotion}</p></div></div></div></div>{showPromptModal&&<div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50"><div className="bg-white rounded-lg max-w-2xl w-full max-h-[80vh] overflow-y-auto p-6"><div className="flex justify-between items-center mb-4"><h2 className="text-xl font-bold">Resultado</h2><button onClick={()=>setShowPromptModal(false)} className="text-gray-500 hover:text-gray-700">✕</button></div><p className="whitespace-pre-wrap">{promptResult}</p></div></div>}</div>;
}
