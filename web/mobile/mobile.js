/* Interface instalável. Nenhum cadastro ou documento é salvo no cache offline. */
async function refreshBrand() {
  const name = document.getElementById('brand-name');
  if (!name || document.hidden || !navigator.onLine) return;
  try {
    const response = await fetch('/identidade', {cache:'no-store'});
    if (!response.ok || !response.headers.get('Content-Type')?.includes('application/json')) return;
    const shop = await response.json();
    name.textContent = shop.name; document.title = shop.name + ' · Gestão';
    const box = document.getElementById('brand-logo');
    box.replaceChildren();
    if (typeof shop.logo === 'string' && shop.logo.startsWith('data:image/png;base64,')) {
      const logo = document.createElement('img'); logo.alt = 'Logo da confeitaria'; logo.src = shop.logo; box.append(logo);
    } else box.textContent = '🧁';
  } catch (_) { /* Manter o cabeçalho atual quando a conexão falhar. */ }
}
refreshBrand(); setInterval(refreshBrand, 15000);
window.addEventListener('focus', refreshBrand);
if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(() => {});
let installation;
const install = document.getElementById('install');
window.addEventListener('beforeinstallprompt', event => {
  event.preventDefault(); installation = event;
  if (install) install.hidden = false;
});
install?.addEventListener('click', async () => {
  if (installation) { await installation.prompt(); await installation.userChoice; installation = undefined; install.hidden = true; }
});
document.getElementById('help')?.addEventListener('click', () => { document.getElementById('instructions').hidden = false; });
document.getElementById('close-help')?.addEventListener('click', () => { document.getElementById('instructions').hidden = true; });
window.addEventListener('appinstalled', () => { if (install) install.hidden = true; });
function connectivity() { const banner = document.getElementById('offline'); if (banner) banner.hidden = navigator.onLine; }
window.addEventListener('online', () => { connectivity(); const frame = document.getElementById('system'); if (frame) frame.src = '/sistema/'; });
window.addEventListener('offline', connectivity); connectivity();
setInterval(async () => {
  if (!document.getElementById('system') || !navigator.onLine) return;
  try { const response = await fetch('/sistema/_stcore/health', {cache: 'no-store'}); if (response.status === 401) window.location.replace('/entrar'); } catch (_) { /* O aviso de conexão é controlado pelo navegador. */ }
}, 60000);
