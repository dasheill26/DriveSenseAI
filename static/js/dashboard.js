// =========================
// DASHBOARD INTERACTIONS
// =========================

document.addEventListener("DOMContentLoaded", () => {

    // =========================
    // HEALTH COUNTER ANIMATION
    // =========================
    const healthEl = document.querySelector(".statValue.green");
  
    if (healthEl) {
      const target = parseInt(healthEl.innerText);
      let current = 0;
  
      const interval = setInterval(() => {
        current += Math.ceil(target / 30);
  
        if (current >= target) {
          current = target;
          clearInterval(interval);
        }
  
        healthEl.innerText = current + "%";
      }, 20);
    }
  
    // =========================
    // PROGRESS BAR SMOOTH FILL
    // =========================
    const progress = document.querySelector(".progressFill");
    if (progress) {
      const targetWidth = progress.style.width;
      progress.style.width = "0%";
  
      setTimeout(() => {
        progress.style.width = targetWidth;
      }, 300);
    }
  
    // =========================
    // CARD ENTRANCE STAGGER
    // =========================
    const cards = document.querySelectorAll(".card");
  
    cards.forEach((card, i) => {
      card.style.opacity = "0";
      card.style.transform = "translateY(20px)";
  
      setTimeout(() => {
        card.style.transition = "all .5s ease";
        card.style.opacity = "1";
        card.style.transform = "translateY(0)";
      }, 150 * i);
    });
  
    // =========================
    // BUTTON CLICK FEEDBACK
    // =========================
    document.querySelectorAll(".btn").forEach(btn => {
      btn.addEventListener("click", () => {
        btn.style.transform = "scale(0.95)";
        setTimeout(() => {
          btn.style.transform = "";
        }, 150);
      });
    });
  
  });