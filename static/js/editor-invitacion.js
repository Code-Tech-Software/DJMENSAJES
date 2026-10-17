/* ==========================================================================
   Editor de invitaciones
   - Los textos, el color, la letra y las secciones visibles se reflejan al
     instante en la vista previa (postMessage al iframe, sin recargar).
   - Todo se guarda solo unos instantes después de dejar de escribir.
   - Plantilla, imágenes, música, lugares, personas y galería recargan la vista
     previa conservando la posición.
   ========================================================================== */
(() => {
  'use strict';

  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];

  const editor = $('#editor');
  const form = $('#form-editor');
  const iframe = $('#vista');
  const marco = $('#marco');
  const marcoEscala = $('#marco-escala');
  const lienzo = $('#lienzo');
  const vista = $('#editor-vista');
  const raiz = document.documentElement;
  const estado = $('#estado-guardado');
  const paletas = JSON.parse($('#datos-paletas').textContent);
  const coloresBase = JSON.parse($('#datos-colores').textContent);
  const ORIGEN = location.origin;

  // Campos que se reflejan al instante en la vista previa
  const EN_VIVO = ['titulo', 'nombres', 'texto_sobre', 'frase', 'aviso', 'hashtag', 'dress_code', 'mesa_regalos', 'musica_titulo'];
  // A qué parte de la invitación lleva cada sección del editor
  const DESTINO = {
    diseno: 'portada', portada: 'portada', mensaje: 'mensaje', lugares: 'lugares',
    personas: 'personas', galeria: 'galeria', detalles: 'detalles', confirmacion: 'confirmar',
  };

  /* ------------------------------------------------------------ Vista previa */
  let vistaLista = false;
  let scrollVista = 0;
  let seccionPendiente = null;

  const aVista = mensaje => {
    if (iframe.contentWindow) iframe.contentWindow.postMessage(mensaje, ORIGEN);
  };

  function valoresEnVivo() {
    const campos = {};
    EN_VIVO.forEach(n => { if (form.elements[n]) campos[n] = form.elements[n].value; });
    campos.color_principal = form.elements.color_principal.value;
    const tipo = form.querySelector('input[name="tipografia"]:checked');
    if (tipo) campos.tipografia = tipo.value;
    $$('input[type="checkbox"][name^="mostrar_"]', form).forEach(c => { campos[c.name] = c.checked; });
    return campos;
  }

  window.addEventListener('message', e => {
    if (e.origin !== ORIGEN || e.source !== iframe.contentWindow) return;
    const d = e.data || {};
    if (d.em === 'listo') {
      vistaLista = true;
      aVista({ em: 'actualizar', campos: valoresEnVivo() });
      if (seccionPendiente) { aVista({ em: 'ir', seccion: seccionPendiente, suave: false }); seccionPendiente = null; }
      else if (scrollVista) aVista({ em: 'scroll', y: scrollVista });
      else if (actual > 0) aVista({ em: 'ir', seccion: DESTINO[pasos[actual].dataset.paso], suave: false });
    }
    if (d.em === 'scroll') scrollVista = d.y;
  });

  function recargarVista(seccion) {
    vistaLista = false;
    seccionPendiente = seccion || null;
    const url = new URL(iframe.src, ORIGEN);
    url.searchParams.set('preview', '1');
    url.searchParams.set('t', Date.now());
    iframe.src = url.toString();
  }
  $('#recargar-vista').addEventListener('click', () => recargarVista());
  $$('[data-ver-sobre]').forEach(b => b.addEventListener('click', () => {
    asegurarVista();
    aVista({ em: 'sobre' });
  }));

  /* Celular / computadora: el marco conserva su tamaño real y se escala para caber */
  const DIMENSIONES = { celular: [392, 820], escritorio: [1280, 830] };
  let dispositivo = 'celular';
  function ajustarDispositivo() {
    const estilo = getComputedStyle(lienzo);
    const ancho = lienzo.clientWidth - parseFloat(estilo.paddingLeft) - parseFloat(estilo.paddingRight);
    const alto = lienzo.clientHeight - parseFloat(estilo.paddingTop) - parseFloat(estilo.paddingBottom);
    if (ancho <= 0 || alto <= 0) return; // la vista está oculta: se ajusta al mostrarse
    let [w, h] = DIMENSIONES[dispositivo];
    // En un celular, la vista de celular ocupa la pantalla tal cual
    const pantalla = dispositivo === 'celular' && window.innerWidth <= 480;
    if (pantalla) { w = ancho; h = alto; }
    marco.className = `marco marco--${dispositivo}${pantalla ? ' marco--pantalla' : ''}`;
    const escala = Math.max(.2, Math.min(ancho / w, alto / h, 1));
    marco.style.width = `${w}px`;
    marco.style.height = `${h}px`;
    marco.style.transform = escala < 1 ? `scale(${escala})` : '';
    marcoEscala.style.width = `${w * escala}px`;
    marcoEscala.style.height = `${h * escala}px`;
  }
  $('#dispositivos').addEventListener('click', e => {
    const b = e.target.closest('[data-dispositivo]');
    if (!b) return;
    dispositivo = b.dataset.dispositivo;
    $$('[data-dispositivo]').forEach(x => x.setAttribute('aria-pressed', x === b));
    ajustarDispositivo();
  });
  if ('ResizeObserver' in window) new ResizeObserver(ajustarDispositivo).observe(lienzo);
  else window.addEventListener('resize', ajustarDispositivo);

  /* Mostrar, ocultar y ampliar la vista previa */
  const esMovil = () => window.matchMedia('(max-width: 1100px)').matches;
  const botonVista = $('#alternar-vista');
  const botonAmpliar = $('#ampliar-vista');

  function llevarVistaASeccion() {
    requestAnimationFrame(() => {
      ajustarDispositivo();
      if (pasos[actual]) aVista({ em: 'ir', seccion: DESTINO[pasos[actual].dataset.paso], suave: false });
    });
  }

  function mostrarVista(mostrar) {
    raiz.classList.toggle('editor-sin-vista', !mostrar);
    botonVista.setAttribute('aria-pressed', mostrar);
    try { localStorage.setItem('em-editor-vista', mostrar ? 'visible' : 'oculta'); } catch (e) { /* sin almacenamiento */ }
    if (mostrar) llevarVistaASeccion();
  }

  function ampliarVista(ampliar) {
    vista.classList.toggle('is-ampliada', ampliar);
    document.body.style.overflow = ampliar ? 'hidden' : '';
    botonAmpliar.querySelector('i').className = ampliar ? 'ph ph-corners-in' : 'ph ph-corners-out';
    botonAmpliar.dataset.tip = ampliar ? 'Reducir' : 'Ver en grande';
    botonAmpliar.setAttribute('aria-label', botonAmpliar.dataset.tip);
    $('#cerrar-vista').dataset.tip = ampliar ? 'Cerrar' : 'Ocultar';
    llevarVistaASeccion();
  }

  // Se asegura de que la vista previa esté a la vista (p. ej. para ver el sobre)
  function asegurarVista() {
    if (esMovil()) { if (!vista.classList.contains('is-ampliada')) ampliarVista(true); }
    else if (raiz.classList.contains('editor-sin-vista')) mostrarVista(true);
  }

  botonVista.addEventListener('click', () => {
    if (esMovil()) ampliarVista(true);
    else mostrarVista(raiz.classList.contains('editor-sin-vista'));
  });
  $('#ver-previa').addEventListener('click', () => (esMovil() ? ampliarVista(true) : mostrarVista(true)));
  botonAmpliar.addEventListener('click', () => ampliarVista(!vista.classList.contains('is-ampliada')));
  $('#cerrar-vista').addEventListener('click', () => {
    if (vista.classList.contains('is-ampliada')) ampliarVista(false);
    else mostrarVista(false);
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && vista.classList.contains('is-ampliada') && !EM.modal.stack.length) ampliarVista(false);
  });

  /* ------------------------------------------------------------ Secciones */
  const pasos = $$('[data-paso]', form);
  const botones = $$('[data-ir]');
  let actual = 0;

  const nav = $('#editor-nav');

  // Centra el paso activo cuando los pasos no caben (celulares), sin mover la página
  function centrarBoton(b) {
    if (nav.scrollWidth <= nav.clientWidth) return;
    const rb = b.getBoundingClientRect();
    const rn = nav.getBoundingClientRect();
    nav.scrollBy({ left: (rb.left + rb.width / 2) - (rn.left + rn.width / 2), behavior: 'smooth' });
  }

  function irA(i, inicio = false) {
    actual = Math.max(0, Math.min(i, pasos.length - 1));
    pasos.forEach((p, j) => { p.hidden = j !== actual; });
    botones.forEach((b, j) => {
      b.classList.toggle('is-active', j === actual);
      if (j === actual) b.setAttribute('aria-current', 'step'); else b.removeAttribute('aria-current');
    });
    centrarBoton(botones[actual]);
    form.scrollTop = 0;
    // En celulares se desplaza la página completa: se vuelve al inicio de la sección
    if (!inicio && esMovil() && form.getBoundingClientRect().top < 0) {
      window.scrollTo({ top: window.scrollY + form.getBoundingClientRect().top - nav.offsetHeight - 70, behavior: 'smooth' });
    }
    $('[data-paso-anterior]').style.visibility = actual === 0 ? 'hidden' : 'visible';
    const sig = $('[data-paso-siguiente]');
    sig.hidden = actual === pasos.length - 1;
    $('#editor-progreso').textContent = `${actual + 1} de ${pasos.length}`;
    aVista({ em: 'ir', seccion: DESTINO[pasos[actual].dataset.paso] });
    try { history.replaceState(null, '', `#${pasos[actual].dataset.paso}`); } catch (e) { /* */ }
  }
  botones.forEach((b, i) => b.addEventListener('click', () => irA(i)));
  $('[data-paso-anterior]').addEventListener('click', () => irA(actual - 1));
  $('[data-paso-siguiente]').addEventListener('click', () => irA(actual + 1));

  /* ------------------------------------------------------------ Estilo */
  function plantillaActual() {
    const r = form.querySelector('input[name="plantilla"]:checked');
    return r ? r.value : 'elegante';
  }

  function pintarPaleta() {
    const actualColor = form.elements.color_principal.value.toUpperCase();
    $('#paleta').innerHTML = (paletas[plantillaActual()] || []).map(c =>
      `<button type="button" data-color="${c}" style="background:${c}" class="${c.toUpperCase() === actualColor ? 'is-active' : ''}" aria-label="Color ${c}"></button>`).join('');
  }

  function ponerColor(color, guardar = true) {
    form.elements.color_principal.value = color.toUpperCase();
    $('#selector-color').value = color;
    aVista({ em: 'actualizar', campos: { color_principal: color } });
    $$('#paleta button').forEach(b => b.classList.toggle('is-active', b.dataset.color.toUpperCase() === color.toUpperCase()));
    if (guardar) programarGuardado();
  }

  $('#paleta').addEventListener('click', e => {
    const b = e.target.closest('[data-color]');
    if (b) ponerColor(b.dataset.color);
  });
  $('#selector-color').addEventListener('input', e => ponerColor(e.target.value));

  function pintarMuestras() {
    const texto = form.elements.nombres.value.trim() || form.elements.nombres.placeholder;
    $$('[data-muestra]').forEach(m => { m.textContent = texto; });
  }

  /* Sugerencias de texto (en la hoja y dentro de los modales) */
  document.addEventListener('click', e => {
    const b = e.target.closest('[data-rellenar]');
    if (!b) return;
    const campo = document.getElementById(b.dataset.rellenar);
    if (!campo) return;
    campo.value = b.textContent.trim();
    campo.dispatchEvent(new Event('input', { bubbles: true }));
    const siguiente = b.dataset.luego && document.getElementById(b.dataset.luego);
    (siguiente && !siguiente.value.trim() ? siguiente : campo).focus();
  });

  // Marca la sugerencia elegida y actualiza el "Así se verá" de personas especiales
  function pintarMencionPrevia(caja) {
    const titulo = document.getElementById(caja.dataset.titulo);
    const nombres = document.getElementById(caja.dataset.nombres);
    if (!titulo || !nombres) return;
    const lista = nombres.value.split('\n').map(n => n.trim()).filter(Boolean);
    caja.querySelector('[data-mp-titulo]').textContent = titulo.value.trim() || 'Padrinos de anillos';
    caja.querySelector('[data-mp-nombres]').innerHTML = (lista.length ? lista : ['Nombre y apellido'])
      .map(n => `<span>${EM.escapeHtml(n)}</span>`).join('');
    caja.classList.toggle('is-vacia', !titulo.value.trim() && !lista.length);
  }
  document.addEventListener('input', e => {
    const id = e.target.id;
    if (id) {
      const valor = e.target.value.trim();
      $$(`[data-rellenar="${CSS.escape(id)}"]`).forEach(b => b.classList.toggle('is-active', b.textContent.trim() === valor));
    }
    const caja = e.target.form && e.target.form.querySelector('[data-mencion-previa]');
    if (caja) pintarMencionPrevia(caja);
  });

  /* ------------------------------------------------------------ Cambios */
  form.addEventListener('input', e => {
    const n = e.target.name;
    if (!n) return;
    if (EN_VIVO.includes(n)) aVista({ em: 'actualizar', campos: { [n]: e.target.value } });
    if (n === 'nombres') pintarMuestras();
    if (n === 'color_principal') {
      const v = e.target.value.trim();
      if (/^#[0-9a-f]{6}$/i.test(v)) ponerColor(v, false);
    }
    if (e.target.type !== 'file' && e.target.type !== 'radio' && e.target.type !== 'checkbox') programarGuardado();
  });

  form.addEventListener('change', e => {
    const n = e.target.name;
    if (!n) return;
    if (n === 'plantilla') {
      editor.dataset.plantilla = e.target.value;
      ponerColor(coloresBase[e.target.value], false);
      pintarPaleta();
      guardarAhora();
      return;
    }
    if (n === 'tipografia') aVista({ em: 'actualizar', campos: { tipografia: e.target.value } });
    if (n.startsWith('mostrar_')) aVista({ em: 'actualizar', campos: { [n]: e.target.checked } });
    if (n === 'publicada') {
      const chip = $('#chip-publicada');
      chip.textContent = e.target.checked ? 'Publicada' : 'Borrador';
      chip.className = `chip ${e.target.checked ? 'chip--success' : 'chip--warning'} chip--dot`;
    }
    if (e.target.type === 'file' || e.target.name.endsWith('-clear')) { guardarAhora(); return; }
    if (e.target.type === 'radio' || e.target.type === 'checkbox' || e.target.type === 'date' || e.target.type === 'url') guardarAhora();
  });

  /* ------------------------------------------------------------ Guardado automático */
  let temporizador = null;
  let guardando = false;
  let otraVez = false;

  function ponerEstado(tipo, texto) {
    estado.dataset.estado = tipo;
    estado.querySelector('i').className = { guardando: 'ph ph-spinner-gap', ok: 'ph ph-cloud-check', error: 'ph ph-warning-circle', pendiente: 'ph ph-pencil-simple' }[tipo];
    estado.querySelector('span').textContent = texto;
    estado.title = texto; // visible al pasar el mouse cuando la barra solo muestra el ícono
  }

  function programarGuardado() {
    ponerEstado('pendiente', 'Cambios sin guardar…');
    clearTimeout(temporizador);
    temporizador = setTimeout(guardarAhora, 700);
  }

  function limpiarErrores() {
    $$('.field--error', form).forEach(f => f.classList.remove('field--error'));
    $$('.field__error[data-autoguardado]', form).forEach(x => x.remove());
  }

  function mostrarErrores(errores) {
    let primero = null;
    Object.entries(errores).forEach(([campo, lista]) => {
      const input = form.elements[campo];
      const el = input && (input.length && !input.tagName ? input[0] : input);
      const wrap = el && el.closest('.field');
      if (!wrap) return;
      wrap.classList.add('field--error');
      const small = document.createElement('small');
      small.className = 'field__error';
      small.dataset.autoguardado = '1';
      small.innerHTML = `<i class="ph ph-warning-circle"></i>${EM.escapeHtml(lista[0])}`;
      wrap.appendChild(small);
      primero = primero || wrap;
    });
    if (primero) {
      const paso = primero.closest('[data-paso]');
      if (paso) irA(pasos.indexOf(paso));
      primero.scrollIntoView({ block: 'center', behavior: 'smooth' });
    }
  }

  async function guardarAhora() {
    clearTimeout(temporizador);
    temporizador = null;
    if (guardando) { otraVez = true; return; }
    guardando = true;
    ponerEstado('guardando', 'Guardando…');
    try {
      const res = await fetch(form.action, {
        method: 'POST', body: new FormData(form), credentials: 'same-origin',
        headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': EM.csrf() },
      });
      const datos = await res.json();
      limpiarErrores();
      if (!datos.ok) {
        ponerEstado('error', 'Revisa los campos marcados');
        mostrarErrores(datos.errores || {});
        return;
      }
      ponerEstado('ok', `Guardado · ${datos.hora}`);
      // Los archivos ya se subieron: se limpian para no volver a enviarlos en el siguiente guardado
      $$('input[type="file"][name]', form).forEach(f => { f.value = ''; });
      $$('input[name$="-clear"]', form).forEach(c => {
        if (c.checked) { c.checked = false; c.closest('.dropzone__clear')?.remove(); }
      });
      const audio = $('#musica-previa');
      if (audio) {
        if (datos.musica && audio.getAttribute('src') !== datos.musica) { audio.src = datos.musica; audio.hidden = false; }
        if (!datos.musica) { audio.removeAttribute('src'); audio.hidden = true; }
      }
      if (datos.recargar) recargarVista();
    } catch (err) {
      ponerEstado('error', 'Sin conexión, reintentando…');
      setTimeout(guardarAhora, 4000);
    } finally {
      guardando = false;
      if (otraVez) { otraVez = false; guardarAhora(); }
    }
  }

  // Enter en un campo no recarga la página: solo guarda
  form.addEventListener('submit', e => { e.preventDefault(); guardarAhora(); });

  // Si se sale con cambios pendientes, se envían en segundo plano
  window.addEventListener('beforeunload', () => {
    if (temporizador) { clearTimeout(temporizador); navigator.sendBeacon(form.action, new FormData(form)); }
  });

  /* ------------------------------------------------------------ Listas y galería */
  async function refrescarLista(seccion) {
    const contenedor = document.getElementById(`lista-${seccion}`);
    if (!contenedor) return;
    const res = await fetch(location.pathname, { credentials: 'same-origin' });
    const doc = new DOMParser().parseFromString(await res.text(), 'text/html');
    const nuevo = doc.getElementById(`lista-${seccion}`);
    if (nuevo) contenedor.innerHTML = nuevo.innerHTML;
    contar(seccion);
  }

  // Número de elementos de cada lista, junto a su sección en el menú
  function contar(seccion) {
    const contenedor = document.getElementById(`lista-${seccion}`);
    const insignia = $(`[data-contador="${seccion}"]`);
    if (!contenedor || !insignia) return;
    const n = contenedor.querySelectorAll('.item-lista, figure').length;
    insignia.textContent = n;
    insignia.hidden = n === 0;
  }

  document.addEventListener('em:saved', async e => {
    const seccion = e.detail && e.detail.refrescar;
    if (!seccion) return;
    await refrescarLista(seccion);
    recargarVista(seccion);
  });

  const zonaFotos = $('#subir-fotos-zona');
  $('#subir-fotos').addEventListener('change', async e => {
    const archivos = [...e.target.files];
    if (!archivos.length) return;
    const datos = new FormData();
    archivos.forEach(a => datos.append('imagenes', a));
    zonaFotos.classList.add('is-subiendo');
    zonaFotos.querySelector('strong').textContent = `Subiendo ${archivos.length} foto${archivos.length > 1 ? 's' : ''}…`;
    try {
      const res = await fetch(zonaFotos.dataset.url, {
        method: 'POST', body: datos, credentials: 'same-origin',
        headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': EM.csrf() },
      });
      const json = await res.json();
      if (json.ok === false) EM.toast(json.message, 'error');
      else EM.handleJson(json);
    } catch (err) {
      EM.toast('No se pudieron subir las fotos.', 'error');
    } finally {
      zonaFotos.classList.remove('is-subiendo');
      zonaFotos.querySelector('strong').textContent = 'Arrastra o elige varias fotos';
      e.target.value = '';
    }
  });

  /* ------------------------------------------------------------ Inicio */
  botonVista.setAttribute('aria-pressed', !raiz.classList.contains('editor-sin-vista'));
  pintarPaleta();
  pintarMuestras();
  ajustarDispositivo();
  const inicial = pasos.findIndex(p => p.dataset.paso === location.hash.slice(1));
  irA(inicial >= 0 ? inicial : 0, true);
})();
