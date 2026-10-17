/* Utilidades compartidas por las pantallas en vivo (invitados, DJ y proyector). */
(() => {
  'use strict';

  /** WebSocket que se reconecta solo (con espera exponencial) y mantiene viva la conexión. */
  function conexion(ruta, { alMensaje, alCambiarEstado } = {}) {
    const url = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}${ruta}`;
    let ws = null;
    let intentos = 0;
    let latido = null;
    let cerrada = false;
    let espera = null;

    const conectar = () => {
      clearTimeout(espera);
      if (ws && ws.readyState <= 1) return;
      ws = new WebSocket(url);
      ws.onopen = () => {
        const reconexion = intentos > 0;
        intentos = 0;
        alCambiarEstado && alCambiarEstado(true, reconexion);
        clearInterval(latido);
        latido = setInterval(() => { if (ws.readyState === 1) ws.send('ping'); }, 25000);
      };
      ws.onmessage = e => {
        if (e.data === 'pong') return;
        try { alMensaje && alMensaje(JSON.parse(e.data)); } catch (err) { /* mensaje inválido */ }
      };
      ws.onclose = () => {
        clearInterval(latido);
        alCambiarEstado && alCambiarEstado(false);
        if (cerrada) return;
        intentos += 1;
        espera = setTimeout(conectar, Math.min(15000, 800 * 2 ** intentos));
      };
      ws.onerror = () => ws.close();
    };

    document.addEventListener('visibilitychange', () => { if (!document.hidden) conectar(); });
    window.addEventListener('online', conectar);
    conectar();
    return { cerrar() { cerrada = true; ws && ws.close(); } };
  }

  function csrf() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : '';
  }

  async function enviarJSON(url, datos = {}) {
    const res = await fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
      body: JSON.stringify(datos),
    });
    let json = {};
    try { json = await res.json(); } catch (e) { json = { ok: false, msg: 'Respuesta inesperada del servidor.' }; }
    return json;
  }

  /**
   * Reduce la foto en el celular antes de subirla (lado mayor de 1600 px, JPEG):
   * pesa una fracción del original y sube rápido aunque el internet del salón sea lento.
   * Si el navegador no puede leerla, se manda el archivo original y el servidor decide.
   */
  async function comprimirImagen(archivo, lado = 1600, calidad = 0.85) {
    let fuente;
    try {
      fuente = await createImageBitmap(archivo, { imageOrientation: 'from-image' });
    } catch (e) {
      fuente = await new Promise((ok, mal) => {
        const img = new Image();
        img.onload = () => ok(img);
        img.onerror = mal;
        img.src = URL.createObjectURL(archivo);
      });
    }
    const escala = Math.min(1, lado / Math.max(fuente.width, fuente.height));
    const lienzo = document.createElement('canvas');
    lienzo.width = Math.round(fuente.width * escala);
    lienzo.height = Math.round(fuente.height * escala);
    lienzo.getContext('2d').drawImage(fuente, 0, 0, lienzo.width, lienzo.height);
    const blob = await new Promise(ok => lienzo.toBlob(ok, 'image/jpeg', calidad));
    if (!blob) throw new Error('No se pudo procesar la imagen');
    return blob;
  }

  /** POST con archivo y avance de subida (fetch no informa el progreso). */
  function subir(url, datos, alAvanzar) {
    return new Promise(resolver => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', url);
      xhr.withCredentials = true;
      xhr.setRequestHeader('X-CSRFToken', csrf());
      xhr.upload.onprogress = e => { if (e.lengthComputable && alAvanzar) alAvanzar(e.loaded / e.total); };
      xhr.onload = () => {
        let json;
        try { json = JSON.parse(xhr.responseText); } catch (e) { json = { ok: false, msg: 'Respuesta inesperada del servidor.' }; }
        resolver(json);
      };
      xhr.onerror = () => resolver({ ok: false, msg: 'Sin conexión. Revisa tu internet e intenta de nuevo.' });
      xhr.send(datos);
    });
  }

  function escapar(texto) {
    return String(texto ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  function tiempo(seg) {
    seg = Math.max(0, Math.round(seg));
    return `${String(Math.floor(seg / 60)).padStart(2, '0')}:${String(seg % 60).padStart(2, '0')}`;
  }

  function haceCuanto(iso) {
    const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
    if (s < 45) return 'ahora';
    if (s < 3600) return `hace ${Math.round(s / 60)} min`;
    return `hace ${Math.floor(s / 3600)} h`;
  }

  /** Pantalla completa con un botón y su ícono. */
  function pantallaCompleta(boton) {
    if (!boton) return;
    const icono = boton.querySelector('i');
    boton.addEventListener('click', () => {
      if (!document.fullscreenElement) document.documentElement.requestFullscreen?.();
      else document.exitFullscreen?.();
    });
    document.addEventListener('fullscreenchange', () => {
      if (icono) icono.className = document.fullscreenElement ? 'ph ph-corners-in' : 'ph ph-corners-out';
    });
  }

  /** Mantiene la pantalla encendida (proyector / DJ) cuando el navegador lo permite. */
  async function mantenerEncendida() {
    try {
      if (!('wakeLock' in navigator)) return;
      let bloqueo = await navigator.wakeLock.request('screen');
      document.addEventListener('visibilitychange', async () => {
        if (!document.hidden && bloqueo.released) bloqueo = await navigator.wakeLock.request('screen');
      });
    } catch (e) { /* no soportado */ }
  }

  window.EnVivo = { conexion, enviarJSON, comprimirImagen, subir, escapar, tiempo, haceCuanto, pantallaCompleta, mantenerEncendida, csrf };
})();
