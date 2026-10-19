/* ==========================================================================
   EventPro · Interfaz
   Modales con formularios AJAX, asistente por pasos, toasts, confirmaciones,
   menús, pestañas, paleta de comandos y filtros en vivo. Sin dependencias.
   ========================================================================== */
(() => {
  'use strict';

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const AJAX = { 'X-Requested-With': 'XMLHttpRequest' };

  function csrf() {
    const meta = $('meta[name="csrf-token"]');
    if (meta) return meta.content;
    const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  }

  function escapeHtml(str) {
    return String(str ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  /* ------------------------------------------------------------------ Toasts */
  const TOAST_ICONS = { success: 'ph ph-check', error: 'ph ph-x-circle', warning: 'ph ph-warning-circle', info: 'ph ph-info' };

  function toast(message, type = 'success', duration = 4200) {
    if (!message) return;
    let box = $('.toasts');
    if (!box) {
      box = document.createElement('div');
      box.className = 'toasts';
      box.setAttribute('aria-live', 'polite');
      document.body.appendChild(box);
    }
    const el = document.createElement('div');
    el.className = `toast toast--${type}`;
    el.style.setProperty('--dur', `${duration}ms`);
    el.innerHTML = `<div class="toast__icon"><i class="${TOAST_ICONS[type] || TOAST_ICONS.info}"></i></div>
      <div class="toast__text">${escapeHtml(message)}</div>
      <button class="toast__close" aria-label="Cerrar"><i class="ph ph-x"></i></button>`;
    const remove = () => { el.classList.add('is-leaving'); setTimeout(() => el.remove(), 250); };
    el.querySelector('.toast__close').addEventListener('click', remove);
    box.appendChild(el);
    setTimeout(remove, duration);
  }

  function toastNextPage(message, type = 'success') {
    try { sessionStorage.setItem('em-toast', JSON.stringify({ message, type })); } catch (e) { /* sin almacenamiento */ }
  }

  function flushPendingToast() {
    try {
      const raw = sessionStorage.getItem('em-toast');
      if (raw) {
        sessionStorage.removeItem('em-toast');
        const { message, type } = JSON.parse(raw);
        toast(message, type);
      }
    } catch (e) { /* sin almacenamiento */ }
  }

  /* ------------------------------------------------------------------ Respuestas JSON */
  function handleJson(data, { fromModal = false } = {}) {
    if (!data) return;
    const type = data.ok === false ? 'error' : 'success';
    if (data.redirect) {
      if (data.message) toastNextPage(data.message, type);
      window.location.href = data.redirect;
      return;
    }
    if (data.reload) {
      if (data.message) toastNextPage(data.message, type);
      window.location.reload();
      return;
    }
    if (data.abrir) {
      // "Guardar y agregar otro": reabre el formulario y recarga al terminar
      if (data.message) toast(data.message, type);
      Modal.pendingReload = true;
      Modal.open(data.abrir);
      return;
    }
    if (data.message) toast(data.message, type);
    document.dispatchEvent(new CustomEvent('em:saved', { detail: data }));
  }

  /* ------------------------------------------------------------------ Diálogo de confirmación */
  function confirmDialog({ title = '¿Estás seguro?', text = '', confirmText = 'Confirmar', cancelText = 'Cancelar', danger = false, icon } = {}) {
    return new Promise(resolve => {
      const el = document.createElement('div');
      el.className = 'modal';
      el.innerHTML = `
        <div class="modal__dialog modal__dialog--sm" role="alertdialog" aria-modal="true">
          <div class="modal__header">
            <div class="modal__icon ${danger ? 'modal__icon--danger' : ''}"><i class="${icon || (danger ? 'ph ph-trash' : 'ph ph-question')}"></i></div>
            <div><h2>${escapeHtml(title)}</h2>${text ? `<p>${escapeHtml(text)}</p>` : ''}</div>
          </div>
          <div class="modal__footer" style="margin-top:22px">
            <button class="btn" data-answer="0">${escapeHtml(cancelText)}</button>
            <button class="btn ${danger ? 'btn--danger' : 'btn--primary'}" data-answer="1">${escapeHtml(confirmText)}</button>
          </div>
        </div>`;
      const finish = ok => {
        el.classList.add('is-closing');
        setTimeout(() => el.remove(), 180);
        document.removeEventListener('keydown', onKey, true);
        resolve(ok);
      };
      const onKey = e => {
        if (e.key === 'Escape') { e.stopPropagation(); finish(false); }
        if (e.key === 'Enter') { e.preventDefault(); e.stopPropagation(); finish(true); }
      };
      el.addEventListener('click', e => {
        const btn = e.target.closest('[data-answer]');
        if (btn) finish(btn.dataset.answer === '1');
        else if (e.target === el) finish(false);
      });
      document.addEventListener('keydown', onKey, true);
      document.body.appendChild(el);
      el.querySelector('[data-answer="1"]').focus();
    });
  }

  /* ------------------------------------------------------------------ Modales */
  const Modal = {
    stack: [],

    async open(url, opts = {}) {
      const el = document.createElement('div');
      el.className = 'modal';
      el.innerHTML = '<div class="modal-loading" aria-label="Cargando"></div>';
      document.body.appendChild(el);
      document.body.style.overflow = 'hidden';
      const entry = { el, url, opts, dirty: false, prevFocus: document.activeElement };
      this.stack.push(entry);

      el.addEventListener('mousedown', e => { entry.downOnOverlay = e.target === el; });
      el.addEventListener('click', e => {
        if (e.target === el && entry.downOnOverlay) this.close(entry);
        if (e.target.closest('[data-close]')) { e.preventDefault(); this.close(entry); }
      });

      try {
        const res = await fetch(url, { headers: AJAX, credentials: 'same-origin' });
        const type = res.headers.get('content-type') || '';
        if (type.includes('application/json')) {
          this.close(entry, true);
          handleJson(await res.json());
          return null;
        }
        if (res.status === 403) throw new Error('Sin permiso');
        if (!res.ok) throw new Error(res.status);
        this.render(entry, await res.text());
      } catch (err) {
        this.close(entry, true);
        toast(err.message === 'Sin permiso' ? 'No tienes permiso para esta acción.' : 'No se pudo abrir el formulario.', 'error');
      }
      return entry;
    },

    render(entry, html) {
      entry.el.innerHTML = html;
      entry.dirty = false;
      // Los <script> insertados con innerHTML no se ejecutan: se recrean
      $$('script', entry.el).forEach(viejo => {
        const nuevo = document.createElement('script');
        nuevo.textContent = viejo.textContent;
        viejo.replaceWith(nuevo);
      });
      init(entry.el);
      const form = $('form', entry.el);
      if (form) {
        form.addEventListener('input', () => { entry.dirty = true; });
        form.addEventListener('change', () => { entry.dirty = true; });
        form.addEventListener('submit', e => {
          if (form.hasAttribute('data-native')) return;
          e.preventDefault();
          submitForm(form, entry, e.submitter);
        });
      }
      const first = $('[autofocus]', entry.el) ||
        $('[data-step-panel].is-active input:not([type=hidden]):not([type=checkbox]):not([type=radio]):not([type=file]), .modal__body input:not([type=hidden]):not([type=checkbox]):not([type=radio]):not([type=file]), .modal__body textarea', entry.el);
      if (first && window.matchMedia('(min-width: 641px)').matches) setTimeout(() => first.focus(), 60);
    },

    async close(entry, force = false) {
      entry = entry || this.stack[this.stack.length - 1];
      if (!entry || entry.closing) return;
      if (!force && entry.dirty) {
        const ok = await confirmDialog({ title: '¿Descartar cambios?', text: 'Tienes cambios sin guardar en este formulario.', confirmText: 'Descartar', danger: true, icon: 'ph ph-warning-circle' });
        if (!ok) return;
      }
      entry.closing = true;
      entry.el.classList.add('is-closing');
      setTimeout(() => entry.el.remove(), 180);
      this.stack = this.stack.filter(x => x !== entry);
      if (!this.stack.length) {
        document.body.style.overflow = '';
        if (this.pendingReload) { this.pendingReload = false; window.location.reload(); }
      }
      if (entry.prevFocus && entry.prevFocus.focus) entry.prevFocus.focus();
    },
  };

  async function submitForm(form, entry, submitter) {
    const btn = submitter || $('[type=submit]', form);
    if (btn) btn.classList.add('is-loading');
    try {
      const data = new FormData(form);
      if (submitter && submitter.name) data.append(submitter.name, submitter.value);
      const res = await fetch(form.action || window.location.href, {
        method: (form.method || 'POST').toUpperCase(),
        body: data,
        headers: { ...AJAX, 'X-CSRFToken': csrf() },
        credentials: 'same-origin',
      });
      const type = res.headers.get('content-type') || '';
      if (type.includes('application/json')) {
        const json = await res.json();
        if (json.ok === false) {
          toast(json.message || 'No se pudo guardar.', 'error');
          return;
        }
        if (json.abrir && entry) {
          // Abre el siguiente formulario antes de cerrar el actual para no recargar a medias
          if (json.message) toast(json.message);
          Modal.pendingReload = true;
          await Modal.open(json.abrir);
          Modal.close(entry, true);
          return;
        }
        if (entry) Modal.close(entry, true);
        handleJson(json, { fromModal: !!entry });
        return;
      }
      if (res.status === 422 || res.ok) {
        const html = await res.text();
        if (entry) {
          Modal.render(entry, html);
          entry.dirty = true;
          toast('Revisa los campos marcados.', 'warning');
        }
        return;
      }
      throw new Error(res.status);
    } catch (err) {
      toast('Ocurrió un error al guardar. Intenta de nuevo.', 'error');
    } finally {
      if (btn) btn.classList.remove('is-loading');
    }
  }

  /* ------------------------------------------------------------------ Asistente por pasos */
  function initWizard(root) {
    $$('[data-wizard]', root).forEach(form => {
      const panels = $$('[data-step-panel]', form);
      const steps = $$('[data-step]', form);
      const prev = $('[data-prev]', form);
      const next = $('[data-next]', form);
      const save = $$('[data-save]', form);
      const freeSave = form.hasAttribute('data-free-save');
      if (!panels.length) return;
      let idx = 0;

      const showError = (field, message) => {
        const wrap = field.closest('.field');
        if (!wrap) return;
        wrap.classList.add('field--error');
        if (!$('.field__error[data-client]', wrap)) {
          const small = document.createElement('small');
          small.className = 'field__error';
          small.dataset.client = '1';
          small.innerHTML = `<i class="ph ph-warning-circle"></i>${escapeHtml(message)}`;
          wrap.appendChild(small);
        }
      };

      const validate = i => {
        let firstBad = null;
        $$('input, select, textarea', panels[i]).forEach(f => {
          if (f.type === 'hidden' || f.disabled) return;
          if (!f.checkValidity()) {
            showError(f, f.validationMessage);
            firstBad = firstBad || f;
          }
        });
        if (firstBad) { firstBad.focus(); return false; }
        return true;
      };

      const go = i => {
        idx = Math.max(0, Math.min(i, panels.length - 1));
        panels.forEach((p, j) => p.classList.toggle('is-active', j === idx));
        steps.forEach((s, j) => {
          s.classList.toggle('is-active', j === idx);
          s.classList.toggle('is-done', j < idx);
        });
        const last = idx === panels.length - 1;
        if (prev) prev.hidden = idx === 0;
        if (next) next.hidden = last;
        save.forEach(b => {
          b.hidden = !last && !freeSave;
          b.classList.toggle('btn--primary', last);
          b.classList.toggle('btn--soft', !last);
        });
        const body = form.querySelector('.modal__body');
        if (body) body.scrollTop = 0;
      };

      form.addEventListener('input', e => {
        const wrap = e.target.closest('.field--error');
        if (wrap) {
          wrap.classList.remove('field--error');
          $$('.field__error[data-client]', wrap).forEach(x => x.remove());
        }
      });

      next && next.addEventListener('click', () => { if (validate(idx)) go(idx + 1); });
      prev && prev.addEventListener('click', () => go(idx - 1));
      steps.forEach((s, j) => s.addEventListener('click', () => {
        if (j <= idx || panels.slice(idx, j).every((_, k) => validate(idx + k))) go(j);
      }));
      form.addEventListener('keydown', e => {
        if (e.key === 'Enter' && e.target.tagName === 'INPUT' && idx < panels.length - 1) {
          e.preventDefault();
          if (validate(idx)) go(idx + 1);
        }
      });
      form.addEventListener('submit', e => {
        // Antes de enviar valida todos los pasos y salta al primero con error
        for (let i = 0; i < panels.length; i++) {
          const bad = $$('input, select, textarea', panels[i]).some(f => f.type !== 'hidden' && !f.disabled && !f.checkValidity());
          if (bad) { e.preventDefault(); e.stopImmediatePropagation(); go(i); validate(i); return; }
        }
      }, true);

      const withError = panels.findIndex(p => $('.field--error', p));
      panels.forEach((p, j) => { if ($('.field--error', p) && steps[j]) steps[j].classList.add('has-error'); });
      go(withError >= 0 ? withError : 0);
    });
  }

  /* ------------------------------------------------------------------ Componentes */
  function initDropzones(root) {
    $$('.dropzone', root).forEach(dz => {
      if (dz.dataset.ready) return;
      dz.dataset.ready = '1';
      const input = $('input[type=file]', dz);
      const preview = $('.dropzone__preview', dz);
      const title = $('.dropzone__text strong', dz);
      if (!input) return;
      input.addEventListener('change', () => {
        const file = input.files[0];
        if (!file) return;
        if (file.type.startsWith('image/') && preview) {
          preview.innerHTML = `<img src="${URL.createObjectURL(file)}" alt="">`;
        }
        if (title) title.textContent = file.name;
        const clear = $('.dropzone__clear input', dz);
        if (clear) clear.checked = false;
      });
      ['dragenter', 'dragover'].forEach(ev => dz.addEventListener(ev, () => dz.classList.add('is-over')));
      ['dragleave', 'drop'].forEach(ev => dz.addEventListener(ev, () => dz.classList.remove('is-over')));
    });
  }

  function initColorFields(root) {
    $$('.color-field', root).forEach(box => {
      if (box.dataset.ready) return;
      box.dataset.ready = '1';
      const color = $('input[type=color]', box);
      const text = $('input[type=text]', box);
      if (!color || !text) return;
      color.addEventListener('input', () => { text.value = color.value.toUpperCase(); text.dispatchEvent(new Event('input', { bubbles: true })); });
      text.addEventListener('input', () => { if (/^#[0-9a-f]{6}$/i.test(text.value)) color.value = text.value; });
      $$('[data-swatch]', box.closest('.field') || box).forEach(b => b.addEventListener('click', e => {
        e.preventDefault();
        color.value = b.dataset.swatch;
        text.value = b.dataset.swatch.toUpperCase();
        text.dispatchEvent(new Event('input', { bubbles: true }));
      }));
    });
  }

  function initTabs(root) {
    $$('[data-tabs]', root).forEach(group => {
      if (group.dataset.ready) return;
      group.dataset.ready = '1';
      const tabs = $$('[data-tab]', group);
      const scope = group.closest('[data-tabs-scope]') || document;
      const activate = (name, push) => {
        tabs.forEach(t => t.classList.toggle('is-active', t.dataset.tab === name));
        $$('[data-panel]', scope).forEach(p => { p.hidden = p.dataset.panel !== name; });
        if (push && group.hasAttribute('data-tabs-hash')) history.replaceState(null, '', `#${name}`);
      };
      tabs.forEach(t => t.addEventListener('click', e => { e.preventDefault(); activate(t.dataset.tab, true); }));
      const fromHash = location.hash.slice(1);
      const initial = tabs.find(t => t.dataset.tab === fromHash) || tabs.find(t => t.classList.contains('is-active')) || tabs[0];
      if (initial) activate(initial.dataset.tab, false);
    });
  }

  function initCountdowns(root) {
    $$('[data-countdown]', root).forEach(el => {
      if (el.dataset.ready) return;
      el.dataset.ready = '1';
      const target = new Date(el.dataset.countdown).getTime();
      const parts = { d: $('[data-cd=d]', el), h: $('[data-cd=h]', el), m: $('[data-cd=m]', el), s: $('[data-cd=s]', el) };
      const tick = () => {
        let diff = Math.max(0, target - Date.now()) / 1000;
        const d = Math.floor(diff / 86400); diff -= d * 86400;
        const h = Math.floor(diff / 3600); diff -= h * 3600;
        const m = Math.floor(diff / 60);
        const s = Math.floor(diff - m * 60);
        if (parts.d) parts.d.textContent = d;
        if (parts.h) parts.h.textContent = String(h).padStart(2, '0');
        if (parts.m) parts.m.textContent = String(m).padStart(2, '0');
        if (parts.s) parts.s.textContent = String(s).padStart(2, '0');
      };
      tick();
      setInterval(tick, 1000);
    });
  }

  function initBars(root) {
    requestAnimationFrame(() => {
      $$('[data-width]', root).forEach(el => { el.style.width = `${el.dataset.width}%`; });
      $$('[data-height]', root).forEach(el => { el.style.height = `${el.dataset.height}%`; });
    });
  }

  function initAutosubmit(root) {
    $$('form[data-autosubmit]', root).forEach(form => {
      if (form.dataset.ready) return;
      form.dataset.ready = '1';
      let timer;
      const target = form.dataset.target;
      const run = async () => {
        const params = new URLSearchParams(new FormData(form));
        [...params.keys()].forEach(k => { if (!params.get(k)) params.delete(k); });
        // Sin atributo action, form.action devuelve la URL actual con su "?…": se arma desde la ruta para no encadenar filtros
        const destino = new URL(form.getAttribute('action') || location.pathname, location.href);
        destino.search = params.toString();
        const url = destino.pathname + destino.search;
        if (!target) { location.href = url; return; }
        const selectores = target.split(',').map(x => x.trim());
        const cajas = selectores.map(sel => $(sel));
        cajas.forEach(b => b && b.classList.add('is-loading-area'));
        try {
          const res = await fetch(url, { headers: AJAX });
          const doc = new DOMParser().parseFromString(await res.text(), 'text/html');
          selectores.forEach((sel, i) => {
            const fresh = doc.querySelector(sel);
            if (fresh && cajas[i]) { cajas[i].innerHTML = fresh.innerHTML; init(cajas[i]); }
          });
          history.replaceState(null, '', url);
        } finally { cajas.forEach(b => b && b.classList.remove('is-loading-area')); }
      };
      form.addEventListener('submit', e => { e.preventDefault(); run(); });
      form.addEventListener('change', e => { if (e.target.type !== 'search' && e.target.type !== 'text') run(); });
      form.addEventListener('input', e => {
        if (e.target.type === 'search' || e.target.type === 'text') { clearTimeout(timer); timer = setTimeout(run, 320); }
      });
    });
  }

  // Límites con "Sin límite": al marcarlo se vacía y bloquea el número (vacío = sin límite)
  function initSinLimite(root) {
    $$('[data-sin-limite]', root).forEach(chk => {
      if (chk.dataset.ready) return;
      chk.dataset.ready = '1';
      const caja = chk.closest('[data-limite]');
      const input = caja && $('input[type=number]', caja);
      if (!input) return;
      const aplicar = enfocar => {
        caja.classList.toggle('is-ilimitado', chk.checked);
        if (chk.checked) {
          if (input.value) input.dataset.antes = input.value;
          input.value = '';
        } else if (!input.value && input.dataset.antes) {
          input.value = input.dataset.antes;
        }
        input.disabled = chk.checked;
        if (!chk.checked && enfocar) input.focus();
      };
      chk.addEventListener('change', () => aplicar(true));
      input.addEventListener('blur', () => { if (!input.value && !chk.checked) { chk.checked = true; aplicar(false); } });
      aplicar(false);
    });
  }

  // Módulos del plan: la tarjeta se marca al encenderla y las que dependen de otra se apagan con ella
  function initModulosPlan(root) {
    const tarjetas = $$('[data-modulo]', root).filter(t => !t.dataset.ready);
    if (!tarjetas.length) return;
    const interruptor = t => $('input[type=checkbox][name]', t);
    const porCampo = {};
    tarjetas.forEach(t => { t.dataset.ready = '1'; porCampo[t.dataset.modulo] = t; });
    const pintar = () => tarjetas.forEach(t => {
      const chk = interruptor(t);
      const padre = porCampo[t.dataset.requiere];
      const disponible = !padre || interruptor(padre).checked;
      if (!disponible && !chk.disabled) {
        chk.dataset.antes = chk.checked ? '1' : '';
        chk.checked = false;
        chk.disabled = true;
      } else if (disponible && chk.disabled) {
        chk.disabled = false;
        chk.checked = chk.dataset.antes === '1';
      }
      t.classList.toggle('is-on', chk.checked);
      t.classList.toggle('is-bloqueado', !disponible);
    });
    tarjetas.forEach(t => interruptor(t).addEventListener('change', pintar));
    pintar();
  }

  // Bolsa de fotos al mes del plan: al cambiar la fecha o las fotos del evento dice cuántas quedan ese mes
  const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
  function initBolsaFotos(root) {
    $$('[data-bolsa-fotos]', root).forEach(el => {
      if (el.dataset.ready) return;
      el.dataset.ready = '1';
      const datos = JSON.parse(el.dataset.bolsaFotos);
      const form = el.closest('form') || document;
      const fecha = $('[name=fecha_inicio_evento]', form);
      const input = $('[data-bolsa-apartar]', form);
      const texto = $('[data-bolsa-texto]', el);
      const fmt = n => Number(n).toLocaleString('es-MX');
      const pintar = () => {
        const valor = (fecha && fecha.value) || '';
        const mes = MESES[parseInt(valor.slice(5, 7), 10) - 1];
        const libres = valor.slice(0, 7) in datos.libres ? datos.libres[valor.slice(0, 7)] : datos.total;
        const apartar = input ? Math.max(0, parseInt(input.value, 10) || 0) : 0;
        const excede = apartar > libres;
        $('.bolsa-fotos__ocupadas', el).style.width = `${(datos.total - libres) * 100 / datos.total}%`;
        $('.bolsa-fotos__este', el).style.width = `${Math.min(apartar, libres) * 100 / datos.total}%`;
        el.classList.toggle('is-excedida', excede);
        const bolsa = mes ? `Bolsa de ${mes}` : 'Bolsa del mes';
        texto.innerHTML = excede
          ? `En ${mes || 'ese mes'} solo quedan <strong>${fmt(libres)}</strong> fotos libres de tu bolsa de ${fmt(datos.total)}.`
          : apartar
            ? `${bolsa}: quedan <strong>${fmt(libres)}</strong> de ${fmt(datos.total)} fotos · con este evento quedarían <strong>${fmt(libres - apartar)}</strong>.`
            : `${bolsa}: quedan <strong>${fmt(libres)}</strong> de ${fmt(datos.total)} fotos. Vacío = usa lo que quede libre del mes.`;
      };
      if (fecha) ['input', 'change'].forEach(ev => fecha.addEventListener(ev, pintar));
      if (input) input.addEventListener('input', pintar);
      pintar();
    });
  }

  function init(root = document) {
    initWizard(root);
    initDropzones(root);
    initColorFields(root);
    initTabs(root);
    initCountdowns(root);
    initBars(root);
    initAutosubmit(root);
    initSinLimite(root);
    initModulosPlan(root);
    initBolsaFotos(root);
  }

  /* ------------------------------------------------------------------ Acciones POST */
  async function post(url, body = {}) {
    const data = body instanceof FormData ? body : new URLSearchParams(body);
    const res = await fetch(url, {
      method: 'POST', body: data, credentials: 'same-origin',
      headers: { ...AJAX, 'X-CSRFToken': csrf() },
    });
    if (!res.ok && res.status !== 422) throw new Error(res.status);
    return res.json();
  }

  async function runPost(el) {
    const msg = el.dataset.confirm;
    if (msg) {
      const ok = await confirmDialog({
        title: msg, text: el.dataset.confirmText || '', danger: el.hasAttribute('data-danger'),
        confirmText: el.dataset.confirmButton || (el.hasAttribute('data-danger') ? 'Eliminar' : 'Confirmar'),
      });
      if (!ok) return;
    }
    el.classList.add('is-loading');
    try {
      handleJson(await post(el.dataset.post));
    } catch (e) {
      toast(e.message === '403' ? 'No tienes permiso para esta acción.' : 'No se pudo completar la acción.', 'error');
    } finally {
      el.classList.remove('is-loading');
    }
  }

  /* ------------------------------------------------------------------ Paleta de comandos */
  const Palette = {
    el: null, input: null, list: null, items: [], active: 0, timer: null,

    open() {
      if (this.el) return;
      const actions = JSON.parse(($('#palette-actions') || {}).textContent || '[]');
      this.el = document.createElement('div');
      this.el.className = 'modal palette';
      this.el.innerHTML = `
        <div class="modal__dialog" role="dialog" aria-label="Buscar">
          <div class="palette__input"><i class="ph ph-magnifying-glass"></i>
            <input type="search" placeholder="Busca eventos, invitados, colaboradores… o escribe una acción" autocomplete="off">
            <kbd>Esc</kbd></div>
          <div class="palette__results scroll-thin"></div>
          <div class="palette__foot"><span><kbd>↑</kbd> <kbd>↓</kbd> navegar</span><span><kbd>Enter</kbd> abrir</span><span><kbd>Ctrl</kbd> <kbd>K</kbd> abrir búsqueda</span></div>
        </div>`;
      document.body.appendChild(this.el);
      this.input = $('input', this.el);
      this.list = $('.palette__results', this.el);
      this.actions = actions;
      this.render([{ grupo: 'Acciones rápidas', items: actions }]);
      this.input.focus();
      this.input.addEventListener('input', () => {
        clearTimeout(this.timer);
        this.timer = setTimeout(() => this.search(this.input.value.trim()), 180);
      });
      this.el.addEventListener('click', e => {
        if (e.target === this.el) this.close();
        const item = e.target.closest('.palette__item');
        if (item) this.go(+item.dataset.i);
      });
      this.el.addEventListener('keydown', e => {
        if (e.key === 'Escape') { e.stopPropagation(); this.close(); }
        if (e.key === 'ArrowDown') { e.preventDefault(); this.move(1); }
        if (e.key === 'ArrowUp') { e.preventDefault(); this.move(-1); }
        if (e.key === 'Enter') { e.preventDefault(); this.go(this.active); }
      });
    },

    close() {
      if (!this.el) return;
      const el = this.el;
      el.classList.add('is-closing');
      setTimeout(() => el.remove(), 180);
      this.el = null;
    },

    async search(q) {
      const norm = s => s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
      const acciones = this.actions.filter(a => norm(`${a.titulo} ${a.sub || ''}`).includes(norm(q)));
      if (q.length < 2) { this.render([{ grupo: 'Acciones rápidas', items: acciones }]); return; }
      try {
        const res = await fetch(`/buscar/?q=${encodeURIComponent(q)}`, { headers: AJAX });
        const data = await res.json();
        const grupos = data.grupos || [];
        if (acciones.length) grupos.push({ grupo: 'Acciones', items: acciones });
        this.render(grupos);
      } catch (e) { this.render([{ grupo: 'Acciones', items: acciones }]); }
    },

    render(grupos) {
      this.items = [];
      const html = grupos.filter(g => g.items.length).map(g => `
        <div class="palette__group">${escapeHtml(g.grupo)}</div>
        ${g.items.map(it => {
          const i = this.items.push(it) - 1;
          return `<div class="palette__item" data-i="${i}">
            <div class="ico-square" style="${it.color ? `--tipo:${it.color}` : ''}"><i class="${escapeHtml(it.icono || 'ph ph-arrow-right')}"></i></div>
            <div class="grow"><strong>${escapeHtml(it.titulo)}</strong>${it.sub ? `<small>${escapeHtml(it.sub)}</small>` : ''}</div>
            ${it.atajo ? `<kbd>${escapeHtml(it.atajo)}</kbd>` : ''}</div>`;
        }).join('')}`).join('');
      this.list.innerHTML = html || '<div class="palette__empty"><i class="ph ph-binoculars" style="font-size:30px"></i><p>Sin resultados</p></div>';
      this.active = 0;
      this.highlight();
    },

    move(d) {
      if (!this.items.length) return;
      this.active = (this.active + d + this.items.length) % this.items.length;
      this.highlight();
    },

    highlight() {
      $$('.palette__item', this.list).forEach(el => {
        const on = +el.dataset.i === this.active;
        el.classList.toggle('is-active', on);
        if (on) el.scrollIntoView({ block: 'nearest' });
      });
    },

    go(i) {
      const it = this.items[i];
      if (!it) return;
      this.close();
      if (it.modal) Modal.open(it.url);
      else window.location.href = it.url;
    },
  };

  /* ------------------------------------------------------------------ Tema y menú lateral */
  function setTheme(theme) {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem('em-theme', theme); } catch (e) { /* sin almacenamiento */ }
    $$('[data-theme-icon]').forEach(i => { i.className = theme === 'dark' ? 'ph ph-sun' : 'ph ph-moon-stars'; });
    document.dispatchEvent(new CustomEvent('em:theme', { detail: theme }));
  }

  /* ------------------------------------------------------------------ Delegación global */
  document.addEventListener('click', async e => {
    const t = e.target;

    // En la página de respaldo (formulario fuera de modal) "Cancelar" regresa
    const closer = t.closest('[data-close]');
    if (closer && !closer.closest('.modal')) {
      e.preventDefault();
      if (history.length > 1) history.back(); else window.location.href = '/';
      return;
    }

    const modalTrigger = t.closest('[data-modal]');
    if (modalTrigger && !e.ctrlKey && !e.metaKey && !e.shiftKey) {
      e.preventDefault();
      closeDropdowns();
      Modal.open(modalTrigger.dataset.modal || modalTrigger.getAttribute('href'));
      return;
    }

    const postTrigger = t.closest('[data-post]');
    if (postTrigger) { e.preventDefault(); closeDropdowns(); runPost(postTrigger); return; }

    const copy = t.closest('[data-copy]');
    if (copy) {
      e.preventDefault();
      let value = copy.dataset.copy;
      if (value.startsWith('/')) value = location.origin + value;
      try { await navigator.clipboard.writeText(value); toast(copy.dataset.copyMsg || 'Enlace copiado al portapapeles'); }
      catch (err) { window.prompt('Copia el enlace:', value); }
      return;
    }

    const dd = t.closest('[data-dropdown]');
    if (dd) {
      e.preventDefault();
      const wrap = dd.closest('.dropdown');
      const open = wrap.classList.contains('is-open');
      closeDropdowns();
      if (!open) openDropdown(wrap, dd);
      return;
    }
    if (!t.closest('.dropdown__menu')) closeDropdowns();

    if (t.closest('[data-theme-toggle]')) {
      setTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');
      return;
    }

    if (t.closest('[data-sidebar-toggle]')) {
      const app = $('.app');
      if (window.matchMedia('(max-width: 1024px)').matches) app.classList.toggle('sidebar-open');
      else {
        app.classList.toggle('is-collapsed');
        try { localStorage.setItem('em-sidebar', app.classList.contains('is-collapsed') ? 'min' : 'full'); } catch (err) { /* */ }
      }
      return;
    }
    if (t.closest('.sidebar-backdrop')) { $('.app').classList.remove('sidebar-open'); return; }

    if (t.closest('[data-palette]')) { e.preventDefault(); Palette.open(); }
  });

  document.addEventListener('submit', async e => {
    const form = e.target;
    if (form.closest('.modal')) return; // los formularios del modal se manejan aparte
    if (form.dataset.confirm && !form.dataset.confirmed) {
      e.preventDefault();
      const ok = await confirmDialog({
        title: form.dataset.confirm, text: form.dataset.confirmText || '',
        danger: form.hasAttribute('data-danger'), confirmText: form.dataset.confirmButton || 'Confirmar',
      });
      if (!ok) return;
      form.dataset.confirmed = '1';
      if (form.hasAttribute('data-ajax')) submitForm(form, null, e.submitter);
      else form.submit();
      return;
    }
    if (form.hasAttribute('data-ajax')) { e.preventDefault(); submitForm(form, null, e.submitter); }
  });

  /*
   * Los menús se "sacan" al <body> mientras están abiertos y se posicionan con "fixed"
   * junto a su botón. Así nunca los recortan tablas o tarjetas, ni los desplaza la barra
   * superior (su desenfoque crea un nuevo contexto de posición para elementos fijos).
   */
  function openDropdown(wrap, trigger) {
    const menu = wrap._menu || $('.dropdown__menu', wrap);
    if (!menu) return;
    wrap._menu = menu;
    document.body.appendChild(menu);
    wrap.classList.add('is-open');
    menu.classList.add('is-open');
    const r = trigger.getBoundingClientRect();
    const mw = menu.offsetWidth;
    const mh = menu.offsetHeight;
    let left = menu.classList.contains('dropdown__menu--left') ? r.left : r.right - mw;
    left = Math.max(8, Math.min(left, window.innerWidth - mw - 8));
    let top = r.bottom + 8;
    if (top + mh > window.innerHeight - 8 && r.top - mh - 8 > 8) top = r.top - mh - 8;
    menu.style.left = `${left}px`;
    menu.style.top = `${top}px`;
    wrap.dispatchEvent(new CustomEvent('em:dropdown-open', { bubbles: true, detail: { menu } }));
  }

  function closeDropdowns() {
    $$('.dropdown.is-open').forEach(wrap => {
      wrap.classList.remove('is-open');
      const menu = wrap._menu;
      if (!menu) return;
      menu.classList.remove('is-open');
      menu.style.left = '';
      menu.style.top = '';
      wrap.appendChild(menu);
    });
  }
  window.addEventListener('scroll', () => closeDropdowns(), { passive: true });
  window.addEventListener('resize', () => closeDropdowns());

  document.addEventListener('keydown', e => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); Palette.el ? Palette.close() : Palette.open(); }
    if (e.key === 'Escape') {
      if (Modal.stack.length && !Palette.el) Modal.close();
      closeDropdowns();
    }
  });

  /* ------------------------------------------------------------------ Menú contraído: etiquetas
     Con el menú en solo íconos, al pasar el mouse (o enfocar con teclado) se muestra el nombre
     de la sección. Va en <body> porque el menú se desplaza y recortaría una etiqueta interna. */
  let etiquetaMenu = null;
  const ocultarEtiquetaMenu = () => { if (etiquetaMenu) etiquetaMenu.hidden = true; };
  function mostrarEtiquetaMenu(link) {
    const contraido = link.closest('.app.is-collapsed') && !window.matchMedia('(max-width: 1024px)').matches;
    const texto = link.querySelector('span')?.textContent.trim();
    if (!contraido || !texto) { ocultarEtiquetaMenu(); return; }
    if (!etiquetaMenu) {
      etiquetaMenu = document.createElement('div');
      etiquetaMenu.className = 'etiqueta-menu';
      etiquetaMenu.setAttribute('role', 'tooltip');
      document.body.appendChild(etiquetaMenu);
    }
    const cuenta = link.querySelector('.nav-count')?.textContent.trim();
    etiquetaMenu.innerHTML = escapeHtml(texto) + (cuenta ? `<span>${escapeHtml(cuenta)}</span>` : '');
    const r = link.getBoundingClientRect();
    etiquetaMenu.style.top = `${r.top + r.height / 2}px`;
    etiquetaMenu.style.left = `${r.right + 12}px`;
    etiquetaMenu.hidden = false;
  }
  document.addEventListener('mouseover', e => {
    const link = e.target.closest('.sidebar .nav-link');
    if (link) mostrarEtiquetaMenu(link);
  });
  document.addEventListener('mouseout', e => {
    const link = e.target.closest('.sidebar .nav-link');
    if (link && !link.contains(e.relatedTarget)) ocultarEtiquetaMenu();
  });
  document.addEventListener('focusin', e => {
    const link = e.target.closest('.sidebar .nav-link');
    if (link) mostrarEtiquetaMenu(link); else ocultarEtiquetaMenu();
  });
  document.addEventListener('scroll', ocultarEtiquetaMenu, true);
  document.addEventListener('click', ocultarEtiquetaMenu);

  /* ------------------------------------------------------------------ Notificaciones */
  document.addEventListener('em:dropdown-open', async e => {
    const wrap = e.target;
    const body = $('[data-notifs-url]', e.detail.menu);
    if (!body || body.dataset.loaded) return;
    body.dataset.loaded = '1';
    try {
      const res = await fetch(body.dataset.notifsUrl, { headers: AJAX });
      body.innerHTML = await res.text();
      const dot = $('.icon-btn .dot', wrap);
      if (dot) { dot.remove(); post(body.dataset.readUrl).catch(() => {}); }
    } catch (err) { body.innerHTML = '<p class="muted small" style="padding:16px 0">No se pudieron cargar.</p>'; }
  });

  /* ------------------------------------------------------------------ Arranque */
  document.addEventListener('DOMContentLoaded', () => {
    // El menú contraído se aplica en layouts/app.html, antes de dibujar la página.
    // Con solo íconos el texto queda oculto: cada enlace conserva su nombre para lectores de pantalla.
    $$('.sidebar .nav-link').forEach(l => {
      const texto = l.querySelector('span')?.textContent.trim();
      if (texto && !l.hasAttribute('aria-label')) l.setAttribute('aria-label', texto);
    });
    $$('[data-theme-icon]').forEach(i => { i.className = document.documentElement.dataset.theme === 'dark' ? 'ph ph-sun' : 'ph ph-moon-stars'; });

    const topbar = $('.topbar');
    if (topbar) {
      const onScroll = () => topbar.classList.toggle('is-scrolled', window.scrollY > 4);
      window.addEventListener('scroll', onScroll, { passive: true });
      onScroll();
    }

    const msgs = $('#django-messages');
    if (msgs) JSON.parse(msgs.textContent).forEach(m => toast(m.text, m.type));
    flushPendingToast();

    init(document);

    // Abre un modal indicado en la URL (?abrir=/ruta/)
    const abrir = new URLSearchParams(location.search).get('abrir');
    if (abrir && abrir.startsWith('/')) Modal.open(abrir);
  });

  window.EM = { toast, toastNextPage, modal: Modal, confirm: confirmDialog, post, csrf, init, escapeHtml, handleJson, setTheme, palette: Palette };
})();
