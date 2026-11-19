import { DEFAULT_CONFIG } from './config.js';

const $ = (s) => document.querySelector(s);
const msgs = $('#msgs'), chips = $('#chips'), input = $('#input'), composer = $('#composer');
const overlay = $('#overlay'), modalForm = $('#modalLeadForm');

let cfg = loadConfig();
applyBranding();

/* ---------- утилиты ---------- */
function loadConfig() {
  try {
    const saved = JSON.parse(localStorage.getItem('botcfg') || 'null');
    return saved && saved.companyName ? { ...DEFAULT_CONFIG, ...saved } : { ...DEFAULT_CONFIG };
  } catch { return { ...DEFAULT_CONFIG }; }
}
function applyBranding() {
  document.title = `${cfg.botName} — ИИ-бот для бизнеса`;
  $('#panelBotName').textContent = cfg.botName;
  $('#headBotName').textContent = cfg.botName;
  $('#panelTagline').textContent = cfg.tagline;
  $('#headCompany').textContent = cfg.companyName;
}
function getLeads() {
  try { return JSON.parse(localStorage.getItem('leads') || '[]'); } catch { return []; }
}
function saveLead(lead) {
  const leads = getLeads();
  leads.push({ ...lead, at: new Date().toISOString() });
  localStorage.setItem('leads', JSON.stringify(leads));
  renderLeadCount();
}
function renderLeadCount() {
  const n = getLeads().length;
  $('#leadCount').textContent = n ? `заявок: ${n}` : '';
}

/* ---------- доставка заявки владельцу ---------- */
async function deliverLead(lead) {
  if (!cfg.leadWebhook) return false; // демо-режим: заявка остаётся в браузере
  try {
    await fetch(cfg.leadWebhook, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...lead, company: cfg.companyName, bot: cfg.botName, page: location.href }),
    });
    return true;
  } catch {
    return false; // сеть/сервер недоступны — заявка не потеряется, она уже в localStorage
  }
}

/* ---------- рендер сообщений ---------- */
function addMsg(text, who = 'bot', extraHTML = '') {
  const div = document.createElement('div');
  div.className = `msg ${who}`;
  div.textContent = text;
  if (extraHTML) div.insertAdjacentHTML('beforeend', extraHTML);
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
  return div;
}
function showTyping() {
  const t = document.createElement('div');
  t.className = 'typing';
  t.innerHTML = '<i></i><i></i><i></i>';
  msgs.appendChild(t);
  msgs.scrollTop = msgs.scrollHeight;
  return t;
}
function setChips(list, withHome = true) {
  chips.innerHTML = '';
  const actions = withHome
    ? [...list, { label: 'Главное меню', act: showMainMenu }]
    : list;
  actions.forEach(({ label, act }) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'chip';
    b.textContent = label;
    b.addEventListener('click', () => { hideLeadForm(); act(); });
    chips.appendChild(b);
  });
}
function clearChips() { chips.innerHTML = ''; }

function mainMenuChips() {
  return [
    { label: 'Услуги и цены', act: () => botSay(rawAnswer('services')) },
    { label: 'Оставить заявку', act: openLeadForm },
    { label: 'График работы', act: () => botSay(rawAnswer('hours')) },
    { label: 'Контакты', act: () => botSay(rawAnswer('contacts')) },
  ];
}

function showMainMenu() {
  clearChips();
  hideLeadForm();
  botSay({
    text: 'Главное меню. Выберите, что хотите сделать:',
    chips: mainMenuChips(),
    main: true,
  });
}

/* ---------- динамические ответы ---------- */
function servicesHTML() {
  return cfg.services.map(s =>
    `<span class="svc"><b>${s.name}</b><span>${s.desc}</span><em>${s.price}</em></span>`
  ).join('');
}
function dynamicAnswer(kind) {
  switch (kind) {
    case 'greeting':
      return {
        text: `Здравствуйте! Я ${cfg.botName}, виртуальный консультант ${cfg.companyName}. Подскажу по услугам и ценам, помогу оставить заявку.`,
        chips: [
          { label: 'Услуги и цены', act: () => botSay(rawAnswer('services')) },
          { label: 'Оставить заявку', act: openLeadForm },
          { label: 'График работы', act: () => botSay(rawAnswer('hours')) },
        ],
      };
    case 'services':
      return {
        text: `Вот что мы предлагаем:`,
        html: servicesHTML(),
        chips: [
          { label: 'Оставить заявку', act: openLeadForm },
          { label: 'Задать вопрос', act: () => input.focus() },
        ],
      };
    case 'hours':
      return {
        text: `Наш график: ${cfg.workHours}. А я в чате круглосуточно — можете задать вопрос или оставить заявку прямо сейчас.`,
        chips: [{ label: 'Оставить заявку', act: openLeadForm }],
      };
    case 'contacts':
      return {
        text: `Мы находимся: ${cfg.address}.\nТелефон: ${cfg.phone}\nПочта: ${cfg.email}`,
        chips: [
          { label: 'Оставить заявку', act: openLeadForm },
          { label: 'График работы', act: () => botSay(rawAnswer('hours')) },
        ],
      };
    case 'human':
      return {
        text: `Конечно! Оставьте заявку — менеджер ${cfg.companyName} свяжется с вами в рабочее время (${cfg.workHours}).`,
        chips: [{ label: 'Оставить заявку', act: openLeadForm }],
      };
    case 'lead':
      return {
        text: `С удовольствием! Оставьте имя и телефон — менеджер перезвонит в рабочее время (${cfg.workHours}).`,
        form: true,
      };
  }
}
function rawAnswer(kind) {
  const r = dynamicAnswer(kind);
  return { text: r.text, html: r.html || '', chips: r.chips || [], form: !!r.form };
}

/* ---------- мозг бота ---------- */
function brain(userText) {
  const t = userText.toLowerCase().replace(/[.,!?«»"]/g, ' ');
  let best = null, bestScore = 0;
  for (const f of cfg.faq) {
    const keys = f.keys.split(',').map(k => k.trim().toLowerCase()).filter(Boolean);
    let score = 0;
    for (const k of keys) if (t.includes(k)) score += k.length; // длинные совпадения весомее
    if (score > bestScore) { bestScore = score; best = f; }
  }
  if (!best) {
    return {
      text: `Хороший вопрос! Точно отвечу за вас менеджер — оставьте заявку, перезвоним в рабочее время (${cfg.workHours}). А пока могу рассказать об услугах и ценах.`,
      chips: [
        { label: 'Услуги и цены', act: () => botSay(rawAnswer('services')) },
        { label: 'Оставить заявку', act: openLeadForm },
      ],
    };
  }
  if (best.dynamic) {
    const r = dynamicAnswer(best.dynamic);
    return { text: r.text, html: r.html || '', chips: r.chips || [], form: !!r.form };
  }
  return {
    text: best.answer,
    chips: [
      { label: 'Оставить заявку', act: openLeadForm },
      { label: 'Услуги и цены', act: () => botSay(rawAnswer('services')) },
    ],
  };
}

/* ---------- диалог ---------- */
function botSay({ text, html = '', chips: ch = [], form = false, main = false }) {
  const t = showTyping();
  setTimeout(() => {
    t.remove();
    addMsg(text, 'bot', html);
    if (form) openLeadForm();
    else setChips(ch, !main);
  }, 500 + Math.random() * 400);
}
function handleUser(text) {
  clearChips();
  hideLeadForm();
  botSay(brain(text));
}

/* ---------- форма заявки прямо в чате ---------- */
let formEl = null;
function openLeadForm() {
  clearChips();
  hideLeadForm();
  formEl = document.createElement('form');
  formEl.className = 'lead-form';
  formEl.innerHTML = `
    <h3>Заявка менеджеру</h3>
    <p>Оставьте контакты — перезвоним в рабочее время (${cfg.workHours}).</p>
    <label>Ваше имя<input name="name" type="text" placeholder="Иван" required></label>
    <label>Телефон<input name="phone" type="tel" placeholder="+7 (___) ___-__-__" required></label>
    <label>Вопрос<textarea name="question" rows="2" placeholder="Коротко о вашей задаче"></textarea></label>
    <div style="display:flex;gap:8px">
      <button type="submit" class="chip" style="background:var(--accent);color:var(--accent-ink);border-color:var(--accent)">Отправить</button>
      <button type="button" class="chip" data-cancel>Отмена</button>
    </div>`;
  msgs.appendChild(formEl);
  msgs.scrollTop = msgs.scrollHeight;
  formEl.querySelector('[data-cancel]').addEventListener('click', hideLeadForm);
  formEl.addEventListener('submit', (e) => {
    e.preventDefault();
    submitLead(new FormData(formEl), formEl);
  });
  formEl.querySelector('input[name=name]').focus();
}
function hideLeadForm() { if (formEl) { formEl.remove(); formEl = null; } }
function submitLead(fd, formNode) {
  const name = (fd.get('name') || '').toString().trim();
  const phone = (fd.get('phone') || '').toString().trim();
  const question = (fd.get('question') || '').toString().trim();
  let ok = true;
  const nameEl = formNode.querySelector('[name=name]');
  const phoneEl = formNode.querySelector('[name=phone]');
  nameEl.classList.toggle('err', !name); if (!name) ok = false;
  const phoneOk = /^[+\d][\d\s()\-]{9,}$/.test(phone);
  phoneEl.classList.toggle('err', !phoneOk); if (!phoneOk) ok = false;
  if (!ok) return;
  saveLead({ name, phone, question });
  const delivered = deliverLead({ name, phone, question });
  const t = showTyping();
  setTimeout(async () => {
    t.remove();
    if (formNode.parentElement === msgs) formNode.remove();
    if (formNode === formEl) formEl = null;
    const ok = await delivered;
    addMsg(ok
      ? `Спасибо, ${name}! Заявка отправлена менеджеру — свяжемся с вами в ближайшее рабочее время.`
      : `Спасибо, ${name}! Заявка сохранена. Менеджер ${cfg.companyName} свяжется с вами в ближайшее рабочее время.`, 'bot');
    setChips([{ label: 'Услуги и цены', act: () => botSay(rawAnswer('services')) }]);
  }, 600);
  if (overlay && !overlay.hidden) overlay.hidden = true;
}

/* ---------- модальное окно (клик по счётчику заявок) ---------- */
$('#leadCount').style.cursor = 'pointer';
$('#leadCount').addEventListener('click', () => { overlay.hidden = false; modalForm.querySelector('[name=name]').focus(); });
$('#closeModal').addEventListener('click', () => { overlay.hidden = true; });
overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.hidden = true; });
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') overlay.hidden = true; });
modalForm.addEventListener('submit', (e) => {
  e.preventDefault();
  submitLead(new FormData(modalForm), modalForm);
  modalForm.reset();
});

/* ---------- запуск ---------- */
composer.addEventListener('submit', (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  addMsg(text, 'user');
  input.value = '';
  handleUser(text);
});
$('#mainMenuButton').addEventListener('click', showMainMenu);

renderLeadCount();
botSay({
  text: `Здравствуйте! Я ${cfg.botName}, виртуальный консультант ${cfg.companyName}. Расскажу об услугах и ценах, отвечу на вопросы и приму заявку. Чем помочь?`,
  chips: mainMenuChips(),
  main: true,
});
