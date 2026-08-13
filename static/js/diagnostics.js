document.addEventListener("DOMContentLoaded", () => {

    const search = document.getElementById("faultSearch");
    const chips = document.querySelectorAll(".chip");
    const cards = document.querySelectorAll(".fault-mock");
  
    let activeFilter = "all";
  
    function filterFaults() {
      const q = search.value.toLowerCase();
  
      cards.forEach(card => {
        const code = card.dataset.code.toLowerCase();
        const title = card.dataset.title.toLowerCase();
        const sev = card.dataset.sev;
  
        const matchesSearch = code.includes(q) || title.includes(q);
        const matchesFilter = activeFilter === "all" || sev === activeFilter;
  
        if (matchesSearch && matchesFilter) {
          card.style.display = "block";
          card.style.animation = "fadeUp 0.4s ease";
        } else {
          card.style.display = "none";
        }
      });
    }
  
    // search typing
    search.addEventListener("input", filterFaults);
  
    // chips click
    chips.forEach(btn => {
      btn.addEventListener("click", () => {
  
        chips.forEach(c => c.classList.remove("active"));
        btn.classList.add("active");
  
        activeFilter = btn.dataset.filter;
  
        filterFaults();
      });
    });
  
  });