/* ChangeLens landing page. The page works without this script: the scope results are
   switched by CSS. The script adds the count announcement, the entry motion (the `js`
   class), the language switch target and the early-bird form. */
(function () {
  'use strict';

  /* ---- Switches (list on, tracker on) -------------------------------------------- */

  // Early-bird list. Open since 2026-11-23 by the owner's decision; the legal review of the
  // mail wording and the privacy text is still open (docs/landing-page-handoff.md, "The
  // early-bird endpoint"). While this is false the form sends nothing and says that the
  // list is not open.
  var EARLY_BIRD_OPEN = true;
  var EARLY_BIRD_URL = 'https://api.pixeltronic.dev/early-bird';

  // Umami tracker tag. On since 2026-11-22 by the owner's decision; the legal review's answer
  // to the consent question is still open (docs/landing-page-handoff.md, "Measurement").
  // While this is false no tracker script is loaded and no tracker request is made; the
  // data-umami-event attributes do nothing. A browser that sends Do Not Track is not recorded.
  var TRACKER_ENABLED = true;
  var TRACKER_SRC = '/umami/script.js'; // same host; Caddy passes it on to Umami (deploy/ionos/Caddyfile)
  var TRACKER_WEBSITE_ID = '2bafac1d-346c-48e2-8b34-c8a77e0e5d0f';

  document.documentElement.classList.add('js');

  if (TRACKER_ENABLED && TRACKER_WEBSITE_ID) {
    var tag = document.createElement('script');
    tag.defer = true;
    tag.src = TRACKER_SRC;
    tag.dataset.websiteId = TRACKER_WEBSITE_ID;
    tag.dataset.doNotTrack = 'true';
    document.head.appendChild(tag);
  }

  function track(name) {
    if (window.umami && typeof window.umami.track === 'function') window.umami.track(name);
  }

  /* ---- Scope question: announce the count line once per choice ------------------- */

  var live = document.getElementById('scope-live');
  var clearLive;
  document.querySelectorAll('input[name="scope"]').forEach(function (input) {
    input.addEventListener('change', function () {
      var line = document.querySelector('[data-count~="' + input.value + '"]');
      if (!live || !line) return;
      // The visible line stays on the page, so the copy in the live region is removed
      // again; a screen reader then does not meet the same sentence twice while reading.
      live.textContent = line.textContent.replace(/\s+/g, ' ').trim();
      clearTimeout(clearLive);
      clearLive = setTimeout(function () { live.textContent = ''; }, 4000);
    });
  });

  /* ---- Language switch: land on the same section of the other document ----------- */

  function currentSection() {
    var found = '';
    document.querySelectorAll('main section[id]').forEach(function (section) {
      if (section.getBoundingClientRect().top <= window.innerHeight / 2) found = section.id;
    });
    return found;
  }

  document.querySelectorAll('a[data-lang-switch]:not([aria-current])').forEach(function (link) {
    var base = link.getAttribute('href');
    link.addEventListener('click', function () {
      var id = currentSection();
      link.setAttribute('href', id ? base + '#' + id : base);
    });
  });

  /* ---- Early-bird form ----------------------------------------------------------- */

  var form = document.getElementById('early-bird');
  if (!form) return;

  var input = form.querySelector('input[type="email"]');
  var button = form.querySelector('button[type="submit"]');
  var error = document.getElementById('eb-error');
  var status = document.getElementById('eb-status');
  // The markup ships with the "needs JavaScript" message visible and the button disabled,
  // which is the honest state without scripting.

  form.noValidate = true; // errors are reported in the page's own text, not browser bubbles
  status.innerHTML = '';
  button.disabled = false;

  function show(html) {
    status.innerHTML = html;
  }

  function template(id) {
    var node = document.getElementById(id);
    return node ? node.innerHTML : '';
  }

  function setInvalid(invalid) {
    error.hidden = !invalid;
    if (invalid) input.setAttribute('aria-invalid', 'true');
    else input.removeAttribute('aria-invalid');
  }

  input.addEventListener('input', function () {
    if (input.getAttribute('aria-invalid') === 'true' && input.validity.valid) setInvalid(false);
  });

  form.addEventListener('submit', function (event) {
    event.preventDefault();
    show('');

    var email = input.value.trim();
    if (!email || !input.validity.valid) {
      setInvalid(true);
      input.focus();
      return;
    }
    setInvalid(false);

    if (!EARLY_BIRD_OPEN) {
      show(template('eb-msg-closed')); // nothing is sent and nothing is saved
      return;
    }

    button.disabled = true;
    form.setAttribute('aria-busy', 'true');
    fetch(EARLY_BIRD_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: email, locale: form.dataset.locale === 'de' ? 'de' : 'en' })
    }).then(function (response) {
      if (response.status !== 202) throw new Error('unexpected status');
      form.reset();
      show(template('eb-msg-sent'));
      track('list-submit');
    }).catch(function () {
      show(template('eb-msg-failed'));
    }).then(function () {
      button.disabled = false;
      form.removeAttribute('aria-busy');
    });
  });
})();
