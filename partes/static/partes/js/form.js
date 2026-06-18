const form = document.querySelector('#parte-form');
const statusBox = document.querySelector('#status');
const passwordToggle = document.querySelector('.password-toggle');
const photoPanel = document.querySelector('#photo-panel');
const photoPreview = document.querySelector('#photo-preview');
const STORAGE_KEY = 'jListoyaParteProfilesV4';
const DRAFT_KEY = 'jListoyaParteDraftsV1';
const PROFILE_FIELDS = [
  'add_photos', 'hora_llegada', 'hora_salida', 'jornada', 'companero', 'matricula', 'conductor',
  'entrada_obra', 'salida_obra', 'hora_comida', 'gastos', 'proyecto_id', 'trabajos', 'admin', 'materiales',
];
const DRAFT_FIELDS = ['tecnico', 'fecha', ...PROFILE_FIELDS];
const EMPTY_PROFILE = {
  add_photos: false,
  hora_llegada: '',
  hora_salida: '',
  jornada: 'normal',
  companero: '',
  matricula: '',
  conductor: false,
  entrada_obra: '',
  salida_obra: '',
  hora_comida: '',
  gastos: '',
  proyecto_id: '',
  trabajos: '',
  admin: '',
  materiales: '',
};
let obraMap = {};
let serverProfiles = {};
let currentTecnico = '';
let isApplyingState = false;
let draftTimer = 0;

function getCookie(name) {
  return document.cookie.split(';').map(v => v.trim()).find(v => v.startsWith(`${name}=`))?.split('=')[1] || '';
}

function todayIso() {
  const now = new Date();
  const offset = now.getTimezoneOffset();
  return new Date(now.getTime() - offset * 60000).toISOString().slice(0, 10);
}

function addOption(select, value, label = value) {
  const option = document.createElement('option');
  option.value = value;
  option.textContent = label;
  select.appendChild(option);
}

function fillSelect(select, values, placeholder) {
  select.innerHTML = '';
  addOption(select, '', placeholder);
  values.forEach(value => addOption(select, value));
}

function normalizeTimeInput(input) {
  if (!input.value) return;
  const [hours, minutes] = input.value.split(':').map(Number);
  const rounded = Math.round(minutes / 15) * 15;
  const date = new Date(2000, 0, 1, hours, rounded);
  input.value = `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
}

function readStore() {
  try {
    const store = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    return {lastTecnico: store.lastTecnico || '', profiles: store.profiles || {}};
  } catch {
    return {lastTecnico: '', profiles: {}};
  }
}

function writeStore(store) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify({
    lastTecnico: store.lastTecnico || '',
    profiles: store.profiles || {},
  }));
}

function readDraftStore() {
  try {
    const store = JSON.parse(localStorage.getItem(DRAFT_KEY) || '{}');
    return {lastTecnico: store.lastTecnico || '', drafts: store.drafts || {}};
  } catch {
    return {lastTecnico: '', drafts: {}};
  }
}

function writeDraftStore(store) {
  localStorage.setItem(DRAFT_KEY, JSON.stringify({
    lastTecnico: store.lastTecnico || '',
    drafts: store.drafts || {},
  }));
}

function fieldExists(name, value) {
  const field = form.elements[name];
  if (!field) return false;
  if (field.tagName !== 'SELECT') return true;
  return [...field.options].some(option => option.value === value);
}

function applyProfile(tecnico) {
  isApplyingState = true;
  const store = readStore();
  const draftStore = readDraftStore();
  const profile = {
    ...EMPTY_PROFILE,
    ...(serverProfiles[tecnico] || {}),
    ...(store.profiles[tecnico] || {}),
    ...(draftStore.drafts[tecnico] || {}),
  };
  PROFILE_FIELDS.forEach(name => {
    const field = form.elements[name];
    if (!field || !fieldExists(name, profile[name])) return;
    if (field.type === 'checkbox') {
      field.checked = Boolean(profile[name]);
    } else {
      field.value = profile[name] ?? '';
    }
  });
  if (profile.fecha) form.elements.fecha.value = profile.fecha;
  syncFridayJornada();
  syncJornada();
  syncProyecto();
  syncPhotoPanel();
  isApplyingState = false;
}

function collectProfile() {
  const profile = {};
  PROFILE_FIELDS.forEach(name => {
    const field = form.elements[name];
    if (!field) return;
    profile[name] = field.type === 'checkbox' ? field.checked : field.value;
  });
  return profile;
}

function collectDraft() {
  const draft = {};
  DRAFT_FIELDS.forEach(name => {
    const field = form.elements[name];
    if (!field) return;
    if (field.type === 'file') return;
    draft[name] = field.type === 'checkbox' ? field.checked : field.value;
  });
  return draft;
}

function saveProfile(tecnico = form.elements.tecnico.value) {
  if (!tecnico) return;
  saveSubmittedProfile(tecnico, collectProfile());
}

function saveSubmittedProfile(tecnico, profile) {
  if (!tecnico) return;
  const store = readStore();
  store.lastTecnico = tecnico;
  store.profiles[tecnico] = profile;
  writeStore(store);
}

function saveDraftNow(tecnico = form.elements.tecnico.value) {
  if (!tecnico || isApplyingState) return;
  const store = readDraftStore();
  store.lastTecnico = tecnico;
  store.drafts[tecnico] = collectDraft();
  writeDraftStore(store);
}

function scheduleDraftSave() {
  if (isApplyingState) return;
  clearTimeout(draftTimer);
  draftTimer = window.setTimeout(() => saveDraftNow(), 180);
}

function clearDraft(tecnico) {
  if (!tecnico) return;
  const store = readDraftStore();
  delete store.drafts[tecnico];
  if (store.lastTecnico === tecnico) store.lastTecnico = '';
  writeDraftStore(store);
}

function restoreLastTecnico() {
  const store = readStore();
  const draftStore = readDraftStore();
  const select = form.elements.tecnico;
  const tecnico = draftStore.lastTecnico || store.lastTecnico;
  if (tecnico && fieldExists('tecnico', tecnico)) {
    select.value = tecnico;
    currentTecnico = tecnico;
    applyProfile(currentTecnico);
  }
}

function rememberLastTecnico(tecnico) {
  const store = readStore();
  store.lastTecnico = tecnico || '';
  writeStore(store);
}

function switchTecnico(nextTecnico) {
  saveDraftNow(currentTecnico);
  currentTecnico = nextTecnico || '';
  rememberLastTecnico(currentTecnico);
  if (currentTecnico) {
    applyProfile(currentTecnico);
  } else {
    applyProfile('');
  }
}

function syncPhotoPanel() {
  const enabled = form.elements.add_photos?.checked;
  if (!photoPanel) return;
  photoPanel.hidden = !enabled;
  if (!enabled) {
    form.elements.photos.value = '';
    renderPhotoPreview();
  }
}

function renderPhotoPreview() {
  if (!photoPreview) return;
  photoPreview.innerHTML = '';
  const files = [...(form.elements.photos?.files || [])];
  files.forEach(file => {
    const item = document.createElement('div');
    item.className = 'photo-thumb';
    const img = document.createElement('img');
    img.src = URL.createObjectURL(file);
    img.alt = file.name;
    img.onload = () => URL.revokeObjectURL(img.src);
    const caption = document.createElement('span');
    caption.textContent = file.name;
    item.append(img, caption);
    photoPreview.appendChild(item);
  });
}

function syncFridayJornada() {
  const fecha = form.elements.fecha.value;
  if (!fecha) return;
  const weekday = new Date(`${fecha}T12:00:00`).getDay();
  if (weekday === 5) form.elements.jornada.value = 'intensiva';
  syncJornada();
}

function syncJornada() {
  const intensiva = form.elements.jornada.value === 'intensiva';
  form.elements.hora_comida.disabled = intensiva;
  form.elements.gastos.disabled = intensiva;
  if (intensiva) {
    form.elements.hora_comida.value = '';
    form.elements.gastos.value = '0';
  }
}

function syncProyecto() {
  const item = obraMap[form.elements.proyecto_id.value] || {cliente: '', obra: ''};
  form.elements.cliente.value = item.cliente;
  form.elements.obra.value = item.obra;
}

function setStatus(type, html) {
  statusBox.className = `status ${type}`;
  statusBox.innerHTML = html;
}

function initPasswordToggle() {
  if (!passwordToggle) return;
  passwordToggle.addEventListener('click', () => {
    const input = form.elements.password;
    const visible = input.type === 'text';
    input.type = visible ? 'password' : 'text';
    passwordToggle.setAttribute('aria-label', visible ? 'Mostrar contraseña' : 'Ocultar contraseña');
    passwordToggle.setAttribute('title', visible ? 'Mostrar contraseña' : 'Ocultar contraseña');
  });
}

async function init() {
  form.elements.fecha.value = todayIso();
  const response = await fetch('/api/init-data/');
  const data = await response.json();
  obraMap = data.obraMap || {};
  serverProfiles = data.profileMap || {};
  fillSelect(form.elements.tecnico, data.tecnicos || [], 'Selecciona técnico');
  fillSelect(form.elements.companero, data.companeros || [], '— Selecciona —');
  fillSelect(form.elements.matricula, data.vehiculos || [], 'Sin matrícula');
  fillSelect(form.elements.proyecto_id, data.ids || [], 'Selecciona proyecto');
  restoreLastTecnico();
  syncFridayJornada();
  syncProyecto();
}

form.querySelectorAll('input[type="time"]').forEach(input => {
  input.addEventListener('change', () => normalizeTimeInput(input));
});
form.elements.fecha.addEventListener('change', syncFridayJornada);
form.elements.jornada.addEventListener('change', syncJornada);
form.elements.proyecto_id.addEventListener('change', syncProyecto);
form.elements.tecnico.addEventListener('change', event => switchTecnico(event.target.value));
form.elements.add_photos.addEventListener('change', syncPhotoPanel);
form.elements.photos.addEventListener('change', renderPhotoPreview);
form.addEventListener('change', event => {
  if (event.target.name === 'proyecto_id') syncProyecto();
  if (event.target.name === 'jornada') syncJornada();
  scheduleDraftSave();
});
form.addEventListener('input', event => {
  if (event.target.type === 'file') return;
  scheduleDraftSave();
});
window.addEventListener('beforeunload', () => saveDraftNow());

form.addEventListener('submit', async event => {
  event.preventDefault();
  if (!form.reportValidity()) return;
  const submitTecnico = form.elements.tecnico.value;
  const submittedProfile = collectProfile();
  const button = form.querySelector('button[type="submit"]');
  button.disabled = true;
  setStatus('', 'Guardando parte...');
  const formData = new FormData(form);
  formData.set('conductor', form.elements.conductor.checked ? 'true' : 'false');
  formData.set('add_photos', form.elements.add_photos.checked ? 'true' : 'false');
  if (!form.elements.add_photos.checked) {
    formData.delete('photos');
  }
  try {
    const response = await fetch('/api/submit/', {
      method: 'POST',
      headers: {'X-CSRFToken': decodeURIComponent(getCookie('csrftoken'))},
      body: formData,
    });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || 'Error al guardar el parte');
    const warning = data.warning ? `<br><span class="warning">${data.warning}</span>` : '';
    const photoText = data.photoCount ? `<br><span>${data.photoCount} foto(s) guardada(s) durante 7 días.</span>` : '';
    setStatus('success', `Parte guardado correctamente. <a href="${data.pdfUrl}" target="_blank" rel="noopener">Abrir PDF</a>${photoText}${warning}`);
    clearDraft(submitTecnico);
    saveSubmittedProfile(submitTecnico, submittedProfile);
    const tecnico = submitTecnico;
    form.reset();
    form.elements.fecha.value = todayIso();
    form.elements.tecnico.value = tecnico;
    currentTecnico = tecnico;
    if (tecnico) applyProfile(tecnico);
    form.elements.password.value = '';
    renderPhotoPreview();
    syncFridayJornada();
    syncProyecto();
  } catch (error) {
    setStatus('error', error.message);
  } finally {
    button.disabled = false;
  }
});

initPasswordToggle();
init().catch(error => setStatus('error', error.message));
