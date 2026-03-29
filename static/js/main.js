document.addEventListener('DOMContentLoaded', () => {
    // --- 1. 基础组件获取 ---
    const chatWindow = document.getElementById('chatWindow');
    const userInput = document.getElementById('userInput');
    const sendBtn = document.getElementById('sendBtn');
    const voiceBtn = document.getElementById('voiceBtn');
    const locationText = document.getElementById('locationText');
    const locationTag = document.getElementById('locationTag');

    // --- 2. 历史记录侧边栏组件 ---
    const historySidebar = document.getElementById('historySidebar');
    const historyList = document.getElementById('historyList');
    const openHistoryBtn = document.getElementById('openHistoryBtn');
    const closeHistoryBtn = document.getElementById('closeHistoryBtn');
    const sidebarOverlay = document.getElementById('sidebarOverlay');

    // 全局状态
    let currentUserLocation = null;
    let isRecording = false;

    // ==========================================
    // 1. 初始化：自动欢迎语与定位
    // ==========================================
    const initApp = () => {
        const welcomeMsg = "您好！我是您的农产品良种咨询专家。您可以问我类似“河南适合种什么玉米？”或“先玉335的特征是什么？”的问题。";
        appendMessage('bot', welcomeMsg);
        initLocation();
    };

    // ==========================================
    // 2. 特色功能：LBS 自动定位
    // ==========================================
    function initLocation() {
        if (!navigator.geolocation) {
            locationText.innerText = "不支持定位";
            return;
        }

        locationText.innerText = "正在定位...";
        navigator.geolocation.getCurrentPosition(
            (position) => {
                const lat = position.coords.latitude;
                const lon = position.coords.longitude;
                fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}&zoom=10`, {
                    headers: { 'Accept-Language': 'zh-CN' }
                })
                .then(res => res.json())
                .then(data => {
                    const address = data.address;
                    currentUserLocation = address.province || address.city || address.state || "未知地区";
                    currentUserLocation = currentUserLocation.replace(/[省市]/g, '');
                    locationText.innerText = currentUserLocation;
                    locationTag.classList.add('active');
                })
                .catch(() => {
                    locationText.innerText = "定位解析失败";
                });
            },
            (error) => {
                locationText.innerText = "请手动输入地区";
                locationTag.onclick = () => {
                    const manualLoc = prompt("请输入您所在的省份或城市（如：河南）：");
                    if (manualLoc) {
                        currentUserLocation = manualLoc.replace(/[省市]/g, '');
                        locationText.innerText = currentUserLocation;
                    }
                };
            },
            { timeout: 8000 }
        );
    }

    // ==========================================
    // 3. 特色功能：ASR 语音识别 (Web Speech API)
    // ==========================================
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    let recognition = null;

    if (SpeechRecognition) {
        recognition = new SpeechRecognition();
        recognition.lang = 'zh-CN';
        recognition.interimResults = false;

        recognition.onstart = () => {
            isRecording = true;
            voiceBtn.classList.add('recording');
            voiceBtn.innerHTML = '<i class="fas fa-stop"></i>';
            userInput.placeholder = "正在聆听，请说话...";
        };

        recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            userInput.value = transcript;
            sendMessage(true);
        };

        recognition.onerror = () => resetVoiceBtn();
        recognition.onend = () => resetVoiceBtn();
    } else {
        voiceBtn.style.display = 'none';
    }

    function resetVoiceBtn() {
        isRecording = false;
        voiceBtn.classList.remove('recording');
        voiceBtn.innerHTML = '<i class="fas fa-microphone"></i>';
        userInput.placeholder = "请输入问题...";
    }

    voiceBtn.addEventListener('click', () => {
        if (!recognition) return;
        isRecording ? recognition.stop() : recognition.start();
    });

    // ==========================================
    // 4. 核心交互：消息渲染逻辑
    // ==========================================
    function appendMessage(type, text, cardData = null) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}-message animate__animated animate__fadeInUp`;

        let avatarHTML = type === 'bot' ? `<div class="avatar"><i class="fas fa-robot"></i></div>` : '';
        let cardHTML = (type === 'bot' && cardData && cardData.length > 0) ? generateCardHTML(cardData) : '';

        const formattedText = text.replace(/\n/g, '<br>');

        messageDiv.innerHTML = `
            ${avatarHTML}
            <div class="content">
                <div class="text-bubble">${formattedText}</div>
                ${cardHTML}
                <span class="time">${new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span>
            </div>
        `;
        chatWindow.appendChild(messageDiv);
        chatWindow.scrollTop = chatWindow.scrollHeight;
    }

    function generateCardHTML(data) {
        return `
            <div class="kg-cards-scroll">
                ${data.map(item => `
                    <div class="kg-card">
                        <div class="kg-card-badge">推荐品种</div>
                        <h4><i class="fas fa-seedling"></i> ${item.variety || item.品种}</h4>
                        <div class="kg-info">
                            <p><strong><i class="fas fa-chart-line"></i> 预估亩产:</strong> ${item.yield || item.亩产}kg</p>
                            <p><strong><i class="fas fa-id-card"></i> 审定编号:</strong> ${item.approval || item.审定号 || '暂无'}</p>
                            <p><strong><i class="fas fa-shield-alt"></i> 抗性特性:</strong> ${(item.resistances || item.抗性 || []).join('、') || '常规'}</p>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
    }

    // ==========================================
    // 5. 消息发送逻辑
    // ==========================================
    function sendMessage(isVoice = false) {
        const text = userInput.value.trim();
        if (!text) return;

        appendMessage('user', text);
        userInput.value = '';
        userInput.style.height = '45px';

        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'message bot-message loading-msg';
        loadingDiv.innerHTML = `
            <div class="avatar"><i class="fas fa-robot"></i></div>
            <div class="content"><div class="text-bubble"><i class="fas fa-ellipsis-h fa-beat"></i> 专家正在为您匹配优良品种...</div></div>
        `;
        chatWindow.appendChild(loadingDiv);
        chatWindow.scrollTop = chatWindow.scrollHeight;

        fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: text,
                location: currentUserLocation,
                is_voice: isVoice
            }),
            credentials: 'include'
        })
        .then(res => res.json())
        .then(data => {
            loadingDiv.remove();
            if (data.code === 200) {
                appendMessage('bot', data.reply, data.card_data);
            } else {
                appendMessage('bot', `服务繁忙：${data.msg}`);
            }
        })
        .catch(() => {
            loadingDiv.remove();
            appendMessage('bot', '网络连接似乎断开了，请检查网络设置。');
        });
    }

    // ==========================================
    // 6. 历史记录交互逻辑
    // ==========================================
    const toggleHistory = (show) => {
        if (show) {
            historySidebar.classList.add('active');
            sidebarOverlay.classList.add('active');
            loadHistory();
        } else {
            historySidebar.classList.remove('active');
            sidebarOverlay.classList.remove('active');
        }
    };

    if (openHistoryBtn) openHistoryBtn.addEventListener('click', () => toggleHistory(true));
    if (closeHistoryBtn) closeHistoryBtn.addEventListener('click', () => toggleHistory(false));
    if (sidebarOverlay) sidebarOverlay.addEventListener('click', () => toggleHistory(false));

    function loadHistory() {
        historyList.innerHTML = '<div style="text-align: center; color: #999; margin-top: 50px;"><i class="fas fa-spinner fa-spin"></i> 加载中...</div>';

        fetch('/api/chat/history', { credentials: 'include' })
            .then(res => res.json())
            .then(data => {
                if (data.code === 200) {
                    if (data.data.length === 0) {
                        historyList.innerHTML = '<div style="text-align: center; color: #999; margin-top: 50px;">暂无历史咨询记录</div>';
                        return;
                    }

                    historyList.innerHTML = '';
                    data.data.forEach(item => {
                        const div = document.createElement('div');
                        div.className = 'history-item';
                        div.innerHTML = `
                            <div class="h-query"><i class="fas fa-question-circle"></i> ${item.query}</div>
                            <div class="h-reply">${item.reply}</div>
                        `;
                        div.onclick = () => {
                            appendMessage('user', item.query);
                            appendMessage('bot', `(历史回溯) ${item.reply}`);
                            toggleHistory(false);
                        };
                        historyList.appendChild(div);
                    });
                } else {
                    historyList.innerHTML = `<div style="text-align: center; color: #d32f2f; margin-top: 50px;">加载失败：${data.msg}</div>`;
                }
            })
            .catch(() => {
                historyList.innerHTML = '<div style="text-align: center; color: #d32f2f; margin-top: 50px;">网络异常</div>';
            });
    }

    // ==========================================
    // 7. 【新增功能】导出用户咨询报告
    // ==========================================
    window.exportUserHistory = function() {
        const btn = event.currentTarget;
        const originalText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 正在生成...';

        fetch('/api/chat/history', { credentials: 'include' })
            .then(res => res.json())
            .then(data => {
                if (data.code === 200 && data.data.length > 0) {
                    let reportContent = `------------------------------------------\n`;
                    reportContent += `   农产品良种智能客服 - 咨询报告\n`;
                    reportContent += `   生成时间：${new Date().toLocaleString()}\n`;
                    reportContent += `------------------------------------------\n\n`;

                    data.data.reverse().forEach((item, index) => {
                        reportContent += `【问题 ${index + 1}】: ${item.query}\n`;
                        reportContent += `【专家建议】: ${item.reply.replace(/<br>/g, '\n')}\n`;
                        reportContent += `【咨询地区】: ${item.location || '自动定位'}\n`;
                        reportContent += `------------------------------------------\n`;
                    });

                    // 纯前端导出 Blob
                    const blob = new Blob([reportContent], { type: 'text/plain;charset=utf-8' });
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `农业专家咨询报告_${new Date().toLocaleDateString().replace(/\//g, '-')}.txt`;
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    document.body.removeChild(a);
                } else {
                    alert("暂无咨询记录可供导出");
                }
            })
            .catch(err => alert("导出报告失败，请稍后再试"))
            .finally(() => {
                btn.disabled = false;
                btn.innerHTML = originalText;
            });
    };

    // 事件绑定
    sendBtn.addEventListener('click', () => sendMessage(false));
    userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage(false);
        }
    });

    userInput.addEventListener('input', function() {
        this.style.height = 'auto';
        let newHeight = this.scrollHeight;
        this.style.height = (newHeight > 150 ? 150 : newHeight) + 'px';
    });

    initApp();
});