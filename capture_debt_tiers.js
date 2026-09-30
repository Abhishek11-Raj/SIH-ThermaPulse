const { spawn } = require('child_process');
const fs = require('fs');

async function main() {
  const chromePath = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
  const port = 9232;
  const tempProfile = "C:\\Users\\ABHISHEK RAJ KUMAR\\.gemini\\antigravity\\brain\\32552837-0cef-4a50-9b7f-4bb84f843151\\scratch\\cdp_profile_tiers";
  
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

    // 1. Red Shade (Ward 12, 96% Thermal Debt, Dark Mode)
    const shotRedDark = await send('Page.captureScreenshot', { format: 'png' });
    const redDarkPath = "C:\\Users\\ABHISHEK RAJ KUMAR\\.gemini\\antigravity\\brain\\32552837-0cef-4a50-9b7f-4bb84f843151\\citizen_hero_red_dark.png";
    fs.writeFileSync(redDarkPath, Buffer.from(shotRedDark.data, 'base64'));
    console.log('Saved citizen_hero_red_dark.png');

    // 2. Switch to Ward 08 (Suburban South, 8% Thermal Debt -> Green Shade!)
    await send('Runtime.evaluate', { expression: "switchWard('WARD-08');" });
    await new Promise(r => setTimeout(r, 800));

    const shotGreenDark = await send('Page.captureScreenshot', { format: 'png' });
    const greenDarkPath = "C:\\Users\\ABHISHEK RAJ KUMAR\\.gemini\\antigravity\\brain\\32552837-0cef-4a50-9b7f-4bb84f843151\\citizen_hero_green_dark.png";
    fs.writeFileSync(greenDarkPath, Buffer.from(shotGreenDark.data, 'base64'));
    console.log('Saved citizen_hero_green_dark.png');

    // 3. Switch to Light Mode with Green Shade (8% Thermal Debt)
    await send('Runtime.evaluate', { expression: 'toggleTheme();' });
    await new Promise(r => setTimeout(r, 800));

    const shotGreenLight = await send('Page.captureScreenshot', { format: 'png' });
    const greenLightPath = "C:\\Users\\ABHISHEK RAJ KUMAR\\.gemini\\antigravity\\brain\\32552837-0cef-4a50-9b7f-4bb84f843151\\citizen_hero_green_light.png";
    fs.writeFileSync(greenLightPath, Buffer.from(shotGreenLight.data, 'base64'));
    console.log('Saved citizen_hero_green_light.png');

    // 4. Open Diagnosis Modal to showcase the live simulator
    await send('Runtime.evaluate', { expression: 'openDiagnosisModal();' });
    await new Promise(r => setTimeout(r, 600));

    const shotModal = await send('Page.captureScreenshot', { format: 'png' });
    const modalPath = "C:\\Users\\ABHISHEK RAJ KUMAR\\.gemini\\antigravity\\brain\\32552837-0cef-4a50-9b7f-4bb84f843151\\citizen_hero_modal_simulator.png";
    fs.writeFileSync(modalPath, Buffer.from(shotModal.data, 'base64'));
    console.log('Saved citizen_hero_modal_simulator.png');

    ws.close();
  } catch (err) {
    console.error('Error during tier capture:', err);
  } finally {
    chromeProc.kill();
  }
}

main();
