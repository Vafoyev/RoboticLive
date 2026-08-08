// Urganch "Aqlli Yordamchi" - Pure Emotional Conversational AI Controller

let isVoiceActive = false;
let liveWebSocket = null;
let recognition = null;
let audioContext = null;
let currentOutputText = "";
let isAIPlayingAudio = false;
let nextAudioStartTime = 0;
let lastRAGUsed = false;

function initAudioContext() {
    if (!audioContext) {
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (audioContext.state === 'suspended') {
        audioContext.resume();
    }
}

// Play PCM 24kHz Audio Chunks with Jitter Buffering
function playGeminiPCM24kAudio(base64PCM) {
    initAudioContext();
    pauseListeningForEchoPrevention();

    try {
        const rawBinary = atob(base64PCM);
        const len = rawBinary.length;
        const pcm16 = new Int16Array(len / 2);
        
        for (let i = 0; i < len; i += 2) {
            pcm16[i / 2] = (rawBinary.charCodeAt(i + 1) << 8) | rawBinary.charCodeAt(i);
        }

        const float32 = new Float32Array(pcm16.length);
        for (let i = 0; i < pcm16.length; i++) {
            float32[i] = pcm16[i] / 32768.0;
        }

        const buffer = audioContext.createBuffer(1, float32.length, 24000);
        buffer.getChannelData(0).set(float32);

        const source = audioContext.createBufferSource();
        source.buffer = buffer;
        source.connect(audioContext.destination);

        const currentTime = audioContext.currentTime;
        if (nextAudioStartTime < currentTime + 0.03) {
            nextAudioStartTime = currentTime + 0.03;
        }

        source.start(nextAudioStartTime);
        nextAudioStartTime += buffer.duration;

        document.getElementById('soundWaves')?.classList.add('active');
        const statusText = document.getElementById('audioStatusText');
        if (statusText) statusText.innerText = "Jonli Notiq Gapirmoqda...";

        source.onended = () => {
            if (audioContext.currentTime >= nextAudioStartTime - 0.05) {
                setTimeout(() => {
                    if (!isAIPlayingAudio && isVoiceActive) {
                        resumeListeningAfterAI();
                    }
                    if (statusText) statusText.innerText = "Tayyor";
                }, 200);
            }
        };
    } catch (err) {
        console.error("PCM Audio decode error:", err);
    }
}

// Dual-Engine Audio Player (HTML5 /api/tts + SpeechSynthesis Fallback)
function speakNativeText(text) {
    if (!text || !text.trim()) return;
    
    // Clean markdown, symbols, and IDs for natural speech
    let cleanText = text
        .replace(/[#*`_📌🔹⚠️✉️💡]/g, '')
        .replace(/---/g, ' ')
        .replace(/UH-\d+/g, '')
        .replace(/YT-\d+/g, '')
        .replace(/ST-\d+/g, '')
        .replace(/SOL-\d+/g, '')
        .replace(/\n+/g, ' ')
        .trim();
        
    // Phonetic Guard (Prevents O -> A reduction)
    cleanText = cleanText
        .replace(/\bbera alaman\b/gi, 'bera olaman')
        .replace(/\bbera alamanmi\b/gi, 'bera olamanmi')
        .replace(/\balaman\b/gi, 'olaman')
        .replace(/\balamanmi\b/gi, 'olamanmi');

    if (!cleanText) return;

    const audioEl = document.getElementById('appAudioPlayer');
    const statusText = document.getElementById('audioStatusText');
    const audioUrl = `/api/tts?text=${encodeURIComponent(cleanText.substring(0, 500))}`;

    if (statusText) statusText.innerText = "Ovoz yangramoqda...";

    if (audioEl) {
        audioEl.src = audioUrl;
        audioEl.onplay = () => {
            isAIPlayingAudio = true;
            document.getElementById('soundWaves')?.classList.add('active');
            if (statusText) statusText.innerText = "Gapirmoqda (Playing Audio)...";
        };
        audioEl.onended = () => {
            isAIPlayingAudio = false;
            document.getElementById('soundWaves')?.classList.remove('active');
            if (statusText) statusText.innerText = "Tayyor";
            resumeListeningAfterAI();
        };
        audioEl.onerror = () => {
            fallbackToSpeechSynthesis(cleanText);
        };
        
        const playPromise = audioEl.play();
        if (playPromise !== undefined) {
            playPromise.catch(err => {
                console.log("Direct play caught:", err);
                fallbackToSpeechSynthesis(cleanText);
            });
        }
    } else {
        fallbackToSpeechSynthesis(cleanText);
    }
}

function fallbackToSpeechSynthesis(cleanText) {
    if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(cleanText);
        utterance.lang = 'uz-UZ';
        utterance.rate = 1.0;
        utterance.pitch = 1.1;
        
        utterance.onstart = () => {
            isAIPlayingAudio = true;
            document.getElementById('soundWaves')?.classList.add('active');
        };
        utterance.onend = () => {
            isAIPlayingAudio = false;
            document.getElementById('soundWaves')?.classList.remove('active');
            resumeListeningAfterAI();
        };
        
        window.speechSynthesis.speak(utterance);
    }
}

function testSpeakerVoice() {
    initAudioContext();
    const testText = "Assalomu alaykum! Men Urganch shahrining 'Aqlli Yordamchi' sun'iy intellekt suhbatdoshiman. Sizga qanday yordam bera olaman?";
    appendMessage('assistant', testText, true, 'Aoede / Madina Neural');
    speakNativeText(testText);
}

function sendManualTextMessage() {
    const input = document.getElementById('userTextInput');
    const text = input ? input.value.trim() : "";
    if (!text) return;
    
    input.value = "";
    appendMessage('user', text);
    sendRESTMessage(text);
}

function pauseListeningForEchoPrevention() {
    isAIPlayingAudio = true;
    if (recognition) {
        try { recognition.stop(); } catch(e) {}
    }
}

function resumeListeningAfterAI() {
    isAIPlayingAudio = false;
    if (isVoiceActive && recognition) {
        try { recognition.start(); } catch(e) {}
    }
}

// Instant Audio Interruption (Barge-In) Function
function stopAllAudioImmediately(reason = "To'xtatildi") {
    const audioEl = document.getElementById('appAudioPlayer');
    if (audioEl) {
        audioEl.pause();
        audioEl.currentTime = 0;
        audioEl.removeAttribute('src');
    }
    
    if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
    }
    
    if (audioContext) {
        try {
            audioContext.suspend().then(() => {
                if (audioContext) audioContext.resume();
            });
        } catch (e) {}
        nextAudioStartTime = 0;
    }
    
    isAIPlayingAudio = false;
    
    document.getElementById('soundWaves')?.classList.remove('active');
    const statusText = document.getElementById('audioStatusText');
    if (statusText) statusText.innerText = "To'xtatildi";
    
    if (liveWebSocket && liveWebSocket.readyState === WebSocket.OPEN) {
        liveWebSocket.send(JSON.stringify({
            event: 'client_interrupted'
        }));
    }
}

// Global Escape Key to Stop Voice Instantly
window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        stopAllAudioImmediately("Escape tugmasi bilan to'xtatildi");
    }
});

// Speech Recognition setup with adaptive language fallback and Instant Barge-In
if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = false;
    recognition.lang = 'uz-UZ';

    recognition.onresult = (event) => {
        const lastIndex = event.results.length - 1;
        const transcript = event.results[lastIndex][0].transcript.trim();
        const lower = transcript.toLowerCase();

        // 1. Instant Barge-In Stop Keywords
        if (lower.includes("to'xta") || lower.includes("toxta") || lower.includes("stop") || 
            lower.includes("bo'ldi") || lower.includes("boldi") || lower.includes("jim") || 
            lower.includes("yetar") || lower.includes("shart emas") || lower.includes("to'xtang") ||
            lower.includes("toxtang") || lower.includes("bas")) {
            
            console.log("Instant Barge-In Stop triggered by user keyword:", transcript);
            stopAllAudioImmediately("Foydalanuvchi to'xtatdi");
            appendMessage('user', `🛑 ${transcript} (Ovoz darhol to'xtatildi)`);
            return;
        }

        // If user speaks while audio was playing, immediately interrupt previous speech
        if (isAIPlayingAudio) {
            stopAllAudioImmediately();
        }

        if (transcript) {
            appendMessage('user', transcript);
            nextAudioStartTime = 0;
            
            if (liveWebSocket && liveWebSocket.readyState === WebSocket.OPEN) {
                liveWebSocket.send(JSON.stringify({
                    event: 'speech_input',
                    text: transcript
                }));
            } else {
                sendRESTMessage(transcript);
            }
        }
    };

    recognition.onerror = (event) => {
        console.log('Speech recognition notice:', event.error);
        if (event.error === 'language-not-supported') {
            recognition.lang = 'tr-TR';
            if (isVoiceActive && !isAIPlayingAudio) {
                try { recognition.start(); } catch(e) {}
            }
        }
    };

    recognition.onend = () => {
        if (isVoiceActive && !isAIPlayingAudio) {
            try { recognition.start(); } catch(e) {}
        } else {
            stopListeningState();
        }
    };
}

// Toggle Gemini 3.1 Flash Live Session
function togglePureVoiceMode() {
    initAudioContext();
    nextAudioStartTime = 0;

    const micSphere = document.getElementById('mainMicTrigger');
    const micIcon = document.getElementById('micIcon');
    const statusLabel = document.getElementById('micStatusLabel');
    const ring = document.getElementById('ringVisualizer');
    const badge = document.getElementById('liveStatusBadge');

    if (isVoiceActive) {
        isVoiceActive = false;
        if (liveWebSocket) {
            liveWebSocket.close();
            liveWebSocket = null;
        }
        stopListeningState();

        micSphere.classList.remove('listening');
        micIcon.className = 'fa-solid fa-microphone';
        statusLabel.innerText = "Mikrofonni bosing va gapiring (to'xtatish uchun \"To'xta\" deng)";
        ring.classList.remove('active');
        badge.innerHTML = '<div class="pulse-dot"></div> TAYYOR';

    } else {
        isVoiceActive = true;
        if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
            navigator.mediaDevices.getUserMedia({ audio: true })
                .then(stream => {
                    console.log("Microphone permission granted");
                })
                .catch(err => {
                    console.warn("Microphone permission needed:", err);
                });
        }

        connectGemini31LiveWebSocket();

        micSphere.classList.add('listening');
        micIcon.className = 'fa-solid fa-microphone-slash';
        statusLabel.innerText = "Jonli Suhbat Faol — Bemalol gapirishingiz mumkin...";
        ring.classList.add('active');
        badge.innerHTML = '<div class="pulse-dot" style="background:var(--accent-pink);"></div> JONLI SUHBATDOSH';

        startListeningState();
    }
}

// Connect to Gemini 3.1 Flash Live WebSocket
function connectGemini31LiveWebSocket() {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/ws/live`;
    
    liveWebSocket = new WebSocket(wsUrl);
    currentOutputText = "";
    nextAudioStartTime = 0;
    lastRAGUsed = false;

    liveWebSocket.onopen = () => {
        console.log("Connected to Dynamic RAG Gemini 3.1 Stream");
    };

    liveWebSocket.onmessage = (event) => {
        const payload = JSON.parse(event.data);
        
        if (payload.event === 'rag_applied') {
            lastRAGUsed = payload.rag_used;
        }

        if (payload.event === 'gemini_audio_chunk' && payload.audio_b64) {
            playGeminiPCM24kAudio(payload.audio_b64);
        }

        if (payload.event === 'output_transcript' && payload.text) {
            currentOutputText += payload.text;
            updateOrCreateAssistantMessage(currentOutputText, lastRAGUsed);
        }

        if (payload.event === 'turn_complete') {
            if (currentOutputText && !isAIPlayingAudio) {
                speakNativeText(currentOutputText);
            }
            currentOutputText = "";
            resumeListeningAfterAI();
        }
    };

    liveWebSocket.onclose = () => {
        console.log("Gemini 3.1 Live Session Closed");
    };
}

function updateOrCreateAssistantMessage(text, ragUsed = false) {
    const chatHistory = document.getElementById('chatHistory');
    let lastBubble = chatHistory.querySelector('.message-bubble.assistant.live-active');
    
    if (!lastBubble) {
        lastBubble = document.createElement('div');
        lastBubble.className = 'message-bubble assistant live-active';
        chatHistory.appendChild(lastBubble);
    }
    
    let content = text.replace(/\n/g, '<br>');
    if (ragUsed) {
        content += `<br><span class="rag-tag"><i class="fa-solid fa-brain"></i> RAG Ma'lumot</span>`;
    }
    content += `<span class="rag-tag" style="margin-left: 6px; background: rgba(255, 51, 102, 0.15); color: var(--accent-pink);"><i class="fa-solid fa-venus"></i> Ayol Notiq (Aoede)</span>`;
    
    lastBubble.innerHTML = content;
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

function startListeningState() {
    document.getElementById('soundWaves')?.classList.add('active');
    try {
        if (recognition) recognition.start();
    } catch(e) {}
}

function stopListeningState() {
    document.getElementById('soundWaves')?.classList.remove('active');
}

function switchTab(tabId) {
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.nav-btn').forEach(el => el.classList.remove('active'));

    document.getElementById(tabId).classList.add('active');
    
    const navButtons = document.querySelectorAll('.nav-btn');
    if (tabId === 'agent-tab') navButtons[0].classList.add('active');
    if (tabId === 'rag-tab') {
        navButtons[1].classList.add('active');
        loadRAGDocs();
    }
    if (tabId === 'portal-tab') {
        navButtons[2].classList.add('active');
        loadSubmissions();
    }
}

async function sendRESTMessage(message) {
    const chatHistory = document.getElementById('chatHistory');
    const loadingBubble = document.createElement('div');
    loadingBubble.className = 'message-bubble assistant';
    loadingBubble.id = 'tempLoading';
    loadingBubble.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> O\'ylamoqda...';
    chatHistory.appendChild(loadingBubble);
    chatHistory.scrollTop = chatHistory.scrollHeight;

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: message })
        });
        
        const data = await response.json();
        
        const tempMsg = document.getElementById('tempLoading');
        if (tempMsg) tempMsg.remove();

        appendMessage('assistant', data.text, data.rag_used, 'Aqlli Yordamchi');
        speakNativeText(data.text);
    } catch (err) {
        console.error(err);
        const tempMsg = document.getElementById('tempLoading');
        if (tempMsg) tempMsg.remove();
        appendMessage('assistant', "Kechirasiz, tarmoqda xatolik yuz berdi. Iltimos qayta urinib ko'ring.");
    }
}

function appendMessage(sender, text, ragUsed = false, modelUsed = null) {
    const chatHistory = document.getElementById('chatHistory');
    const bubble = document.createElement('div');
    bubble.className = `message-bubble ${sender}`;
    
    let content = text.replace(/\n/g, '<br>');
    if (ragUsed) {
        content += `<br><span class="rag-tag"><i class="fa-solid fa-brain"></i> RAG Ma'lumot</span>`;
    }
    if (modelUsed) {
        content += `<span class="rag-tag" style="margin-left: 6px; background: rgba(255, 51, 102, 0.15); color: var(--accent-pink);"><i class="fa-solid fa-venus"></i> ${modelUsed}</span>`;
    }
    
    bubble.innerHTML = content;
    chatHistory.appendChild(bubble);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

// Modals and Submissions
function openSubmissionModal(type) {
    document.getElementById('subType').value = type;
    const titleMap = {
        'shikoyat': '⚠️ Shikoyat Yuborish',
        'murojaat': '✉️ Rasmiy Murojaat Qoldirish',
        'taklif': '💡 Taklif Bildirish'
    };
    document.getElementById('modalFormTitle').innerText = titleMap[type] || 'Murojaat Formasi';
    document.getElementById('submissionModal').classList.add('active');
}

function closeSubmissionModal() {
    document.getElementById('submissionModal').classList.remove('active');
}

async function submitForm(event) {
    event.preventDefault();
    const payload = {
        type: document.getElementById('subType').value,
        full_name: document.getElementById('subFullName').value,
        phone: document.getElementById('subPhone').value,
        mahalla: document.getElementById('subMahalla').value,
        address: document.getElementById('subAddress').value,
        topic: document.getElementById('subTopic').value,
        description: document.getElementById('subDescription').value
    };

    try {
        const response = await fetch('/api/submissions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            alert("Murojaatingiz muvaffaqiyatli saqlandi va ro'yxatga olindi!");
            closeSubmissionModal();
            document.getElementById('submissionForm').reset();
        } else {
            alert("Xatolik yuz berdi.");
        }
    } catch(err) {
        console.error(err);
        alert("Tizim bilan ulanishda xatolik.");
    }
}

function openRAGModal() {
    document.getElementById('ragModal').classList.add('active');
}

function closeRAGModal() {
    document.getElementById('ragModal').classList.remove('active');
}

async function submitRAGDoc(event) {
    event.preventDefault();
    const payload = {
        title: document.getElementById('ragTitle').value,
        category: document.getElementById('ragCategory').value,
        content: document.getElementById('ragContent').value
    };

    try {
        const res = await fetch('/api/rag/docs', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (res.ok) {
            alert("RAG Bilimi saqlandi va AI uchun tayyorlandi!");
            closeRAGModal();
            document.getElementById('ragForm').reset();
            loadRAGDocs();
        }
    } catch(err) {
        console.error(err);
    }
}

async function loadRAGDocs() {
    const container = document.getElementById('ragDocsContainer');
    try {
        const res = await fetch('/api/rag/docs');
        const docs = await res.json();
        
        container.innerHTML = '';
        docs.forEach(doc => {
            const card = document.createElement('div');
            card.className = 'glass-panel';
            card.style.padding = '20px';
            card.innerHTML = `
                <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:10px;">
                    <span class="rag-tag">${doc.category.toUpperCase()}</span>
                    <button class="close-btn" style="font-size:1rem;" onclick="deleteRAG('${doc.id}')"><i class="fa-solid fa-trash"></i></button>
                </div>
                <h4 style="margin-bottom:8px;">${doc.title}</h4>
                <p style="font-size:0.85rem; color:var(--text-muted); line-height:1.5;">${doc.content.substring(0, 180)}...</p>
            `;
            container.appendChild(card);
        });
    } catch(err) {
        console.error(err);
    }
}

async function deleteRAG(id) {
    if (!confirm("Ushbu ma'lumotni RAG bazasidan o'chirmoqchimisiz?")) return;
    try {
        await fetch(`/api/rag/docs/${id}`, { method: 'DELETE' });
        loadRAGDocs();
    } catch(err) {
        console.error(err);
    }
}

async function loadSubmissions() {
    const tbody = document.getElementById('submissionsTableBody');
    try {
        const res = await fetch('/api/submissions');
        const list = await res.json();
        
        tbody.innerHTML = '';
        if (list.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color:var(--text-muted);">Hozircha murojaatlar yo'q</td></tr>`;
            return;
        }

        list.forEach(item => {
            const tr = document.createElement('tr');
            const dateStr = new Date(item.timestamp * 1000).toLocaleString('uz-UZ');
            
            const badgeClass = item.type === 'shikoyat' ? 'status-yangi' : (item.type === 'taklif' ? 'status-haletildi' : 'status-koruvda');

            tr.innerHTML = `
                <td><span class="status-badge ${badgeClass}">${item.type.toUpperCase()}</span></td>
                <td><strong>${item.full_name}</strong><br><small style="color:var(--text-muted);">${item.phone}</small></td>
                <td>${item.mahalla}<br><small style="color:var(--text-muted);">${item.address || ''}</small></td>
                <td><strong>${item.topic}</strong><br><small style="color:var(--text-muted);">${item.description}</small></td>
                <td><span class="status-badge status-koruvda">${item.status}</span></td>
                <td style="font-size:0.8rem; color:var(--text-muted);">${dateStr}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch(err) {
        console.error(err);
    }
}
