(() => {
  const routeButtons = document.querySelectorAll('.route-option');
  const demoCommand = document.querySelector('#demo-command');
  const toast = document.querySelector('.toast');
  const menuButton = document.querySelector('.menu-button');
  const nav = document.querySelector('.main-nav');
  const languageSwitcher = document.querySelector('.language-switcher');
  let toastTimer;

  // The landing copy was rewritten around profiles, context safety and project
  // policy. Hide the old language switcher until the new copy is translated as
  // a complete unit instead of serving stale partial translations.
  if (languageSwitcher) languageSwitcher.remove();

  const commands = {
    copilot: 'alt-claude --profile north-mini-code --yolo',
    codex: 'alt-claude --profile nemotron --yolo',
    openrouter: 'alt-claude --profile laguna --yolo',
    kimi: 'alt-claude profiles'
  };

  function showToast(message = 'Comando copiado.') {
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add('is-visible');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('is-visible'), 1800);
  }

  routeButtons.forEach((button) => {
    button.addEventListener('click', () => {
      routeButtons.forEach((item) => {
        item.classList.remove('is-active');
        item.setAttribute('aria-pressed', 'false');
      });
      button.classList.add('is-active');
      button.setAttribute('aria-pressed', 'true');
      const command = commands[button.dataset.route];
      if (demoCommand && command) demoCommand.textContent = command;
    });
  });

  document.querySelectorAll('[data-copy-target]').forEach((button) => {
    button.addEventListener('click', async () => {
      const target = document.getElementById(button.dataset.copyTarget);
      if (!target) return;
      const value = target.innerText || target.textContent || '';
      try {
        await navigator.clipboard.writeText(value.trim());
        showToast();
      } catch {
        const area = document.createElement('textarea');
        area.value = value.trim();
        area.setAttribute('readonly', '');
        area.style.position = 'fixed';
        area.style.opacity = '0';
        document.body.appendChild(area);
        area.select();
        document.execCommand('copy');
        area.remove();
        showToast();
      }
    });
  });

  if (menuButton && nav) {
    menuButton.addEventListener('click', () => {
      const open = menuButton.getAttribute('aria-expanded') === 'true';
      menuButton.setAttribute('aria-expanded', String(!open));
      nav.classList.toggle('is-open', !open);
    });
    nav.querySelectorAll('a').forEach((link) => {
      link.addEventListener('click', () => {
        menuButton.setAttribute('aria-expanded', 'false');
        nav.classList.remove('is-open');
      });
    });
  }

  const year = document.getElementById('year');
  if (year) year.textContent = String(new Date().getFullYear());

  const revealElements = document.querySelectorAll('.reveal');
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.15 });
    revealElements.forEach((element) => observer.observe(element));
  } else {
    revealElements.forEach((element) => element.classList.add('is-visible'));
  }
})();
