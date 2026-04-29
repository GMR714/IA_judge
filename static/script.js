/* =======================================================
   Ipe City DAO — Governance Dashboard Script
   ======================================================= */

// --- DOM References ---
const feed           = document.getElementById('chat-box');
const btnRun         = document.getElementById('btn-run');
const btnDebug       = document.getElementById('btn-debug');
const proposalList   = document.getElementById('proposal-list');
const proposalCount  = document.getElementById('proposal-count');
const headerStatus   = document.getElementById('header-status');
const statusDot      = document.getElementById('status-dot');
const typingIndicator= document.getElementById('typing-indicator');
const typingName     = document.getElementById('typing-name');
const idleText       = document.getElementById('idle-text');
const tabTournament  = document.getElementById('tab-tournament');
const tabGraph       = document.getElementById('tab-graph');

let currentMode = 'tournament';

// --- MetaMask / Ethers.js Integration ---
let walletProvider = null;
let walletSigner = null;
let walletAddress = null;
let vaultContract = null;
let contractConfig = null;

function disconnectMetaMask() {
    walletProvider = null;
    walletSigner = null;
    walletAddress = null;
    const btn = document.getElementById('btn-metamask');
    btn.innerHTML = `<span>🦊</span> Conectar MetaMask`;
    btn.classList.remove('connected');
}

async function connectMetaMask() {
    const btn = document.getElementById('btn-metamask');
    
    if (walletAddress) {
        disconnectMetaMask();
        return;
    }

    if (!window.ethereum) {
        alert('MetaMask nao encontrada! Instale a extensao.');
        return;
    }
    try {
        await window.ethereum.request({
            method: 'wallet_requestPermissions',
            params: [{ eth_accounts: {} }]
        });
        const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
        walletProvider = new ethers.BrowserProvider(window.ethereum);
        walletSigner = await walletProvider.getSigner();
        walletAddress = accounts[0];
        
        const short = walletAddress.slice(0, 6) + '...' + walletAddress.slice(-4);
        btn.innerHTML = `<span>🦊</span> ${short}`;
        btn.title = "Clique para desconectar";
        btn.classList.add('connected');
        
        await loadContract();
        
        const network = await walletProvider.getNetwork();
        if (Number(network.chainId) !== 11155111) {
            try {
                await window.ethereum.request({
                    method: 'wallet_switchEthereumChain',
                    params: [{ chainId: '0xaa36a7' }]
                });
            } catch (e) {}
        }
    } catch (err) {
        console.error('Erro ao conectar MetaMask:', err);
    }
}

async function loadContract() {
    if (contractConfig) return;
    try {
        const res = await fetch('/contract-config');
        contractConfig = await res.json();
    } catch (e) {}
}

async function approveAndClaim(proposalId, btn) {
    if (!walletSigner || !contractConfig) {
        alert('Conecte sua MetaMask primeiro!');
        return;
    }
    
    btn.disabled = true;
    btn.textContent = 'Assinando via MetaMask...';
    
    try {
        const contract = new ethers.Contract(contractConfig.address, contractConfig.abi, walletSigner);
        
        btn.textContent = '1/2 Assinando approveGrant...';
        const txApprove = await contract.approveGrant(proposalId);
        btn.textContent = '1/2 Aguardando confirmacao...';
        await txApprove.wait();
        
        btn.textContent = '2/2 Executando claim...';
        try {
            const txClaim = await contract.claim(proposalId);
            btn.textContent = '2/2 Aguardando confirmacao...';
            await txClaim.wait();
            btn.textContent = 'Aprovado e Pago!';
            btn.classList.add('success');
        } catch (claimErr) {
            const errMsg = claimErr.reason || claimErr.message || '';
            if (errMsg.includes('Faltam assinaturas')) {
                btn.textContent = 'Assinado! (Troque a carteira e assine novamente)';
                btn.classList.add('success');
                btn.disabled = false;
            } else {
                btn.textContent = 'Assinado! Claim falhou.';
                btn.classList.add('success');
                btn.disabled = false;
            }
        }
    } catch (err) {
        btn.textContent = 'Erro ou rejeitado';
        btn.disabled = false;
    }
}

// Auto-connect se MetaMask ja estava conectada
if (window.ethereum) {
    if (window.ethereum.selectedAddress) {
        connectMetaMask();
    }
    window.ethereum.on('accountsChanged', (accounts) => {
        if (accounts.length > 0) {
            walletAddress = null;
            connectMetaMask();
        } else {
            disconnectMetaMask();
        }
    });
}

// --- Agent Avatar / Color Maps ---
const AVATARS = {
    "Auditor de Projeto":      "static/auditor.png",
    "Auditor Técnico":         "static/auditor.png",
    "Embaixador Comunitário":  "static/community.png",
    "Avaliador de Perfil":     "static/finance.png",
    "Analista Financeiro":     "static/finance.png",
    "Juiz de Competição":      "static/judge.png",
    "Cofre Ipe City":          "static/judge.png",
    "Sistema":                 "static/judge.png"
};

const COLORS = {
    "Auditor de Projeto":      "color-auditor",
    "Auditor Técnico":         "color-auditor",
    "Embaixador Comunitário":  "color-community",
    "Avaliador de Perfil":     "color-finance",
    "Analista Financeiro":     "color-finance",
    "Juiz de Competição":      "color-judge",
    "Cofre Ipe City":          "color-system",
    "Sistema":                 "color-system"
};

// --- Proposal Data ---
const mockProposals = [
    {
        proposal_id: "IPE_001_XMTP",
        proposal_text: `Track: Ipê City | Categoria: Connect\nNome: VillageComm — Mensageria Privada com XMTP\nDescrição: Protocolo de comunicação wallet-native entre residentes do Ipê Village, organizações parceiras e visitantes. Utiliza XMTP para garantir que nenhuma mensagem passe por servidor centralizado — cada conversa é criptografada e assinada on-chain. Inclui módulo de notificações para eventos, emergências e atualizações do cofre de governança.\nStack: XMTP, Push Protocol, Ethereum (Base L2).\nGrant solicitado: 2.500 USD em tokens IPE.`,
        recipient_wallet_address: "0x5FbDB2315678afecb367f032d93F642f64180aa3",
        grant_amount: 2500
    },
    {
        proposal_id: "VRT_002_HOA",
        proposal_text: `Track: Veritas Village | Categoria: Governance\nNome: VeritasDAO — HOA Voting & Dues Collection\nDescrição: Sistema completo de gestão do condomínio Veritas Village via blockchain. Moradores submetem pautas, votam propostas de melhoria (quadras, piscina, regras de uso) e pagam a taxa de condomínio via Bitcoin sidechain (Stacks). Transparência total: todo pagamento e resultado de votação fica registrado na chain. Integra com o Ipê Passport para autenticação de quórum.\nStack: Stacks (Bitcoin L2), Clarity smart contracts, Snapshot off-chain signaling.\nGrant solicitado: 2.500 USD em tokens IPE.`,
        recipient_wallet_address: "0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
        grant_amount: 2500
    },
    {
        proposal_id: "IPE_003_ZKDOOR",
        proposal_text: `Track: Ipê City | Categoria: Safety\nNome: ZK-Door — Controle de Acesso Físico via Carteira Cripto\nDescrição: Sistema de acesso keyless para todos os portões e espaços comuns do Village. Nenhum app, nenhum PIN, nenhum cartão RFID — apenas a assinatura da sua wallet Ethereum. ZK-proofs garantem que o sistema verifique sua identidade sem revelar sua chave pública completa. Suporte a acesso temporário para visitantes via NFT de convite com expiração on-chain.\nStack: Ethereum/Base, ZK-proofs (Circom), hardware IoT (ESP32 + HSM).\nGrant solicitado: 2.500 USD em tokens IPE.`,
        recipient_wallet_address: "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC",
        grant_amount: 2500
    }
];

const mockSingleProposal = [{
    proposal_id: "VRT_DELIB_002_BIO",
    proposal_text: `Track: Veritas Village | Categoria: Security & Infrastructure\nNome: SafeFace — Reconhecimento Facial Centralizado AWS\nDescrição: Sistema de controle de acesso biométrico para as áreas comuns do Veritas Village e do Ipê Village. Instalaremos câmeras de reconhecimento facial nas portas. As biometrias dos moradores e visitantes serão armazenadas anonimamente em um banco de dados AWS RDS. Não usaremos blockchain para guardar os rostos por questões de custo de armezamento on-chain, mas faremos o registro de um hash diário de auditoria na rede Base. Promete muita segurança e tolerância zero a intrusos.\nModelo de sustentabilidade: Cobrança de assinatura SaaS anual da Administração.\nStack: AWS Rekognition, Node, React, Base L2 (apenas para hash audit).\nGrant solicitado: 2.500 USD em tokens IPE.`,
    recipient_wallet_address: "0x5FbDB2315678afecb367f032d93F642f64180aa3",
    grant_amount: 2500
}];

const globalDebugWallet = "0x2f2A9fF7079B0BdaFFEb385f17629c4793276CB3";
mockProposals.forEach(p => p.recipient_wallet_address = globalDebugWallet);
mockSingleProposal.forEach(p => p.recipient_wallet_address = globalDebugWallet);

const PROPOSAL_INFO = {};
[...mockProposals, ...mockSingleProposal].forEach(p => {
    PROPOSAL_INFO[p.proposal_id] = p.proposal_text;
});

// --- Render Proposal Cards ---
function populateProposals() {
    proposalList.innerHTML = '';
    const items = currentMode === 'tournament' ? mockProposals : mockSingleProposal;
    proposalCount.textContent = items.length;

    items.forEach((p, i) => {
        const card = document.createElement('div');
        card.className = 'proposal-card';
        card.id = `card-${p.proposal_id}`;
        card.style.animationDelay = `${i * 0.07}s`;

        const shortWallet = p.recipient_wallet_address.slice(0, 8) + '...' + p.recipient_wallet_address.slice(-6);
        const isVeritas = p.proposal_text.includes('Veritas Village');
        const trackLabel = isVeritas ? '🌿 Veritas' : '🌳 Ipê City';
        const trackClass = isVeritas ? 'track-veritas' : 'track-ipe';
        const catMatch = p.proposal_text.match(/Categoria:\s*([^\n]+)/);
        const category = catMatch ? catMatch[1].trim() : '';
        const nameMatch = p.proposal_text.match(/Nome:\s*([^\n]+)/);
        const displayName = nameMatch ? nameMatch[1].trim() : p.proposal_id;
        const descMatch = p.proposal_text.match(/Descrição:\s*([^\n]+)/);
        const shortDesc = descMatch ? descMatch[1].trim().substring(0, 110) + '…' : p.proposal_text.substring(0, 110) + '…';

        card.innerHTML = `
            <div class="proposal-card-header">
                <span class="proposal-id">${p.proposal_id}</span>
                <span class="proposal-amount">💰 $${p.grant_amount.toLocaleString()}</span>
            </div>
            <div class="proposal-card-meta">
                <span class="track-badge ${trackClass}">${trackLabel}</span>
                ${category ? `<span class="category-badge">${category}</span>` : ''}
            </div>
            <p class="proposal-name">${displayName}</p>
            <p class="proposal-text">${shortDesc}</p>
            <div class="proposal-wallet" title="${p.recipient_wallet_address}">📬 ${shortWallet}</div>
        `;
        proposalList.appendChild(card);
    });
}
populateProposals();

function markProposalResult(proposalId, type) {
    const card = document.getElementById(`card-${proposalId}`);
    if (!card) return;
    const old = card.querySelector('.proposal-result-badge');
    if (old) old.remove();

    const badge = document.createElement('div');
    badge.className = `proposal-result-badge ${type}`;
    if (type === 'winner') {
        badge.innerHTML = '🏆 Vencedor';
        card.style.borderColor = 'rgba(245, 158, 11, 0.4)';
    } else {
        badge.innerHTML = '⛔ Rejeitado';
        card.style.borderColor = 'rgba(239, 68, 68, 0.25)';
    }
    card.appendChild(badge);
}

// --- Mode Tabs ---
tabTournament.addEventListener('click', () => {
    if (currentMode === 'tournament') return;
    currentMode = 'tournament';
    tabTournament.classList.add('active');
    tabGraph.classList.remove('active');
    tabNew.classList.remove('active');
    proposalList.style.display = 'flex';
    newProposalForm.style.display = 'none';
    document.getElementById('panel-footer-controls').style.display = 'flex';
    populateProposals();
});

tabGraph.addEventListener('click', () => {
    if (currentMode === 'graph') return;
    currentMode = 'graph';
    tabGraph.classList.add('active');
    tabTournament.classList.remove('active');
    tabNew.classList.remove('active');
    proposalList.style.display = 'flex';
    newProposalForm.style.display = 'none';
    document.getElementById('panel-footer-controls').style.display = 'flex';
    populateProposals();
});

const tabNew = document.getElementById('tab-new');
const newProposalForm = document.getElementById('new-proposal-form');

tabNew.addEventListener('click', () => {
    currentMode = 'custom';
    tabNew.classList.add('active');
    tabTournament.classList.remove('active');
    tabGraph.classList.remove('active');
    proposalList.style.display = 'none';
    newProposalForm.style.display = 'flex';
    document.getElementById('panel-footer-controls').style.display = 'none';
});

// --- Utilities ---
function formatTime() {
    return new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
}

function parseMessage(msg) {
    const scoreRegex = /Nota para ([A-Z0-9_]+):\s*([\d.]+)\.\s*(?:Feedback:\s*)?(.*)/is;
    const m = msg.match(scoreRegex);
    if (m) {
        return {
            proposalId: m[1].trim(),
            score:      parseFloat(m[2]),
            feedback:   m[3].trim()
        };
    }
    return null;
}

function scoreClass(s) {
    if (s >= 7) return 'score-high';
    if (s >= 4) return 'score-mid';
    return 'score-low';
}

function setStatus(text, active = false) {
    headerStatus.textContent = text;
    statusDot.classList.toggle('active', active);
}

function showTyping(name) {
    idleText.style.display = 'none';
    typingIndicator.style.display = 'flex';
    typingName.textContent = name;
    setStatus(`${name} analisando...`, true);
}

function hideTyping() {
    typingIndicator.style.display = 'none';
    idleText.style.display = '';
}

// --- Feed Message Functions ---
function addMessage(sender, message, type = "chat") {
    const empty = feed.querySelector('.feed-empty');
    if (empty) empty.remove();

    if (type === "info") {
        const sysDiv = document.createElement('div');
        sysDiv.className = 'system-message round-sep';
        sysDiv.textContent = message;
        feed.appendChild(sysDiv);
        feed.scrollTop = feed.scrollHeight;
        return;
    }

    const row = document.createElement('div');
    row.className = `message-row ${sender === "Cofre Ipe City" ? "out" : "in"}`;

    let avatarHtml = '';
    if (sender !== "Cofre Ipe City") {
        const src = AVATARS[sender] || "static/judge.png";
        avatarHtml = `<img src="${src}" class="message-avatar-img" alt="${sender}">`;
    }

    const colorClass = COLORS[sender] || "color-system";
    let bubbleHtml = `<div class="bubble">`;

    if (sender) {
        bubbleHtml += `<span class="sender-name ${colorClass}">${sender}</span>`;
    }

    const parsed = parseMessage(message);
    if (parsed) {
        const shortText = PROPOSAL_INFO[parsed.proposalId] || parsed.proposalId;
        bubbleHtml += `
            <div class="proposal-tag">📍 ${parsed.proposalId} — ${shortText.substring(0, 50)}…</div>
            <div class="score-row">
                <span class="score-badge ${scoreClass(parsed.score)}">${parsed.score}/10</span>
                <span class="score-label">${parsed.score >= 7 ? 'Viável ✅' : parsed.score >= 4 ? 'Atenção ⚠️' : 'Risco Alto ❌'}</span>
            </div>
            <div class="bubble-text">${marked.parse(parsed.feedback)}</div>
        `;
    } else {
        bubbleHtml += `<div class="bubble-text">${marked.parse(message)}</div>`;
    }

    bubbleHtml += `<span class="timestamp">${formatTime()}</span></div>`;
    row.innerHTML = avatarHtml + bubbleHtml;

    feed.appendChild(row);
    feed.scrollTop = feed.scrollHeight;
}

function addWinnerCard(message) {
    const empty = feed.querySelector('.feed-empty');
    if (empty) empty.remove();

    const row = document.createElement('div');
    row.className = 'message-row in';

    // Rejected?
    if (message.includes("PROPOSTA REJEITADA") || message.includes("NENHUM VENCEDOR")) {
        const reason = message.replace(/PROPOSTA REJEITADA\.?\s*MOTIVO:\s*|NENHUM VENCEDOR ESCOLHIDO\.?\s*MOTIVO:\s*/is, "");

        // Try to find which proposal was rejected from context (only applies to single graph mode)
        const propMatch = message.match(/([A-Z0-9_]{5,})/);
        if (propMatch) markProposalResult(propMatch[1], 'rejected');

        row.innerHTML = `
            <img src="${AVATARS['Juiz de Competição']}" class="message-avatar-img" alt="Juiz">
            <div class="bubble" style="max-width: 90%;">
                <span class="sender-name color-judge">Juiz de Competição</span>
                <div class="winner-card" style="border-color: rgba(239,68,68,0.4); background: linear-gradient(135deg, rgba(239,68,68,0.07) 0%, rgba(23,32,48,0.9) 100%);">
                    <div class="winner-card-header">
                        <div class="winner-card-emoji">⛔</div>
                        <div class="winner-card-title rejected">Veredito: Rejeitado</div>
                    </div>
                    <div class="winner-card-reason">${marked.parse(reason)}</div>
                </div>
                <span class="timestamp">${formatTime()}</span>
            </div>
        `;
        feed.appendChild(row);
        feed.scrollTop = feed.scrollHeight;
        return;
    }

    // Winner
    const m = message.match(/VENCEDOR ESCOLHIDO:\s*([A-Z0-9_]+)\.\s*MOTIVO:\s*([\s\S]*)/is);
    const winnerId = m ? m[1] : 'Decisão do Conselho';
    const reason   = m ? m[2] : message;

    if (m) markProposalResult(winnerId, 'winner');

    row.innerHTML = `
        <img src="${AVATARS['Juiz de Competição']}" class="message-avatar-img" alt="Juiz">
        <div class="bubble" style="max-width: 90%;">
            <span class="sender-name color-judge">Juiz de Competição</span>
            <div class="winner-card">
                <div class="winner-card-header">
                    <div class="winner-card-emoji">🏆</div>
                    <div class="winner-card-title">Veredito: Aprovado (${winnerId})</div>
                </div>
                <div class="winner-card-reason">${marked.parse(reason)}</div>
            </div>
            <span class="timestamp">${formatTime()}</span>
        </div>
    `;
    feed.appendChild(row);
    feed.scrollTop = feed.scrollHeight;
}

function addTxCard(message, proposalOnchainId) {
    const empty = feed.querySelector('.feed-empty');
    if (empty) empty.remove();

    const hashMatch = message.match(/(0x[a-fA-F0-9]{40,})/);
    const hash = hashMatch ? hashMatch[1] : message;

    const row = document.createElement('div');
    row.className = 'message-row out';
    
    let approveHtml = '';
    if (proposalOnchainId !== null && proposalOnchainId !== undefined) {
        approveHtml = `
            <button class="btn-approve-onchain" onclick="approveAndClaim(${proposalOnchainId}, this)">
                🦊 Assinar & Resgatar (Proposta #${proposalOnchainId})
            </button>
        `;
    }
    
    row.innerHTML = `
        <div class="bubble">
            <div class="tx-card">
                <div class="tx-label">Proposta Submetida no Cofre On-Chain</div>
                <div class="tx-hash">${hash}</div>
                ${approveHtml}
            </div>
            <span class="timestamp">${formatTime()}</span>
        </div>
    `;
    feed.appendChild(row);
    feed.scrollTop = feed.scrollHeight;
}

// --- Main Event: Run Debate ---
if (btnDebug) {
    btnDebug.addEventListener('click', () => {
        window.isDebugAction = true;
        btnRun.click();
    });
}
btnRun.addEventListener('click', async () => {
    feed.innerHTML = '';
    document.querySelectorAll('.proposal-card').forEach(card => {
        card.style.borderColor = '';
        const badge = card.querySelector('.proposal-result-badge');
        if (badge) badge.remove();
    });

    const startDiv = document.createElement('div');
    startDiv.className = 'system-message';
    startDiv.textContent = `🚀 Debate iniciado — ${formatTime()}`;
    feed.appendChild(startDiv);

    btnRun.disabled = true;
    btnRun.querySelector('.btn-label').textContent = 'DEBATE EM CURSO...';
    btnRun.querySelector('.btn-icon').textContent = '⏳';

    const endpoint = currentMode === 'tournament' ? '/run-tournament' : '/run-graph';
    let payload  = currentMode === 'tournament' ? mockProposals : mockSingleProposal;
    if (window.isDebugAction && currentMode === 'tournament') {
        payload = payload.slice(0, 2);
        window.isDebugAction = false;
    }

    try {
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ proposals: payload })
        });

        const reader  = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop();

            for (const line of lines) {
                const trimmed = line.trim();
                if (!trimmed.startsWith('data: ')) continue;
                try {
                    const data = JSON.parse(trimmed.slice(6));

                    if (data.type === 'done') {
                        hideTyping();
                        setStatus('Sessão encerrada', false);
                        btnRun.disabled = false;
                        btnRun.querySelector('.btn-label').textContent = 'NOVO DEBATE';
                        btnRun.querySelector('.btn-icon').textContent = '↺';

                        const endDiv = document.createElement('div');
                        endDiv.className = 'system-message';
                        endDiv.textContent = `🏁 Debate encerrado — ${formatTime()}`;
                        feed.appendChild(endDiv);
                        feed.scrollTop = feed.scrollHeight;
                        continue;
                    }

                    if (data.type === 'info') {
                        showTyping(data.sender);
                        addMessage(data.sender, data.message || `[${data.sender} está processando]`, 'info');
                    } else if (data.type === 'chat') {
                        hideTyping();
                        if (data.sender === 'Juiz de Competição') {
                            addWinnerCard(data.message);
                        } else {
                            addMessage(data.sender, data.message, data.type);
                        }
                    } else if (data.type === 'success') {
                        hideTyping();
                        addTxCard(data.message, data.proposal_onchain_id);
                    } else if (data.type === 'error') {
                        hideTyping();
                        addMessage('Sistema', `⚠️ ${data.message}`, 'chat');
                    }
                } catch (e) {}
            }
        }
    } catch (err) {
        hideTyping();
        setStatus('Erro de conexão', false);
        const errDiv = document.createElement('div');
        errDiv.className = 'system-message';
        errDiv.textContent = '⚠️ Não foi possível conectar ao servidor.';
        feed.appendChild(errDiv);
        feed.scrollTop = feed.scrollHeight;

        btnRun.disabled = false;
        btnRun.querySelector('.btn-label').textContent = 'TENTAR NOVAMENTE';
        btnRun.querySelector('.btn-icon').textContent = '▶';
    }
});

// --- New Form Submit Logic ---
const npSubmit = document.getElementById('np-submit');
npSubmit.addEventListener('click', async () => {
    const id = document.getElementById('np-id').value || "IPE_CUSTOM";
    const amount = document.getElementById('np-amount').value || "2500";
    const text = document.getElementById('np-text').value;
    const github = document.getElementById('np-github').value || "";
    const intent = document.getElementById('np-intent').value || "";

    if (!text && !github && !intent) {
        alert("Preencha a descrição da proposta, GitHub ou intenção!");
        return;
    }

    const payload = {
        proposals: [{
            proposal_id: id,
            proposal_text: text,
            recipient_wallet_address: globalDebugWallet,
            grant_amount: parseInt(amount),
            github_url: github,
            intent: intent
        }]
    };

    feed.innerHTML = '';
    setStatus("Processando Nova Proposta...", true);
    
    const url = '/run-graph';
    const req = {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    };

    try {
        const response = await fetch(url, req);
        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            
            const lines = buffer.split('\n');
            buffer = lines.pop();

            for (let line of lines) {
                const trimmed = line.trim();
                if (!trimmed.startsWith('data: ')) continue;
                try {
                    const data = JSON.parse(trimmed.slice(6));
                    if (data.type === 'done') {
                        setStatus("Concluído", false);
                    } else {
                        if (data.sender === 'Juiz de Competição') {
                            addWinnerCard(data.message);
                        } else if (data.message.includes('0x')) {
                            addTxCard(data.message, data.sender);
                        } else {
                            addMessage(data.sender, data.message, data.type);
                        }
                    }
                } catch (e) {}
            }
        }
    } catch (e) {
        addMessage("Sistema", "Erro na requisição: " + e.message, "error");
    }
});