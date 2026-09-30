const { spawn } = require('child_process');
const fs = require('fs');

async function main() {
  const chromePath = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
  const port = 9240;
  const tempProfile = "C:\\Users\\ABHISHEK RAJ KUMAR\\.gemini\\antigravity\\brain\\32552837-0cef-4a50-9b7f-4bb84f843151\\scratch\\cdp_profile_ops_mobile";
  
  const chromeProc = spawn(chromePath, [
    '--headless=new',
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${tempProfile}`,
    '--window-size=390,844',
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

    await send('Page.navigate', { url: 'http://127.0.0.1:8000/dashboard/authority.html' });
    await new Promise(r => setTimeout(r, 2500));

    // Capture Mobile Viewport (Dark Mode)
    const shotMobile = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync("C:\\Users\\ABHISHEK RAJ KUMAR\\.gemini\\antigravity\\brain\\32552837-0cef-4a50-9b7f-4bb84f843151\\authority_ops_mobile_dark.png", Buffer.from(shotMobile.data, 'base64'));
    console.log('Saved authority_ops_mobile_dark.png');

    ws.close();
  } catch (err) {
    console.error('Error during mobile verification:', err);
  } finally {
    chromeProc.kill();
  }
}

main();
