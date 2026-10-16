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
      if (icono) icono.className = document.fullscreenElement ? 'ri-fullscreen-exit-line' : 'ri-fullscreen-line';
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

  window.EnVivo = { conexion, enviarJSON, escapar, tiempo, haceCuanto, pantallaCompleta, mantenerEncendida, csrf };
})();
