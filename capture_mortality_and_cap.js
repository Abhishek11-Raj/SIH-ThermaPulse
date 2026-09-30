const { spawn } = require('child_process');
const fs = require('fs');

async function main() {
  const chromePath = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
  const port = 9234;
  const tempProfile = "C:\\Users\\ABHISHEK RAJ KUMAR\\.gemini\\antigravity\\brain\\32552837-0cef-4a50-9b7f-4bb84f843151\\scratch\\cdp_profile_cap";
  
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

    console.log('Navigating to http://127.0.0.1:8000/dashboard/ ...');
    await send('Page.navigate', { url: 'http://127.0.0.1:8000/dashboard/' });
    await new Promise(r => setTimeout(r, 2500));

    // 1. Red Tier (Ward 12, Critical +38% Hospitalization, +18% Mortality)
    const shotRed = await send('Page.captureScreenshot', { format: 'png' });
    const redPath = "C:\\Users\\ABHISHEK RAJ KUMAR\\.gemini\\antigravity\\brain\\32552837-0cef-4a50-9b7f-4bb84f843151\\citizen_hero_mortality_red.png";
    fs.writeFileSync(redPath, Buffer.from(shotRed.data, 'base64'));
    console.log('Saved citizen_hero_mortality_red.png');

    // 2. Open CAP 1.2 XML Modal
    await send('Runtime.evaluate', { expression: 'openCapModal();' });
    await new Promise(r => setTimeout(r, 800));

    const shotCap = await send('Page.captureScreenshot', { format: 'png' });
    const capPath = "C:\\Users\\ABHISHEK RAJ KUMAR\\.gemini\\antigravity\\brain\\32552837-0cef-4a50-9b7f-4bb84f843151\\citizen_hero_cap_modal.png";
    fs.writeFileSync(capPath, Buffer.from(shotCap.data, 'base64'));
    console.log('Saved citizen_hero_cap_modal.png');

    // Close modal and switch to Ward 08 (Green Tier)
    await send('Runtime.evaluate', { expression: "closeModal(); switchWard('WARD-08');" });
    await new Promise(r => setTimeout(r, 800));

    const shotGreen = await send('Page.captureScreenshot', { format: 'png' });
    const greenPath = "C:\\Users\\ABHISHEK RAJ KUMAR\\.gemini\\antigravity\\brain\\32552837-0cef-4a50-9b7f-4bb84f843151\\citizen_hero_mortality_green.png";
    fs.writeFileSync(greenPath, Buffer.from(shotGreen.data, 'base64'));
    console.log('Saved citizen_hero_mortality_green.png');

    ws.close();
  } catch (err) {
    console.error('Error during capture:', err);
  } finally {
    chromeProc.kill();
  }
}

main();
