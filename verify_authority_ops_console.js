const { spawn } = require('child_process');
const fs = require('fs');

async function main() {
  const chromePath = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
  const port = 9238;
  const tempProfile = "C:\\Users\\ABHISHEK RAJ KUMAR\\.gemini\\antigravity\\brain\\32552837-0cef-4a50-9b7f-4bb84f843151\\scratch\\cdp_profile_ops_console";
  
  const chromeProc = spawn(chromePath, [
    '--headless=new',
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${tempProfile}`,
    '--window-size=1440,1100',
    '--disable-gpu',
    '--no-sandbox',
    'about:blank'
  ]);

  await new Promise(r => setTimeout(r, 2000));

  try {
    const listRes = await fetch(`http://127.0.0.1:${port}/json/list`).then(r => r.json());
    const target = listRes.find(t => t.type === 'page') || listRes[0];
    const ws = new WebSocket(target.webSocketDebuggerUrl);
    await new Promise((resolve, reject) => {
      ws.onopen = resolve;
      ws.onerror = reject;
    });

    let msgId = 1;
    function send(method, params = {}) {
      return new Promise((resolve, reject) => {
        const id = msgId++;
        const handler = (event) => {
          const data = JSON.parse(event.data);
          if (data.id === id) {
            ws.removeEventListener('message', handler);
            if (data.error) reject(data.error);
            else resolve(data.result);
          }
        };
        ws.addEventListener('message', handler);
        ws.send(JSON.stringify({ id, method, params }));
      });
    }

    await send('Runtime.enable');
    await send('Page.enable');

    console.log('Navigating to http://127.0.0.1:8000/dashboard/authority.html ...');
    await send('Page.navigate', { url: 'http://127.0.0.1:8000/dashboard/authority.html' });
    await new Promise(r => setTimeout(r, 2500));

    // Ensure pure Dark Mode for first capture
    await send('Runtime.evaluate', { expression: "localStorage.setItem('keshav_theme', 'dark'); document.documentElement.classList.add('dark'); state.theme = 'dark'; simulateEdgeCaseState('LIVE');" });
    await new Promise(r => setTimeout(r, 600));

    // Capture 1: Main Desktop Command Console View (Dark Mode)
    const shot1 = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync("C:\\Users\\ABHISHEK RAJ KUMAR\\.gemini\\antigravity\\brain\\32552837-0cef-4a50-9b7f-4bb84f843151\\authority_ops_desktop_dark.png", Buffer.from(shot1.data, 'base64'));
    console.log('Saved authority_ops_desktop_dark.png');

    // Capture 2: Open Slide-Over Ward Drawer
    await send('Runtime.evaluate', { expression: "openWardDrawer('WARD-12');" });
    await new Promise(r => setTimeout(r, 500));
    const shot2 = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync("C:\\Users\\ABHISHEK RAJ KUMAR\\.gemini\\antigravity\\brain\\32552837-0cef-4a50-9b7f-4bb84f843151\\authority_ops_ward_drawer.png", Buffer.from(shot2.data, 'base64'));
    console.log('Saved authority_ops_ward_drawer.png');

    // Capture 3: Close Drawer & Open Governed Action Modal
    await send('Runtime.evaluate', { expression: "closeWardDrawer(); openGovernedActionModal('DISPATCH_WARD', 'WARD-12');" });
    await new Promise(r => setTimeout(r, 500));
    const shot3 = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync("C:\\Users\\ABHISHEK RAJ KUMAR\\.gemini\\antigravity\\brain\\32552837-0cef-4a50-9b7f-4bb84f843151\\authority_ops_governed_modal.png", Buffer.from(shot3.data, 'base64'));
    console.log('Saved authority_ops_governed_modal.png');

    // Capture 4: Switch to Light Mode
    await send('Runtime.evaluate', { expression: "closeGovernedActionModal(); localStorage.setItem('keshav_theme', 'light'); document.documentElement.classList.remove('dark'); state.theme = 'light'; simulateEdgeCaseState('LIVE');" });
    await new Promise(r => setTimeout(r, 600));
    const shot4 = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync("C:\\Users\\ABHISHEK RAJ KUMAR\\.gemini\\antigravity\\brain\\32552837-0cef-4a50-9b7f-4bb84f843151\\authority_ops_light_stale.png", Buffer.from(shot4.data, 'base64'));
    console.log('Saved authority_ops_light_stale.png');

    ws.close();
  } catch (err) {
    console.error('Error during console verification:', err);
  } finally {
    chromeProc.kill();
  }
}

main();
