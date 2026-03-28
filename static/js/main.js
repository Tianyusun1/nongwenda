document.addEventListener('DOMContentLoaded', () => {
    const chatWindow = document.getElementById('chatWindow');
    const userInput = document.getElementById('userInput');
    const sendBtn = document.getElementById('sendBtn');
    const voiceBtn = document.getElementById('voiceBtn');
    const locationText = document.getElementById('locationText');
    const locationTag = document.getElementById('locationTag');

    // 全局状态
    let currentUserLocation = null;
    let isRecording = false;

    // ==========================================
    // 1. 【新增】用户登录状态检查与 UI 更新
    // ==========================================
    function updateAuthUI() {
        // 我们通过请求 health 接口或其他方式，在后端 session 中获取状态
        // 也可以直接在 index.html 渲染时注入变量，这里采用更灵活的 JS 检查
        fetch('/api/health') // 利用健康检查接口顺便探测登录态（或者新增一个专门的 /api/user/info）
            .then(res => res.json())
            .then(data => {
                // 假设我们在后端返回中加入了简单的 session 识别或在 index.html 预留容器
                const authContainer = document.getElementById('authContainer');
                if (!authContainer) return;

                // 注意：这里为了配合 app.py 的 session，我们通常在后端模板里直接判断更准
                // 但为了系统完整性，我们在前端也写好动态逻辑
            });
    }

    // ==========================================
    // 2. 特色功能：LBS 自动定位
    // ==========================================
    function initLocation() {
        if (navigator.geolocation) {
            locationText.innerText = "定位中...";
            navigator.geolocation.getCurrentPosition(
                (position) => {
                    const lat = position.coords.latitude;
                    const lon = position.coords.longitude;
                    fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}&zoom=10&addressdetails=1`)
                        .then(res => res.json())
                        .then(data => {
                            const address = data.address;
                            currentUserLocation = address.state || address.city || address.province || "未知地区";
                            locationText.innerText = currentUserLocation;
                            locationTag.style.color = "#fff9c4";
                        })
                        .catch(() => {
                            locationText.innerText = "定位解析失败";
                            currentUserLocation = null;
                        });
                },
                (error) => {
                    locationText.innerText = "未开启定位";
                },
                { timeout: 10000 }
            );
        } else {
            locationText.innerText = "浏览器不支持定位";
        }
    }

    locationTag.addEventListener('click', initLocation);
    initLocation();

    // ==========================================
    // 3. 特色功能：ASR 语音识别 (Web Speech API)
    // ==========================================
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    let recognition = null;

    if (SpeechRecognition) {
        recognition = new SpeechRecognition();
        recognition.lang = 'zh-CN';
        recognition.continuous = false;
        recognition.interimResults = false;

        recognition.onstart = function() {
            isRecording = true;
            voiceBtn.style.backgroundColor = "#d32f2f";
            voiceBtn.innerHTML = '<i class="fas fa-stop" style="color:white"></i>';
            userInput.placeholder = "正在聆听，请说话...";
        };

        recognition.onresult = function(event) {
            const transcript = event.results[0][0].transcript;
            userInput.value = transcript;
            sendMessage(true);
        };

        recognition.onerror = function() { resetVoiceBtn(); };
        recognition.onend = function() { resetVoiceBtn(); };
    } else {
        voiceBtn.style.display = 'none';
    }

    function resetVoiceBtn() {
        isRecording = false;
        voiceBtn.style.backgroundColor = "#fff";
        voiceBtn.innerHTML = '<i class="fas fa-microphone" style="color: #2e7d32;"></i>';
        userInput.placeholder = "请输入问题，或点击左侧麦克风说话...";
    }

    voiceBtn.addEventListener('click', () => {
        if (!recognition) return alert("您的浏览器不支持语音识别。");
        isRecording ? recognition.stop() : recognition.start();
    });

    // ==========================================
    // 4. 核心交互：聊天气泡与卡片渲染
    // ==========================================
    function getCurrentTime() {
        const now = new Date();
        return `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
    }

    function scrollToBottom() {
        chatWindow.scrollTop = chatWindow.scrollHeight;
    }

    function generateCardHTML(cardData) {
        if (!cardData || cardData.length === 0) return '';
        let cardsHtml = '<div class="kg-cards-container">';
        cardData.forEach(item => {
            cardsHtml += `
                <div class="kg-card">
                    <div class="kg-card-header">
                        <i class="fas fa-seedling"></i> <strong>${item.品种}</strong>
                    </div>
                    <div class="kg-card-body">
                        <p><span><i class="fas fa-balance-scale"></i> 亩产：</span>${item.亩产} 公斤</p>
                        <p><span><i class="fas fa-certificate"></i> 审定：</span>${item.审定号}</p>
                        ${item.抗病害.length > 0 ? `<p><span><i class="fas fa-shield-virus"></i> 抗病：</span>${item.抗病害.join('、')}</p>` : ''}
                        ${item.耐受特性.length > 0 ? `<p><span><i class="fas fa-sun"></i> 抗逆：</span>${item.耐受特性.join('、')}</p>` : ''}
                    </div>
                </div>
            `;
        });
        cardsHtml += '</div>';
        return cardsHtml;
    }

    function appendMessage(type, text, cardData = null) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}-message`;
        let avatarHTML = type === 'bot' ? `<div class="avatar"><i class="fas fa-user-graduate"></i></div>` : '';
        let extraCardHTML = (type === 'bot' && cardData) ? generateCardHTML(cardData) : '';
        const formattedText = text.replace(/\n/g, '<br>');

        messageDiv.innerHTML = `
            ${avatarHTML}
            <div class="content">
                <p>${formattedText}</p>
                ${extraCardHTML}
                <span class="time">${getCurrentTime()}</span>
            </div>
        `;
        chatWindow.appendChild(messageDiv);
        scrollToBottom();
    }

    function sendMessage(isVoice = false) {
        const text = userInput.value.trim();
        if (text === '') return;

        appendMessage('user', text);
        userInput.value = '';
        userInput.style.height = 'auto';

        const loadingId = 'loading-' + Date.now();
        const loadingDiv = document.createElement('div');
        loadingDiv.className = `message bot-message`;
        loadingDiv.id = loadingId;
        loadingDiv.innerHTML = `
            <div class="avatar"><i class="fas fa-user-graduate"></i></div>
            <div class="content"><p><i class="fas fa-spinner fa-spin"></i> 专家正在查阅图谱分析中...</p></div>
        `;
        chatWindow.appendChild(loadingDiv);
        scrollToBottom();

        //
        // 这里的后端接口会根据 Session 自动关联 user_id
        fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: text,
                location: currentUserLocation,
                is_voice: isVoice
            }),
        })
        .then(response => response.json())
        .then(data => {
            document.getElementById(loadingId).remove();
            if (data.code === 200) {
                appendMessage('bot', data.reply, data.card_data);
            } else {
                appendMessage('bot', `抱歉，出现了一些问题：${data.msg}`);
            }
        })
        .catch(error => {
            if(document.getElementById(loadingId)) document.getElementById(loadingId).remove();
            appendMessage('bot', '糟了，与服务器的连接断开了。');
        });
    }

    sendBtn.addEventListener('click', () => sendMessage(false));
    userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage(false);
        }
    });

    userInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
        this.style.overflowY = this.scrollHeight > 100 ? "scroll" : "hidden";
    });
});