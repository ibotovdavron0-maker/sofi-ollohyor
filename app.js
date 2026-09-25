document.getElementById('year').textContent = new Date().getFullYear();

const teacherGrid = document.getElementById('teachersGrid');
const leaderboard = document.getElementById('leaderboard');

function esc(value) {
  return String(value ?? '').replace(/[&<>'"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));
}

function renderTeachers(list) {
  if (!teacherGrid) return;
  if (!list?.length) {
    teacherGrid.innerHTML = '<div class="empty-card">👨‍🏫 Hozircha o‘qituvchilar ma’lumoti qo‘shilmagan.</div>';
    return;
  }
  teacherGrid.innerHTML = list.map(t => {
    const photo = t.photo ? `<img src="${esc(t.photo)}" alt="${esc(t.name)}">` : '<div class="placeholder">👨‍🏫</div>';
    const subject = t.subject ? `<span class="teacher-subject">${esc(t.subject)}</span>` : '';
    const meta = [t.experience, t.education].filter(Boolean).slice(0,2).map(x => `<span>${esc(x)}</span>`).join('');
    const desc = t.description || t.achievements || t.results || 'So‘fi Ollohyor O‘quv markazi o‘qituvchisi.';
    return `<article class="teacher-card"><div class="teacher-photo">${photo}</div><div class="teacher-body"><h3>${esc(t.name)}</h3>${subject}<p>${esc(desc)}</p><div class="teacher-meta">${meta}</div></div></article>`;
  }).join('');
}

function renderRanking(list) {
  if (!leaderboard) return;
  const head = '<div class="leader-head"><span>O‘RIN</span><span>O‘QUVCHI</span><span>BALL</span></div>';
  if (!list?.length) {
    leaderboard.innerHTML = head + '<div class="leader-row"><span class="place number">—</span><strong>Hozircha reyting yo‘q</strong><b>0</b></div>';
    return;
  }
  leaderboard.innerHTML = head + list.slice(0,10).map((r,i) => {
    const medal = i===0?'🥇':i===1?'🥈':i===2?'🥉':String(i+1);
    const placeClass = i<3 ? 'place' : 'place number';
    return `<div class="leader-row"><span class="${placeClass}">${medal}</span><strong>${esc(r.name)}${r.class_name ? ` <small style="color:#7b8998;font-weight:500">· ${esc(r.class_name)}</small>`:''}</strong><b>${esc(r.score)}</b></div>`;
  }).join('');
}

async function loadLiveData() {
  try {
    const response = await fetch(`data.json?v=${Date.now()}`, {cache:'no-store'});
    if (!response.ok) throw new Error('data.json topilmadi');
    const data = await response.json();
    renderTeachers(data.teachers || []);
    renderRanking(data.ranking || []);
    const st = data.stats || {};
    const statTeachers = document.getElementById('statTeachers');
    const statSubjects = document.getElementById('statSubjects');
    if (statTeachers) statTeachers.textContent = String(st.teachers ?? 0);
    if (statSubjects) statSubjects.textContent = String(st.subjects ?? 0);
  } catch (err) {
    renderTeachers([]);
    renderRanking([]);
    console.warn('Live data:', err);
  }
}

loadLiveData();
setInterval(loadLiveData, 60000);
