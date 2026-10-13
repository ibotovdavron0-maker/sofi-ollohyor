
/* =========================================
   SUFIOLLOHYOR — MAIN JAVASCRIPT
   Modal • Application form • Teachers
   Ranking • Books • Live data
   ========================================= */

const $ = (selector, parent = document) =>
  parent.querySelector(selector);

const $$ = (selector, parent = document) =>
  [...parent.querySelectorAll(selector)];

document.addEventListener("DOMContentLoaded", () => {
  /* 1. FOOTER YILI */
  const year = $("#year");
  if (year) {
    year.textContent = new Date().getFullYear();
  }

  /* 2. MOBILE MENU */
  const hamburger = $("#hamb");
  const nav = $("#nav");

  hamburger?.addEventListener("click", () => {
    nav?.classList.toggle("open");
    hamburger.setAttribute(
      "aria-expanded",
      String(nav?.classList.contains("open") ?? false)
    );
  });

  $$("#nav a").forEach(link => {
    link.addEventListener("click", () => {
      nav?.classList.remove("open");
      hamburger?.setAttribute("aria-expanded", "false");
    });
  });

  /* 3. APPLICATION MODAL */
  const modal = $("#applyModal");

  const openModal = () => {
    if (!modal) {
      console.error("Ariza oynasi topilmadi: #applyModal");
      alert("Ariza oynasi topilmadi. Sayt HTML kodini tekshirish kerak.");
      return;
    }

    modal.classList.add("open");
    modal.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";

    const firstInput = $("input:not([type='hidden'])", modal);
    firstInput?.focus();
  };

  const closeModal = () => {
    if (!modal) return;

    modal.classList.remove("open");
    modal.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
  };

  $$("[data-open-apply]").forEach(button => {
    button.addEventListener("click", event => {
      event.preventDefault();
      openModal();
    });
  });

  $$("[data-close-modal]").forEach(button => {
    button.addEventListener("click", event => {
      event.preventDefault();
      closeModal();
    });
  });

  modal?.addEventListener("click", event => {
    if (event.target === modal) closeModal();
  });

  document.addEventListener("keydown", event => {
    if (event.key === "Escape") closeModal();
  });

  /* 4. APPLICATION FORM */
  const applyForm = $("#applyForm");
  const formSuccess = $("#formSuccess");

  applyForm?.addEventListener("submit", event => {
    event.preventDefault();

    if (!applyForm.checkValidity()) {
      applyForm.reportValidity();
      return;
    }

    /*
      Hozircha bu forma serverga yuborilmaydi.
      Supabase bilan saqlash integratsiyasini
      alohida ulash kerak.
    */

    if (formSuccess) {
      formSuccess.textContent =
        "Forma tekshirildi, lekin ariza hali serverga yuborilmadi. Saqlash tizimi ulanishi kerak.";
      formSuccess.classList.add("show");
      formSuccess.setAttribute("role", "status");
    } else {
      alert(
        "Ariza hali serverga yuborilmadi. Supabase integratsiyasini ulash kerak."
      );
    }
  });

  /* 5. SAFE TEXT */
  const escapeHTML = value =>
    String(value ?? "").replace(/[&<>'"]/g, character => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      "'": "&#39;",
      '"': "&quot;"
    })[character]);

  /* 6. TEACHERS */
  function renderTeachers(list) {
    const box = $("#teachersGrid");
    if (!box) return;

    if (!Array.isArray(list) || list.length === 0) {
      box.innerHTML =
        '<div class="empty">Hozircha ustozlar ma’lumoti qo‘shilmagan.</div>';
      return;
    }

    box.innerHTML = list.slice(0, 9).map(teacher => {
      const name = escapeHTML(teacher.name || "O‘qituvchi");

      const photo = teacher.photo
        ? `<img src="${escapeHTML(teacher.photo)}"
                alt="${name}" loading="lazy">`
        : '<div class="placeholder">👨‍🏫</div>';

      const meta = [
        teacher.experience,
        teacher.education
      ]
        .filter(Boolean)
        .slice(0, 2)
        .map(value => `<span>${escapeHTML(value)}</span>`)
        .join("");

      const description =
        teacher.description ||
        teacher.achievements ||
        teacher.results ||
        "So‘fi Ollohyor o‘quv markazi o‘qituvchisi.";

      return `
        <article class="teacher-card">
          <div class="teacher-photo">${photo}</div>
          <div class="teacher-body">
            <h3>${name}</h3>
            ${
              teacher.subject
                ? `<span class="teacher-subject">${escapeHTML(teacher.subject)}</span>`
                : ""
            }
            <p>${escapeHTML(description)}</p>
            <div class="teacher-meta">${meta}</div>
          </div>
        </article>
      `;
    }).join("");
  }

  /* 7. STUDENT RANKING */
  function renderRanking(list) {
    const box = $("#leaderboard");
    if (!box) return;

    const count = $("#rankCount");

    if (!Array.isArray(list) || list.length === 0) {
      if (count) count.textContent = "0";

      box.innerHTML =
        '<div class="empty">Hozircha reyting ma’lumotlari yo‘q.</div>';
      return;
    }

    if (count) count.textContent = String(list.length);

    const header = `
      <div class="leader-head">
        <span>O‘RIN</span>
        <span>O‘QUVCHI</span>
        <span>BALL</span>
      </div>
    `;

    const rows = list.slice(0, 10).map((student, index) => {
      const medal = ["🥇", "🥈", "🥉"][index] || String(index + 1);

      const className = student.class_name
        ? `<small> · ${escapeHTML(student.class_name)}</small>`
        : "";

      return `
        <div class="leader-row">
          <span class="${index < 3 ? "place" : "number"}">
            ${medal}
          </span>
          <strong>${escapeHTML(student.name || "O‘quvchi")}${className}</strong>
          <b>${escapeHTML(student.score ?? 0)}</b>
        </div>
      `;
    }).join("");

    box.innerHTML = header + rows;
  }

  /* 8. BOOKS AND LEARNING MATERIALS */
  function renderBooks(list) {
    const box = $("#booksGrid");
    if (!box) return;

    if (!Array.isArray(list) || list.length === 0) {
      box.innerHTML =
        '<div class="empty">Hozircha darsliklar qo‘shilmagan.</div>';
      return;
    }

    box.innerHTML = list.slice(0, 12).map(book => {
      const title = escapeHTML(book.title || book.name || "Darslik");
      const subject = escapeHTML(book.subject || "O‘quv materiali");

      const link = book.url
        ? `<a href="${escapeHTML(book.url)}"
              target="_blank"
              rel="noopener noreferrer">Ochish →</a>`
        : "";

      return `
        <article class="book-card">
          <div class="book-icon">📘</div>
          <h3>${title}</h3>
          <p>${subject}</p>
          ${link}
        </article>
      `;
    }).join("");
  }

  /* 9. LOAD PUBLIC DATA */
  let isLoading = false;

  async function loadLiveData() {
    if (isLoading) return;
    isLoading = true;

    try {
      const response = await fetch(
        `data.json?v=${Date.now()}`,
        { cache: "no-store" }
      );

      if (!response.ok) {
        throw new Error(`Ma’lumot yuklanmadi: ${response.status}`);
      }

      const data = await response.json();

      renderTeachers(data.teachers || []);
      renderRanking(data.ranking || []);
      renderBooks(data.books || []);

      const stats = data.stats || {};

      const teachers = $("#statTeachers");
      const subjects = $("#statSubjects");
      const students = $("#statStudents");

      if (teachers && stats.teachers != null) {
        teachers.textContent = String(stats.teachers);
      }

      if (subjects && stats.subjects != null) {
        subjects.textContent = String(stats.subjects);
      }

      if (students && stats.students != null) {
        students.textContent = String(stats.students);
      }
    } catch (error) {
      console.warn("Sayt ma’lumotlarini yuklashda xato:", error);

      renderTeachers([]);
      renderRanking([]);
      renderBooks([]);
    } finally {
      isLoading = false;
    }
  }

  loadLiveData();
  window.setInterval(loadLiveData, 60000);

  /* 10. HEADER SCROLL EFFECT */
  const header = $("#header");

  const updateHeader = () => {
    header?.classList.toggle("scrolled", window.scrollY > 20);
  };

  window.addEventListener("scroll", updateHeader, { passive: true });
  updateHeader();
});
      
