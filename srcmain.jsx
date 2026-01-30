import React, { useState, useEffect } from 'react';
import { 
  LayoutDashboard, 
  Store, 
  CheckCircle2, 
  Wrench, 
  BookOpen, 
  Plus, 
  Search, 
  ChevronRight, 
  MapPin, 
  Phone, 
  MessageSquare,
  Clock,
  Check,
  AlertCircle,
  TrendingUp,
  Save,
  X,
  Calendar as CalendarIcon,
  RefreshCw,
  User,
  ClipboardList,
  History,
  AlertTriangle,
  Image as ImageIcon,
  Star,
  FileText,
  Lightbulb,
  Briefcase,
  Users,
  Building2,
  Sparkles,
  Copy,
  Hash,
  Camera,
  Target,
  ArrowUpRight,
  Database,
  Loader2,
  Smartphone,
  Share,
  Menu,
  Bot
} from 'lucide-react';

// Firebase SDK Import
import { initializeApp } from 'firebase/app';
import { 
  getAuth, 
  signInAnonymously, 
  onAuthStateChanged, 
  signInWithCustomToken 
} from 'firebase/auth';
import { 
  getFirestore, 
  collection, 
  addDoc, 
  updateDoc, 
  doc, 
  onSnapshot, 
  query, 
  orderBy,
  writeBatch 
} from 'firebase/firestore';

// --- Firebase 초기화 ---
const firebaseConfig = JSON.parse(__firebase_config);
const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const db = getFirestore(app);
const appId = typeof __app_id !== 'undefined' ? __app_id : 'default-app-id';

// --- 카테고리별 컬러 매핑 설정 ---
const CATEGORY_COLORS = {
  'AS': 'bg-orange-100 text-orange-700 border-orange-200',
  '계약관련': 'bg-green-100 text-green-700 border-green-200',
  '법인업무': 'bg-blue-100 text-blue-700 border-blue-200',
  '외부업무협조': 'bg-purple-100 text-purple-700 border-purple-200',
  '내부업무협조': 'bg-gray-100 text-gray-700 border-gray-200'
};

const CATEGORY_ICONS = {
  'AS': Wrench,
  '계약관련': TrendingUp,
  '법인업무': Briefcase,
  '외부업무협조': Users,
  '내부업무협조': ClipboardList
};

// --- 초기 샘플 데이터 ---
const INITIAL_STORES = [
  { id: '1', name: '강남본점', owner: '김점주', tel: '010-1234-5678', businessNo: '123-45-67890', address: '서울 강남구 역삼동 123', model: 'K-1000', grade: 'A', lastVisited: '2024-01-10', salesOpportunity: '재계약' },
  { id: '2', name: '홍대입구점', owner: '이점주', tel: '010-9876-5432', businessNo: '987-65-43210', address: '서울 마포구 서교동 456', model: 'K-2000', grade: 'B', lastVisited: '2023-05-20', salesOpportunity: '업셀링' },
  { id: '3', name: '성수역점', owner: '박점주', tel: '010-1111-2222', businessNo: '111-22-33333', address: '서울 성동구 성수동 789', model: 'K-1000', grade: 'A', lastVisited: '2023-12-01', salesOpportunity: '정기점검' },
];

const INITIAL_EVENTS = [
  { storeId: '1', time: '10:00', title: '포스기 교체 및 계약 연장', category: '계약관련', status: '대기', date: '2026-01-29' },
  { storeId: '2', time: '14:00', title: '키오스크 AS 긴급출동', category: 'AS', status: '접수', date: '2026-01-29' },
];

const INITIAL_WIKI = [
  { 
    title: 'K-2000 모델 용지 걸림 해결', 
    content: '롤러 부분에 이물질이 끼어 발생하는 경우가 많음. 알콜솜으로 닦아내면 해결됨.', 
    tags: ['#키오스크', '#용지걸림', '#K2000'],
    image: 'https://images.unsplash.com/photo-1556742049-0cfed4f6a45d?q=80&w=400&auto=format&fit=crop',
    date: '2025-12-10'
  }
];

const App = () => {
  const [user, setUser] = useState(null);
  const [activeTab, setActiveTab] = useState('dashboard');
  
  // 데이터 상태
  const [stores, setStores] = useState([]);
  const [events, setEvents] = useState([]);
  const [visitLogs, setVisitLogs] = useState([]); 
  const [wiki, setWiki] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  
  // --- 모달 및 폼 상태 ---
  const [isChecklistOpen, setIsChecklistOpen] = useState(false);
  const [isRegisterModalOpen, setIsRegisterModalOpen] = useState(false);
  const [isInstallGuideOpen, setIsInstallGuideOpen] = useState(false);
  const [selectedStore, setSelectedStore] = useState(null);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [formError, setFormError] = useState('');
  
  // --- AI 관련 상태 ---
  const [isAiLoading, setIsAiLoading] = useState(false);
  const [aiReport, setAiReport] = useState('');
  const [aiTip, setAiTip] = useState('');
  const [aiWikiResult, setAiWikiResult] = useState(''); // Wiki AI 검색 결과

  // --- 신규 일정 등록 폼 ---
  const [formData, setFormData] = useState({
    storeName: '', businessNo: '', owner: '', tel: '', address: '',
    time: '09:00', date: new Date().toISOString().split('T')[0], title: '', category: 'AS'
  });

  // --- 업무 마감 및 노하우 등록 폼 ---
  const [routineData, setRoutineData] = useState({
    techCompleted: false,
    salesAction: '상담없음', 
    conversation: '',
    hesitationReason: '없음', 
    saveToWiki: false, 
    wikiImage: '', 
    wikiTags: '',
    wikiContent: '' // AI가 정리해줄 내용
  });
  
  const [wikiSearchTerm, setWikiSearchTerm] = useState('');
  const [salesGoal, setSalesGoal] = useState({ current: 0, target: 20 });

  // --- 1. 인증 처리 ---
  useEffect(() => {
    const initAuth = async () => {
      if (typeof __initial_auth_token !== 'undefined' && __initial_auth_token) {
        await signInWithCustomToken(auth, __initial_auth_token);
      } else {
        await signInAnonymously(auth);
      }
    };
    initAuth();
    const unsubscribe = onAuthStateChanged(auth, (u) => setUser(u));
    return () => unsubscribe();
  }, []);

  // --- 2. 데이터 실시간 동기화 (Firestore) ---
  useEffect(() => {
    if (!user) return;
    setIsLoading(true);

    const storesRef = collection(db, 'artifacts', appId, 'users', user.uid, 'stores');
    const eventsRef = collection(db, 'artifacts', appId, 'users', user.uid, 'events');
    const logsRef = collection(db, 'artifacts', appId, 'users', user.uid, 'visitLogs');
    const wikiRef = collection(db, 'artifacts', appId, 'users', user.uid, 'wiki');

    const unsubStores = onSnapshot(storesRef, (snapshot) => {
      const data = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
      setStores(data);
    });

    const unsubEvents = onSnapshot(eventsRef, (snapshot) => {
      const data = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
      data.sort((a, b) => new Date(a.date + 'T' + a.time) - new Date(b.date + 'T' + b.time));
      setEvents(data);
      setIsLoading(false);
    });

    const unsubLogs = onSnapshot(logsRef, (snapshot) => {
      const data = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
      data.sort((a, b) => new Date(b.date) - new Date(a.date));
      setVisitLogs(data);
      setSalesGoal(prev => ({ ...prev, current: data.length }));
    });

    const unsubWiki = onSnapshot(wikiRef, (snapshot) => {
      const data = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
      data.sort((a, b) => new Date(b.date) - new Date(a.date));
      setWiki(data);
    });

    return () => {
      unsubStores(); unsubEvents(); unsubLogs(); unsubWiki();
    };
  }, [user]);

  const loadSampleData = async () => {
    if (!user) return;
    const batch = writeBatch(db);
    INITIAL_STORES.forEach(store => {
      const ref = doc(collection(db, 'artifacts', appId, 'users', user.uid, 'stores'));
      batch.set(ref, store);
    });
    INITIAL_EVENTS.forEach(event => {
       const ref = doc(collection(db, 'artifacts', appId, 'users', user.uid, 'events'));
       batch.set(ref, event);
    });
    INITIAL_WIKI.forEach(item => {
      const ref = doc(collection(db, 'artifacts', appId, 'users', user.uid, 'wiki'));
      batch.set(ref, item);
    });
    await batch.commit();
  };

  // --- Gemini API 호출 함수 ---
  const callGeminiApi = async (prompt) => {
    const apiKey = ""; 
    setIsAiLoading(true);
    try {
      const response = await fetch(
        `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent?key=${apiKey}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ contents: [{ parts: [{ text: prompt }] }] })
        }
      );
      const data = await response.json();
      setIsAiLoading(false);
      return data.candidates?.[0]?.content?.parts?.[0]?.text || "AI 응답을 불러올 수 없습니다.";
    } catch (error) {
      console.error("Gemini API Error:", error);
      setIsAiLoading(false);
      return "네트워크 오류가 발생했습니다.";
    }
  };

  // 1. 영업 전략 생성
  const handleGenerateSalesTip = async () => {
    if (!routineData.hesitationReason && !routineData.conversation) {
      setAiTip("망설임 사유나 대화 내용을 먼저 입력해주세요.");
      return;
    }
    const prompt = `당신은 베테랑 기술 영업 멘토입니다. 대화내용: "${routineData.conversation}", 망설임사유: "${routineData.hesitationReason}"를 바탕으로 영업 대응 전략을 3줄로 요약해줘.`;
    const result = await callGeminiApi(prompt);
    setAiTip(result);
  };

  // 2. 보고서 생성
  const handleGenerateReport = async () => {
    if (!selectedStore) return;
    const prompt = `매장명: ${selectedStore.name}, 조치여부: ${routineData.techCompleted ? "완료" : "미완료"}, 상담내용: "${routineData.conversation}" 내용을 바탕으로 점주님께 보낼 정중한 방문 결과 보고 문자를 작성해줘.`;
    const result = await callGeminiApi(prompt);
    setAiReport(result);
  };

  // 3. ✨ AI 노하우 자동 정리 (New)
  const handleRefineWiki = async () => {
    if (!routineData.conversation) {
      setRoutineData(prev => ({...prev, wikiContent: "정리할 대화 내용이 없습니다."}));
      return;
    }
    const prompt = `
      다음은 현장에서 엔지니어가 메모한 내용입니다. 
      이 내용을 다른 기술자들도 참고할 수 있도록 '기술 위키(Wiki)'에 올릴 문서 형태로 정리해주세요.
      
      [입력 내용]
      "${routineData.conversation}"
      
      [출력 형식]
      1. 증상: (한줄 요약)
      2. 원인: (추정 원인)
      3. 해결 방법: (단계별 조치 내용)
      4. 주의 사항: (필요시)
      
      반말이나 메모체 대신 명확한 서술형을 사용하세요.
    `;
    const result = await callGeminiApi(prompt);
    setRoutineData(prev => ({...prev, wikiContent: result}));
  };

  // 4. ✨ AI 기술 질문 (Wiki Search) (New)
  const handleAiWikiSearch = async () => {
    if (!wikiSearchTerm) return;
    
    // 현재 보유한 노하우 타이틀 리스트 추출 (RAG 시뮬레이션)
    const existingTitles = wiki.map(w => w.title).join(", ");
    
    const prompt = `
      사용자가 기술적인 문제에 대해 질문했습니다: "${wikiSearchTerm}"
      
      당신은 이 회사의 기술 지원 AI입니다.
      아래 [보유 노하우 목록]을 참고하여 관련 문서가 있다면 추천해주고,
      없다면 당신의 일반적인 기술 지식을 바탕으로 해결책을 제시해주세요.
      
      [보유 노하우 목록]
      ${existingTitles}
      
      답변은 짧고 명확하게 한국어로 해주세요.
    `;
    
    const result = await callGeminiApi(prompt);
    setAiWikiResult(result);
  };

  const handleRegisterSchedule = async (e) => {
    e.preventDefault();
    if (!formData.storeName || !formData.businessNo || !formData.owner || !formData.tel || !formData.address) {
      setFormError('필수 정보를 모두 입력해주세요.');
      return;
    }
    if (!user) return;

    try {
      const storesRef = collection(db, 'artifacts', appId, 'users', user.uid, 'stores');
      const newStoreDoc = await addDoc(storesRef, {
        name: formData.storeName,
        businessNo: formData.businessNo,
        owner: formData.owner,
        tel: formData.tel,
        address: formData.address,
        model: '신규등록',
        grade: 'C',
        lastVisited: '방문없음',
        salesOpportunity: '신규'
      });

      const eventsRef = collection(db, 'artifacts', appId, 'users', user.uid, 'events');
      await addDoc(eventsRef, {
        storeId: newStoreDoc.id,
        time: formData.time,
        date: formData.date,
        title: formData.title || `${formData.category} 업무`,
        category: formData.category,
        status: '접수'
      });

      setIsRegisterModalOpen(false);
      setFormError('');
      setFormData({ storeName: '', businessNo: '', owner: '', tel: '', address: '', time: '09:00', date: new Date().toISOString().split('T')[0], title: '', category: 'AS' });
    } catch (error) {
      console.error("Error adding document: ", error);
      setFormError("저장 중 오류가 발생했습니다.");
    }
  };

  const handleCompleteVisit = async () => {
    if (!selectedStore || !user) return;

    try {
      const storeRef = doc(db, 'artifacts', appId, 'users', user.uid, 'stores', selectedStore.id);
      await updateDoc(storeRef, {
        lastVisited: new Date().toISOString().split('T')[0]
      });
      
      if (selectedEvent) {
        const eventRef = doc(db, 'artifacts', appId, 'users', user.uid, 'events', selectedEvent.id);
        await updateDoc(eventRef, { status: '완료' });
      }
      
      const logsRef = collection(db, 'artifacts', appId, 'users', user.uid, 'visitLogs');
      await addDoc(logsRef, {
        storeName: selectedStore.name,
        date: new Date().toISOString().split('T')[0],
        ...routineData,
        aiTip: aiTip
      });

      if (routineData.saveToWiki) {
        const wikiRef = collection(db, 'artifacts', appId, 'users', user.uid, 'wiki');
        await addDoc(wikiRef, {
          title: `${selectedStore.name} 이슈 (${new Date().toISOString().split('T')[0]})`,
          content: routineData.wikiContent || routineData.conversation || '상세 내용 없음',
          tags: routineData.wikiTags.split(' ').filter(t => t.startsWith('#')),
          image: routineData.wikiImage || 'https://via.placeholder.com/400x300?text=No+Image',
          date: new Date().toISOString().split('T')[0]
        });
      }

      setRoutineData({ techCompleted: false, salesAction: '상담없음', conversation: '', hesitationReason: '없음', saveToWiki: false, wikiImage: '', wikiTags: '', wikiContent: '' });
      setAiTip('');
      setAiReport('');
      setIsChecklistOpen(false);
      setSelectedStore(null);
      setSelectedEvent(null);

    } catch (error) {
      console.error("Error completing visit: ", error);
    }
  };

  const handleOpenSalesRoutine = (store, actionType) => {
    setSelectedStore(store);
    setRoutineData({
      techCompleted: false,
      salesAction: actionType,
      conversation: '',
      hesitationReason: '없음',
      saveToWiki: false, wikiImage: '', wikiTags: '', wikiContent: ''
    });
    setIsChecklistOpen(true);
  };

  const NavButton = ({ id, icon: Icon, label, badge }) => (
    <button
      onClick={() => setActiveTab(id)}
      className={`flex flex-col items-center justify-center w-full py-2 text-[10px] font-bold transition-colors relative ${
        activeTab === id ? 'text-blue-600' : 'text-gray-400 hover:text-blue-400'
      }`}
    >
      <Icon size={20} className="mb-1" />
      {label}
      {badge > 0 && (
        <span className="absolute top-1 right-2 w-4 h-4 bg-red-500 text-white text-[10px] flex items-center justify-center rounded-full border-2 border-white">
          {badge}
        </span>
      )}
    </button>
  );

  // --- 뷰: 캘린더 ---
  const CalendarView = () => (
    <div className="space-y-4 animate-in fade-in duration-500">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-black text-gray-800">업무 캘린더</h1>
        <button className="p-2 bg-white border border-gray-200 rounded-xl"><RefreshCw size={18} className="text-gray-400"/></button>
      </div>
      <div className="bg-white p-4 rounded-3xl shadow-sm border border-gray-100">
        <div className="flex justify-between items-center mb-4">
          <h2 className="font-bold text-gray-800">2026년 1월</h2>
          <div className="flex gap-2">
             <button className="p-1 text-gray-400"><ChevronRight size={18} className="rotate-180" /></button>
             <button className="p-1 text-gray-400"><ChevronRight size={18} /></button>
          </div>
        </div>
        <div className="grid grid-cols-7 gap-1 text-center mb-2">
          {['일', '월', '화', '수', '목', '금', '토'].map(d => <span key={d} className="text-[10px] font-bold text-gray-400">{d}</span>)}
        </div>
        <div className="grid grid-cols-7 gap-1">
          {[...Array(31)].map((_, i) => {
            const day = i + 1;
            const isToday = day === 29;
            const hasEvent = events.some(e => parseInt(e.date.split('-')[2]) === day);
            return (
              <div key={i} className={`aspect-square flex flex-col items-center justify-center rounded-xl relative ${isToday ? 'bg-blue-600 text-white' : 'text-gray-700'}`}>
                <span className="text-xs font-bold">{day}</span>
                {hasEvent && !isToday && <div className="w-1 h-1 bg-blue-400 rounded-full mt-0.5"></div>}
              </div>
            );
          })}
        </div>
      </div>
      <div className="space-y-3">
        <h3 className="text-xs font-black text-gray-400 uppercase tracking-widest px-1">선택일 일정</h3>
        {events.filter(e => e.date === '2026-01-29').length === 0 ? (
          <div className="text-center py-4 text-xs text-gray-400">일정이 없습니다.</div>
        ) : (
          events.filter(e => e.date === '2026-01-29').map(event => {
            const store = stores.find(s => s.id === event.storeId);
            return (
              <div key={event.id} className="flex items-center gap-3 bg-white p-3 rounded-2xl border border-gray-100">
                <div className={`w-1 h-8 rounded-full ${CATEGORY_COLORS[event.category]?.split(' ')[0] || 'bg-gray-200'}`}></div>
                <div className="flex-1">
                  <p className="text-[10px] font-black text-gray-400">{event.time} | {event.category}</p>
                  <p className="text-sm font-bold text-gray-800">{store?.name || '가맹점 정보 없음'}</p>
                </div>
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded-lg ${event.status === '완료' ? 'bg-gray-100 text-gray-400' : 'bg-blue-50 text-blue-600'}`}>{event.status}</span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );

  // --- 뷰: 기술 노하우 (Wiki) ---
  const WikiView = () => {
    const filteredWiki = wiki.filter(item => 
      item.title.includes(wikiSearchTerm) || 
      (item.tags && item.tags.some(tag => tag.includes(wikiSearchTerm)))
    );

    return (
      <div className="space-y-4 animate-in slide-in-from-right duration-500">
        <div className="flex justify-between items-center">
          <h1 className="text-2xl font-black text-gray-800">기술 노하우</h1>
          <div className="bg-blue-50 text-blue-600 px-3 py-1 rounded-full text-xs font-bold">{wiki.length}건</div>
        </div>

        <div className="relative flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
            <input 
              type="text" 
              placeholder="검색 또는 AI에게 질문..." 
              className="w-full pl-10 pr-4 py-3 bg-white border border-gray-200 rounded-2xl text-sm focus:ring-2 focus:ring-blue-500"
              value={wikiSearchTerm}
              onChange={(e) => setWikiSearchTerm(e.target.value)}
            />
          </div>
          <button 
            onClick={handleAiWikiSearch}
            disabled={isAiLoading || !wikiSearchTerm}
            className="bg-purple-600 text-white p-3 rounded-2xl shadow-lg hover:bg-purple-700 transition-colors disabled:bg-gray-300"
          >
            {isAiLoading ? <Loader2 className="animate-spin" size={20}/> : <Bot size={20} />}
          </button>
        </div>

        {/* AI 검색 결과 표시 */}
        {aiWikiResult && (
          <div className="bg-purple-50 p-4 rounded-3xl border border-purple-100 animate-in fade-in slide-in-from-top-2">
            <div className="flex items-center gap-2 mb-2">
              <Sparkles className="text-purple-600" size={16} />
              <span className="text-xs font-black text-purple-700">AI 기술 해결사</span>
            </div>
            <p className="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">{aiWikiResult}</p>
            <button 
              onClick={() => setAiWikiResult('')} 
              className="text-[10px] text-gray-400 mt-2 underline"
            >
              닫기
            </button>
          </div>
        )}

        <div className="space-y-4">
          {filteredWiki.map((item) => (
            <div key={item.id} className="bg-white rounded-3xl overflow-hidden border border-gray-100 shadow-sm">
              <div className="relative h-40 bg-gray-100">
                {item.image ? (
                  <img src={item.image} alt={item.title} className="w-full h-full object-cover" />
                ) : (
                  <div className="flex items-center justify-center h-full text-gray-400"><ImageIcon size={32} /></div>
                )}
                <div className="absolute top-3 right-3 bg-black/50 backdrop-blur-md text-white px-2 py-1 rounded-lg text-[10px] font-bold">
                  {item.date}
                </div>
              </div>
              <div className="p-5">
                <div className="flex flex-wrap gap-1 mb-2">
                  {item.tags && item.tags.map((tag, idx) => (
                    <span key={idx} className="text-[10px] font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded-md">
                      {tag}
                    </span>
                  ))}
                </div>
                <h3 className="font-bold text-gray-800 text-lg mb-1">{item.title}</h3>
                <p className="text-sm text-gray-500 line-clamp-2">{item.content}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className="max-w-md mx-auto h-screen bg-gray-50 flex flex-col shadow-2xl overflow-hidden font-sans relative">
      {/* 상단바 */}
      <div className="bg-white px-6 pt-6 pb-2 border-b border-gray-100 shrink-0">
        <div className="flex justify-between items-center mb-2">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center text-white font-black text-xl italic shadow-sm">G</div>
            <span className="font-bold text-gray-800 tracking-tight">Pro 통합 매니저</span>
          </div>
          <div className="flex gap-2">
            <button 
              onClick={() => setIsInstallGuideOpen(true)}
              className="p-2 bg-gray-100 text-gray-600 rounded-xl active:scale-90 transition-transform"
            >
              <Smartphone size={20} />
            </button>
            <button 
              onClick={() => setIsRegisterModalOpen(true)}
              className="p-2 bg-blue-600 text-white rounded-xl shadow-lg shadow-blue-100 active:scale-90 transition-transform"
            >
              <Plus size={20} />
            </button>
          </div>
        </div>
      </div>

      <main className="flex-1 overflow-y-auto px-6 py-4 pb-24 scroll-smooth">
        {isLoading ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-400">
            <Loader2 className="animate-spin mb-2" size={32} />
            <span className="text-xs font-bold">데이터 불러오는 중...</span>
          </div>
        ) : stores.length === 0 && events.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full space-y-4 p-6 text-center">
            <div className="w-16 h-16 bg-blue-50 rounded-full flex items-center justify-center mb-2">
               <Database className="text-blue-600" size={32} />
            </div>
            <h2 className="text-xl font-black text-gray-800">환영합니다!</h2>
            <p className="text-sm text-gray-500">아직 등록된 업무 데이터가 없습니다.<br/>샘플 데이터를 불러와 앱을 체험해보세요.</p>
            <button 
              onClick={loadSampleData}
              className="px-6 py-3 bg-blue-600 text-white rounded-2xl text-sm font-bold shadow-lg shadow-blue-200"
            >
              샘플 데이터 불러오기
            </button>
          </div>
        ) : activeTab === 'dashboard' && (
          <div className="space-y-6 animate-in fade-in duration-500">
             <header>
               <h1 className="text-2xl font-black text-gray-800">오늘의 스케줄</h1>
               <p className="text-sm text-gray-500 font-medium">색상별 업무를 확인하세요.</p>
             </header>

             <div className="flex flex-wrap gap-2">
                {Object.keys(CATEGORY_COLORS).map(cat => (
                  <span key={cat} className={`text-[9px] font-black px-2 py-0.5 rounded-full border ${CATEGORY_COLORS[cat]}`}>{cat}</span>
                ))}
             </div>

             <section className="space-y-3">
               {events.filter(e => e.status !== '완료').length === 0 ? (
                 <div className="text-center py-6 text-gray-400 text-xs">예정된 업무가 없습니다. + 버튼을 눌러 등록하세요.</div>
               ) : (
                 events.filter(e => e.status !== '완료').map((event) => {
                   const store = stores.find(s => s.id === event.storeId);
                   const CategoryIcon = CATEGORY_ICONS[event.category] || Clock;
                   return (
                     <div key={event.id} className="flex items-center gap-4 bg-white p-4 rounded-3xl border border-gray-100 shadow-sm">
                       <div className={`w-12 h-12 rounded-2xl flex flex-col items-center justify-center shrink-0 border ${CATEGORY_COLORS[event.category]?.split(' ')[0] || 'bg-gray-100'}`}>
                          <CategoryIcon size={18} />
                          <span className="text-[8px] font-black mt-0.5">{event.time}</span>
                       </div>
                       <div className="flex-1 min-w-0">
                         <p className="text-[10px] font-black text-gray-400 mb-0.5 uppercase">{event.category}</p>
                         <h3 className="text-sm font-bold text-gray-800 truncate">{store?.name || '정보 없음'}</h3>
                         <p className="text-[11px] text-gray-500 truncate">{event.title}</p>
                       </div>
                       <button 
                         onClick={() => { setSelectedStore(store); setSelectedEvent(event); setIsChecklistOpen(true); }} 
                         className="bg-gray-100 text-gray-400 p-2 rounded-xl"
                       >
                         <ChevronRight size={18} />
                       </button>
                     </div>
                   );
                 })
               )}
             </section>

             <section className="bg-gray-800 text-white p-5 rounded-3xl shadow-xl">
               <div className="flex justify-between items-center mb-3">
                 <h2 className="text-sm font-bold flex items-center gap-2"><Target size={18} className="text-green-400"/> 이달의 영업 목표</h2>
                 <span className="text-[10px] font-black bg-gray-700 px-2 py-1 rounded-lg">달성률 {Math.round((salesGoal.current / salesGoal.target) * 100)}%</span>
               </div>
               <div className="w-full bg-gray-700 rounded-full h-2 mb-2">
                 <div className="bg-gradient-to-r from-green-400 to-blue-500 h-2 rounded-full" style={{ width: `${Math.min((salesGoal.current / salesGoal.target) * 100, 100)}%` }}></div>
               </div>
               <div className="flex justify-between text-[10px] text-gray-400 font-bold">
                 <span>현재 {salesGoal.current}건 완료</span>
                 <span>목표 {salesGoal.target}건</span>
               </div>
             </section>

             {stores.some(s => s.salesOpportunity) && (
               <section className="space-y-3 pb-4">
                 <div className="flex justify-between items-center px-1">
                   <h2 className="text-lg font-black text-gray-800 flex items-center gap-2">
                     <TrendingUp size={20} className="text-blue-600" /> 
                     영업 기회 (AI 추천)
                   </h2>
                   <span className="text-[10px] font-bold bg-blue-50 text-blue-600 px-2 py-1 rounded-full animate-pulse">Now</span>
                 </div>
                 
                 <div className="flex gap-3 overflow-x-auto pb-4 -mx-6 px-6 scrollbar-hide snap-x">
                   {stores.filter(s => s.salesOpportunity).map(store => (
                     <div 
                       key={store.id}
                       onClick={() => handleOpenSalesRoutine(store, store.salesOpportunity)}
                       className="min-w-[200px] snap-center bg-white p-4 rounded-3xl border border-green-100 shadow-sm flex flex-col justify-between h-32 relative overflow-hidden group cursor-pointer active:scale-95 transition-transform"
                     >
                        <div className="absolute right-0 top-0 w-16 h-16 bg-green-50 rounded-bl-full -mr-4 -mt-4 transition-transform group-hover:scale-110"></div>
                        <div className="relative z-10">
                          <span className="text-[9px] font-black text-green-600 bg-green-50 px-2 py-1 rounded-lg">{store.salesOpportunity} 제안</span>
                          <h3 className="font-bold text-gray-800 mt-2 text-lg">{store.name}</h3>
                          <p className="text-[10px] text-gray-500">{store.model || '기기'} 점검 및 제안</p>
                        </div>
                        <div className="flex justify-end relative z-10">
                          <button className="bg-green-600 text-white p-2 rounded-xl shadow-lg shadow-green-100"><ArrowUpRight size={16}/></button>
                        </div>
                     </div>
                   ))}
                 </div>
               </section>
             )}
          </div>
        )}

        {activeTab === 'calendar' && <CalendarView />}
        {activeTab === 'as' && (
          <div className="space-y-4 animate-in slide-in-from-right duration-500">
            <h1 className="text-2xl font-black text-gray-800">현장 AS 관리</h1>
            <div className="space-y-3">
              {events.filter(e => e.category === 'AS').map(item => {
                const store = stores.find(s => s.id === item.storeId);
                return (
                  <div key={item.id} className={`p-5 rounded-3xl border shadow-sm bg-white border-orange-100 ${item.status === '완료' ? 'opacity-50' : ''}`}>
                    <div className="flex justify-between items-start mb-3">
                      <span className="bg-orange-100 text-orange-600 text-[10px] font-black px-2 py-1 rounded-lg">AS 접수</span>
                      <span className="text-xs text-gray-400 font-bold">{item.time}</span>
                    </div>
                    <h3 className="font-bold text-gray-800 text-lg">{store?.name || '가맹점 미상'}</h3>
                    <p className="text-sm text-gray-500 mb-4">{item.title}</p>
                    <button onClick={() => { setSelectedStore(store); setSelectedEvent(item); setIsChecklistOpen(true); }} className="w-full py-3 bg-orange-500 text-white rounded-2xl text-xs font-black">보고서 작성</button>
                  </div>
                );
              })}
            </div>
          </div>
        )}
        {activeTab === 'stores' && (
          <div className="space-y-4">
            <h1 className="text-2xl font-black text-gray-800">가맹점 목록</h1>
            <div className="space-y-3">
              {stores.map(store => (
                <div key={store.id} className="p-5 bg-white rounded-3xl border border-gray-100 shadow-sm">
                  <div className="flex justify-between mb-2">
                    <h3 className="font-bold text-lg text-gray-800">{store.name}</h3>
                    <span className="text-xs font-bold text-blue-600 bg-blue-50 px-2 py-1 rounded-lg">{store.grade}</span>
                  </div>
                  <div className="text-xs text-gray-500 space-y-1">
                    <p className="flex items-center gap-2"><Building2 size={12}/> {store.businessNo}</p>
                    <p className="flex items-center gap-2"><MapPin size={12}/> {store.address}</p>
                    <p className="flex items-center gap-2"><Phone size={12}/> {store.tel}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
        {activeTab === 'wiki' && <WikiView />}
      </main>

      {/* 설치 가이드 모달 */}
      {isInstallGuideOpen && (
        <div className="absolute inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-6">
          <div className="bg-white w-full max-w-sm rounded-3xl p-6 space-y-4 animate-in zoom-in-95">
             <div className="flex justify-between items-center">
               <h2 className="text-xl font-black text-gray-800">앱 설치 방법</h2>
               <button onClick={() => setIsInstallGuideOpen(false)} className="bg-gray-100 p-2 rounded-full"><X size={20}/></button>
             </div>
             <div className="space-y-4">
               <div className="bg-gray-50 p-4 rounded-2xl border border-gray-100">
                 <h3 className="text-sm font-bold text-blue-600 mb-2 flex items-center gap-2"><Smartphone size={16}/> 아이폰 (iOS)</h3>
                 <ol className="text-xs text-gray-600 space-y-1 list-decimal list-inside font-medium">
                   <li>사파리(Safari) 브라우저로 접속합니다.</li>
                   <li>하단 중앙의 <Share size={10} className="inline"/> <strong>공유 버튼</strong>을 누릅니다.</li>
                   <li>메뉴에서 <strong>'홈 화면에 추가'</strong>를 선택합니다.</li>
                 </ol>
               </div>
               <div className="bg-gray-50 p-4 rounded-2xl border border-gray-100">
                 <h3 className="text-sm font-bold text-green-600 mb-2 flex items-center gap-2"><Smartphone size={16}/> 갤럭시 (Android)</h3>
                 <ol className="text-xs text-gray-600 space-y-1 list-decimal list-inside font-medium">
                   <li>크롬(Chrome) 브라우저로 접속합니다.</li>
                   <li>상단 우측의 <Menu size={10} className="inline"/> <strong>점 3개 메뉴</strong>를 누릅니다.</li>
                   <li><strong>'앱 설치'</strong> 또는 <strong>'홈 화면에 추가'</strong>를 선택합니다.</li>
                 </ol>
               </div>
             </div>
             <button onClick={() => setIsInstallGuideOpen(false)} className="w-full py-3 bg-blue-600 text-white rounded-xl font-bold">확인했습니다</button>
          </div>
        </div>
      )}

      {/* 일정 및 가맹점 등록 모달 */}
      {isRegisterModalOpen && (
        <div className="absolute inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-end">
          <div className="w-full bg-white rounded-t-[40px] p-8 space-y-6 animate-in slide-in-from-bottom duration-300 max-h-[95%] overflow-y-auto">
            <div className="flex justify-between items-center">
              <h2 className="text-xl font-black text-gray-800">가맹점 일정 등록</h2>
              <button onClick={() => setIsRegisterModalOpen(false)} className="p-2 bg-gray-100 rounded-full text-gray-400"><X size={20} /></button>
            </div>
            {formError && (
              <div className="bg-red-50 text-red-600 p-3 rounded-xl text-[10px] font-bold flex items-center gap-2">
                <AlertCircle size={14} /> {formError}
              </div>
            )}
            <form onSubmit={handleRegisterSchedule} className="space-y-4 pb-10">
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1"><label className="text-[10px] font-black text-gray-400 ml-1">가맹점명 *</label><input className="w-full bg-gray-50 border-none rounded-2xl p-3 text-sm font-bold" placeholder="매장명" value={formData.storeName} onChange={(e) => setFormData({...formData, storeName: e.target.value})} /></div>
                  <div className="space-y-1"><label className="text-[10px] font-black text-gray-400 ml-1">사업자번호 *</label><input className="w-full bg-gray-50 border-none rounded-2xl p-3 text-sm font-bold" placeholder="000-00-00000" value={formData.businessNo} onChange={(e) => setFormData({...formData, businessNo: e.target.value})} /></div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1"><label className="text-[10px] font-black text-gray-400 ml-1">대표자명 *</label><input className="w-full bg-gray-50 border-none rounded-2xl p-3 text-sm font-bold" placeholder="대표자 성함" value={formData.owner} onChange={(e) => setFormData({...formData, owner: e.target.value})} /></div>
                  <div className="space-y-1"><label className="text-[10px] font-black text-gray-400 ml-1">연락처 *</label><input className="w-full bg-gray-50 border-none rounded-2xl p-3 text-sm font-bold" placeholder="010-0000-0000" value={formData.tel} onChange={(e) => setFormData({...formData, tel: e.target.value})} /></div>
                </div>
                <div className="space-y-1"><label className="text-[10px] font-black text-gray-400 ml-1">주소 *</label><input className="w-full bg-gray-50 border-none rounded-2xl p-3 text-sm font-bold" placeholder="상세 주소 입력" value={formData.address} onChange={(e) => setFormData({...formData, address: e.target.value})} /></div>
                <div className="h-px bg-gray-100 my-2"></div>
                <div className="space-y-1"><label className="text-[10px] font-black text-gray-400 ml-1">업무 내용</label><input className="w-full bg-gray-50 border-none rounded-2xl p-3 text-sm font-bold" placeholder="예: 정기 점검 및 수리" value={formData.title} onChange={(e) => setFormData({...formData, title: e.target.value})} /></div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1"><label className="text-[10px] font-black text-gray-400 ml-1">카테고리</label><select className="w-full bg-gray-50 border-none rounded-2xl p-3 text-sm font-bold" value={formData.category} onChange={(e) => setFormData({...formData, category: e.target.value})}>{Object.keys(CATEGORY_COLORS).map(cat => <option key={cat} value={cat}>{cat}</option>)}</select></div>
                  <div className="space-y-1"><label className="text-[10px] font-black text-gray-400 ml-1">방문 시간</label><input type="time" className="w-full bg-gray-50 border-none rounded-2xl p-3 text-sm font-bold" value={formData.time} onChange={(e) => setFormData({...formData, time: e.target.value})} /></div>
                </div>
              </div>
              <button type="submit" className="w-full py-5 bg-blue-600 text-white rounded-3xl font-black shadow-xl mt-4">일정 및 가맹점 등록</button>
            </form>
          </div>
        </div>
      )}

      {/* 업무 보고서 작성 모달 */}
      {isChecklistOpen && (
        <div className="absolute inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-end">
          <div className="w-full bg-white rounded-t-[40px] p-8 space-y-6 animate-in slide-in-from-bottom duration-300 max-h-[95%] overflow-y-auto">
            <div className="flex justify-between items-center">
              <h2 className="text-xl font-black text-gray-800">{selectedStore?.name} <span className="text-blue-600">업무 마감</span></h2>
              <button onClick={() => setIsChecklistOpen(false)} className="p-2 bg-gray-100 rounded-full text-gray-400"><X size={20} /></button>
            </div>
            <div className="space-y-4">
               <div className="space-y-2">
                 <label className="text-[10px] font-black text-gray-400">영업 액션 (루틴)</label>
                 <div className="grid grid-cols-3 gap-2">
                   {['상담없음', '재계약', '업셀링', '신규제안', '클레임방어'].map(action => (
                     <button 
                       key={action}
                       onClick={() => setRoutineData({...routineData, salesAction: action})}
                       className={`py-2 px-1 rounded-xl text-[10px] font-black border transition-all ${routineData.salesAction === action ? 'bg-green-600 text-white border-green-600' : 'bg-white text-gray-400 border-gray-100'}`}
                     >
                       {action}
                     </button>
                   ))}
                 </div>
               </div>

               <div className="space-y-2">
                 <label className="text-[10px] font-black text-gray-400">현장 조치 상태</label>
                 <button onClick={() => setRoutineData({...routineData, techCompleted: !routineData.techCompleted})} className={`w-full p-4 rounded-2xl border-2 flex items-center justify-between transition-all ${routineData.techCompleted ? 'border-blue-500 bg-blue-50' : 'border-gray-50 bg-gray-50'}`}>
                   <span className="text-sm font-bold">기술 점검/조치 완료</span>
                   {routineData.techCompleted && <CheckCircle2 className="text-blue-500" />}
                 </button>
               </div>
               <div className="space-y-2">
                 <label className="text-[10px] font-black text-gray-400">계약/구매 망설임 사유</label>
                 <select className="w-full bg-gray-50 border-none rounded-2xl p-3 text-sm font-bold" value={routineData.hesitationReason} onChange={(e) => setRoutineData({...routineData, hesitationReason: e.target.value})}>
                   <option value="없음">해당 없음</option><option value="가격 부담">가격 부담</option><option value="타사 비교">타사 비교</option><option value="기능 불만">기능 불만</option><option value="결정 권한 없음">결정 권한 없음</option>
                 </select>
               </div>
               <div className="space-y-2">
                 <label className="text-[10px] font-black text-gray-400 flex justify-between items-center">
                   <span>상담 내용 및 특이사항</span>
                   <button onClick={handleGenerateSalesTip} disabled={isAiLoading} className="flex items-center gap-1 text-blue-600 bg-blue-50 px-2 py-0.5 rounded-lg hover:bg-blue-100 transition-colors"><Sparkles size={12} /> {isAiLoading ? "분석 중..." : "AI 전략 분석"}</button>
                 </label>
                 <textarea className="w-full bg-gray-50 border-none rounded-2xl p-4 text-sm min-h-[100px]" placeholder="내용을 입력하세요." value={routineData.conversation} onChange={(e) => setRoutineData({...routineData, conversation: e.target.value})}></textarea>
               </div>
               {aiTip && (
                 <div className="bg-gradient-to-r from-blue-50 to-purple-50 p-4 rounded-2xl border border-blue-100 animate-in fade-in zoom-in-95">
                   <div className="flex items-center gap-2 mb-2"><Lightbulb className="text-yellow-500 fill-yellow-500" size={16} /><span className="text-xs font-black text-gray-700">AI 영업 가이드</span></div>
                   <p className="text-xs text-gray-700 leading-relaxed whitespace-pre-wrap">{aiTip}</p>
                 </div>
               )}

               {/* --- 노하우 등록 섹션 (AI 자동 정리 추가) --- */}
               <div className="pt-2 border-t border-dashed border-gray-200 space-y-3">
                 <button 
                   onClick={() => setRoutineData({...routineData, saveToWiki: !routineData.saveToWiki})}
                   className={`flex items-center gap-2 text-xs font-bold transition-colors ${routineData.saveToWiki ? 'text-blue-600' : 'text-gray-400'}`}
                 >
                   <div className={`w-4 h-4 rounded border flex items-center justify-center ${routineData.saveToWiki ? 'bg-blue-600 border-blue-600' : 'border-gray-300'}`}>
                     {routineData.saveToWiki && <Check size={10} className="text-white" />}
                   </div>
                   이 내용을 기술 노하우로 등록하기
                 </button>

                 {routineData.saveToWiki && (
                   <div className="bg-gray-50 p-4 rounded-2xl space-y-3 animate-in fade-in slide-in-from-top-2">
                      <div className="flex justify-between items-center">
                        <label className="text-[10px] font-black text-gray-400">노하우 내용 정리</label>
                        <button 
                          onClick={handleRefineWiki}
                          disabled={isAiLoading || !routineData.conversation}
                          className="flex items-center gap-1 text-[10px] text-purple-600 bg-purple-50 px-2 py-1 rounded-lg hover:bg-purple-100 transition-colors"
                        >
                          <Sparkles size={10} /> AI 자동 정리
                        </button>
                      </div>
                      <textarea 
                        className="w-full bg-white border border-gray-200 rounded-xl p-3 text-xs min-h-[80px]" 
                        placeholder="위의 대화 내용이 자동으로 정리되어 입력됩니다."
                        value={routineData.wikiContent || routineData.conversation}
                        onChange={(e) => setRoutineData({...routineData, wikiContent: e.target.value})}
                      ></textarea>

                      <div className="space-y-1">
                        <label className="text-[10px] font-black text-gray-400 ml-1">해시태그</label>
                        <div className="relative">
                          <Hash size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                          <input 
                            className="w-full bg-white border border-gray-200 rounded-xl pl-9 pr-3 py-2 text-xs" 
                            placeholder="#포스기 #전원불량" 
                            value={routineData.wikiTags}
                            onChange={(e) => setRoutineData({...routineData, wikiTags: e.target.value})}
                          />
                        </div>
                      </div>
                      <div className="space-y-1">
                        <label className="text-[10px] font-black text-gray-400 ml-1">현장 사진</label>
                        <div className="relative">
                          <Camera size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                          <input 
                            className="w-full bg-white border border-gray-200 rounded-xl pl-9 pr-3 py-2 text-xs" 
                            placeholder="https://..." 
                            value={routineData.wikiImage}
                            onChange={(e) => setRoutineData({...routineData, wikiImage: e.target.value})}
                          />
                        </div>
                      </div>
                   </div>
                 )}
               </div>

               <div className="pt-2">
                 <button onClick={handleGenerateReport} disabled={isAiLoading || !routineData.conversation} className="w-full py-3 bg-gray-800 text-white rounded-2xl text-xs font-bold flex items-center justify-center gap-2 hover:bg-gray-700 transition-colors"><MessageSquare size={14} /> {isAiLoading ? "작성 중..." : "점주 발송용 리포트 작성"}</button>
                 {aiReport && (
                   <div className="mt-3 bg-gray-50 p-4 rounded-2xl border border-gray-200 animate-in slide-in-from-top-2">
                     <div className="flex justify-between items-center mb-2"><span className="text-[10px] font-black text-gray-400">발송 메시지 초안</span><button className="text-gray-400 hover:text-blue-600" onClick={() => navigator.clipboard.writeText(aiReport)}><Copy size={14}/></button></div>
                     <p className="text-xs text-gray-600 leading-relaxed whitespace-pre-wrap select-all">{aiReport}</p>
                   </div>
                 )}
               </div>
            </div>
            <button onClick={handleCompleteVisit} disabled={!routineData.conversation || !routineData.techCompleted} className={`w-full py-5 rounded-3xl font-black shadow-xl ${routineData.conversation && routineData.techCompleted ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-400'}`}>저장 및 업무 마감</button>
          </div>
        </div>
      )}

      {/* 하단 네비게이션 */}
      <nav className="bg-white/95 backdrop-blur-md border-t border-gray-100 px-2 py-1 flex justify-around items-center fixed bottom-0 w-full max-w-md z-10 shadow-lg">
        <NavButton id="dashboard" icon={LayoutDashboard} label="홈" />
        <NavButton id="calendar" icon={CalendarIcon} label="캘린더" />
        <NavButton id="as" icon={Wrench} label="AS/현장" badge={events.filter(e => e.category === 'AS' && e.status !== '완료').length} />
        <NavButton id="stores" icon={Store} label="가맹점" />
        <NavButton id="wiki" icon={BookOpen} label="노하우" />
      </nav>
    </div>
  );
};

export default App;
