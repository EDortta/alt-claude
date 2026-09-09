(() => {
  const routeButtons = document.querySelectorAll('.route-option');
  const demoCommand = document.querySelector('#demo-command');
  const toast = document.querySelector('.toast');
  const menuButton = document.querySelector('.menu-button');
  const nav = document.querySelector('.main-nav');
  let toastTimer;

  routeButtons.forEach((button) => {
    button.addEventListener('click', () => {
      routeButtons.forEach((item) => {
        item.classList.remove('is-active');
        item.setAttribute('aria-pressed', 'false');
      });

      button.classList.add('is-active');
      button.setAttribute('aria-pressed', 'true');
      demoCommand.textContent = `alt-claude --use ${button.dataset.route}`;
    });
  });

  function showToast(message = 'Comando copiado. Finja que decorou.') {
    toast.textContent = message;
    toast.classList.add('is-visible');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('is-visible'), 2500);
  }

  document.querySelectorAll('[data-copy-target]').forEach((button) => {
    button.addEventListener('click', async () => {
      const target = document.getElementById(button.dataset.copyTarget);
      const text = target?.innerText ?? target?.textContent ?? '';

      try {
        await navigator.clipboard.writeText(text.trim());
        showToast();
        const label = button.querySelector('span');
        if (label) {
          const original = label.textContent;
          label.textContent = 'copiado!';
          setTimeout(() => { label.textContent = original; }, 1800);
        }
      } catch {
        showToast('Selecione e copie. O terminal gosta do método clássico.');
      }
    });
  });

  menuButton?.addEventListener('click', () => {
    const isOpen = menuButton.getAttribute('aria-expanded') === 'true';
    menuButton.setAttribute('aria-expanded', String(!isOpen));
    nav.classList.toggle('is-open', !isOpen);
  });

  nav?.querySelectorAll('a').forEach((link) => {
    link.addEventListener('click', () => {
      menuButton?.setAttribute('aria-expanded', 'false');
      nav.classList.remove('is-open');
    });
  });

  const year = document.querySelector('#year');
  if (year) year.textContent = new Date().getFullYear();
})();
