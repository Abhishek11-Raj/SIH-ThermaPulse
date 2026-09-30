const { spawn } = require('child_process');
const fs = require('fs');

async function main() {
  const chromePath = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
  const port = 9235;
  const tempProfile = "C:\\Users\\ABHISHEK RAJ KUMAR\\.gemini\\antigravity\\brain\\32552837-0cef-4a50-9b7f-4bb84f843151\\scratch\\cdp_profile_headings";
  
  const chromeProc = spawn(chromePath, [
    '--headless=new',
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${tempProfile}`,
    '--window-size=1280,900',
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

    // Capture Ward 12
    const h12 = await send('Runtime.evaluate', {
      expression: `({
        text: document.getElementById('hero-headline').innerText,
        height: document.getElementById('hero-headline').offsetHeight,
        lines: document.getElementById('hero-headline').innerText.split('\\n')
      })`,
      returnByValue: true
    });
    console.log('Ward 12 Heading:', h12.result.value);

    const shot12 = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync("C:\\Users\\ABHISHEK RAJ KUMAR\\.gemini\\antigravity\\brain\\32552837-0cef-4a50-9b7f-4bb84f843151\\citizen_heading_ward12.png", Buffer.from(shot12.data, 'base64'));

    // Switch to Ward 15
    await send('Runtime.evaluate', { expression: "switchWard('WARD-15');" });
    await new Promise(r => setTimeout(r, 600));

    const h15 = await send('Runtime.evaluate', {
      expression: `({
        text: document.getElementById('hero-headline').innerText,
        height: document.getElementById('hero-headline').offsetHeight,
        lines: document.getElementById('hero-headline').innerText.split('\\n')
      })`,
      returnByValue: true
    });
    console.log('Ward 15 Heading:', h15.result.value);

    const shot15 = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync("C:\\Users\\ABHISHEK RAJ KUMAR\\.gemini\\antigravity\\brain\\32552837-0cef-4a50-9b7f-4bb84f843151\\citizen_heading_ward15.png", Buffer.from(shot15.data, 'base64'));

    // Switch to Ward 22
    await send('Runtime.evaluate', { expression: "switchWard('WARD-22');" });
    await new Promise(r => setTimeout(r, 600));

    const h22 = await send('Runtime.evaluate', {
      expression: `({
        text: document.getElementById('hero-headline').innerText,
        height: document.getElementById('hero-headline').offsetHeight,
        lines: document.getElementById('hero-headline').innerText.split('\\n')
      })`,
      returnByValue: true
    });
    console.log('Ward 22 Heading:', h22.result.value);

    const shot22 = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync("C:\\Users\\ABHISHEK RAJ KUMAR\\.gemini\\antigravity\\brain\\32552837-0cef-4a50-9b7f-4bb84f843151\\citizen_heading_ward22.png", Buffer.from(shot22.data, 'base64'));

    // Switch to Ward 08
    await send('Runtime.evaluate', { expression: "switchWard('WARD-08');" });
    await new Promise(r => setTimeout(r, 600));

    const h08 = await send('Runtime.evaluate', {
      expression: `({
        text: document.getElementById('hero-headline').innerText,
        height: document.getElementById('hero-headline').offsetHeight,
        lines: document.getElementById('hero-headline').innerText.split('\\n')
      })`,
      returnByValue: true
    });
    console.log('Ward 08 Heading:', h08.result.value);

    const shot08 = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync("C:\\Users\\ABHISHEK RAJ KUMAR\\.gemini\\antigravity\\brain\\32552837-0cef-4a50-9b7f-4bb84f843151\\citizen_heading_ward08.png", Buffer.from(shot08.data, 'base64'));

    ws.close();
  } catch (err) {
    console.error('Error during verification:', err);
  } finally {
    chromeProc.kill();
  }
}

main();
