const $=(s,p=document)=>p.querySelector(s);
const $$=(s,p=document)=>[...p.querySelectorAll(s)];
document.addEventListener("DOMContentLoaded",()=>{
  $("#year").textContent=new Date().getFullYear();

  const hamb=$("#hamb"), nav=$("#nav");
  hamb?.addEventListener("click",()=>nav.classList.toggle("open"));
  $$("#nav a").forEach(a=>a.addEventListener("click",()=>nav.classList.remove("open")));

  const modal=$("#applyModal");
  const openModal=()=>{modal.classList.add("open");modal.setAttribute("aria-hidden","false");document.body.style.overflow="hidden"};
  const closeModal=()=>{modal.classList.remove("open");modal.setAttribute("aria-hidden","true");document.body.style.overflow=""};
  $$("[data-open-apply]").forEach(b=>b.addEventListener("click",openModal));
  $$("[data-close-modal]").forEach(b=>b.addEventListener("click",closeModal));
  document.addEventListener("keydown",e=>{if(e.key==="Escape")closeModal()});

  $("#applyForm")?.addEventListener("submit",e=>{
    e.preventDefault();
    $("#formSuccess").classList.add("show");
    e.target.reset();
  });

  const esc=v=>String(v??"").replace(/[&<>'"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c]));

  function renderTeachers(list){
    const box=$("#teachersGrid"); if(!box)return;
    if(!list?.length){box.innerHTML='<div class="empty">Hozircha ustozlar ma’lumoti qo‘shilmagan.</div>';return}
    box.innerHTML=list.slice(0,9).map(t=>{
      const photo=t.photo?`<img src="${esc(t.photo)}" alt="${esc(t.name)}">`:`<div class="placeholder">👨‍🏫</div>`;
      const meta=[t.experience,t.education].filter(Boolean).slice(0,2).map(x=>`<span>${esc(x)}</span>`).join("");
      const desc=t.description||t.achievements||t.results||"So‘fi Ollohyor O‘quv markazi o‘qituvchisi.";
      return `<article class="teacher-card"><div class="teacher-photo">${photo}</div><div class="teacher-body"><h3>${esc(t.name)}</h3>${t.subject?`<span class="teacher-subject">${esc(t.subject)}</span>`:""}<p>${esc(desc)}</p><div class="teacher-meta">${meta}</div></div></article>`;
    }).join("");
  }

  function renderRanking(list){
    const box=$("#leaderboard"); if(!box)return;
    if(!list?.length){box.innerHTML='<div class="empty">Hozircha reyting ma’lumotlari yo‘q.</div>';return}
    $("#rankCount").textContent=list.length;
    const head='<div class="leader-head"><span>O‘RIN</span><span>O‘QUVCHI</span><span>BALL</span></div>';
    box.innerHTML=head+list.slice(0,10).map((r,i)=>{
      const medal=i===0?"🥇":i===1?"🥈":i===2?"🥉":String(i+1);
      return `<div class="leader-row"><span class="${i<3?"place":"number"}">${medal}</span><strong>${esc(r.name)}${r.class_name?` <small style="color:#8290a0">· ${esc(r.class_name)}</small>`:""}</strong><b>${esc(r.score)}</b></div>`;
    }).join("");
  }

  function renderBooks(list){
    const box=$("#booksGrid"); if(!box)return;
    if(!list?.length){box.innerHTML='<div class="empty">Hozircha darsliklar qo‘shilmagan. Telegram bot orqali qo‘shilganda shu yerda chiqadi.</div>';return}
    box.innerHTML=list.slice(0,12).map(b=>`<article class="book-card"><div class="book-icon">📘</div><h3>${esc(b.title||b.name||"Darslik")}</h3><p>${esc(b.subject||"O‘quv materiali")}</p>${b.url?`<a href="${esc(b.url)}" target="_blank" rel="noopener">Ochish →</a>`:""}</article>`).join("");
  }

  async function loadLiveData(){
    try{
      const r=await fetch(`data.json?v=${Date.now()}`,{cache:"no-store"});
      if(!r.ok)throw new Error("data.json topilmadi");
      const d=await r.json();
      renderTeachers(d.teachers||[]);
      renderRanking(d.ranking||[]);
      renderBooks(d.books||[]);
      const st=d.stats||{};
      if($("#statTeachers"))$("#statTeachers").textContent=String(st.teachers??"—");
      if($("#statSubjects"))$("#statSubjects").textContent=String(st.subjects??"—");
      if($("#statStudents")&&st.students)$("#statStudents").textContent=String(st.students);
    }catch(e){
      console.warn("Live data:",e);
      renderTeachers([]);
      renderRanking([]);
      renderBooks([]);
    }
  }
  loadLiveData();
  setInterval(loadLiveData,60000);

  const header=$("#header");
  window.addEventListener("scroll",()=>header?.classList.toggle("scrolled",scrollY>20),{passive:true});
});
