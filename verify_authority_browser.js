const { spawn } = require('child_process');
const fs = require('fs');

async function main() {
  const chromePath = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
  const port = 9227;
  const chromeProc = spawn(chromePath, [
    '--headless=new',
    `--remote-debugging-port=${port}`,
    '--window-size=1280,2400',
    '--disable-gpu',
    '--no-sandbox',
    'about:blank'
  ]);

  await new Promise(r => setTimeout(r, 1500));

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
    await new Promise(r => setTimeout(r, 2000));

    // Test toggleTheme() and switchLanguage('hi') on authority.html
    const evalRes = await send('Runtime.evaluate', {
      expression: `
        try {
          toggleTheme(); // switches to light
          switchLanguage('hi'); // switches to hindi
          ({
            success: true,
            theme: window.state?.theme,
            lang: window.state?.lang,
            htmlClass: document.documentElement.className,
            bodyBg: getComputedStyle(document.body).backgroundColor,
            cardBg: getComputedStyle(document.querySelector('.k-card')).backgroundColor,
            title: document.getElementById('hdr-auth-title')?.innerText,
            subDesc: document.getElementById('sub-auth-desc')?.innerText,
            metricTankers: document.getElementById('lbl-metric-tankers')?.innerText,
            metricIcu: document.getElementById('lbl-metric-icu')?.innerText,
            tabOperations: document.getElementById('tab-txt-operations')?.innerText,
            tabTwin: document.getElementById('tab-txt-twin')?.innerText
          });
        } catch(e) {
          ({ success: false, error: e.message, stack: e.stack });
        }
      `,
      returnByValue: true
    });
    console.log('Authority evaluation result:', JSON.stringify(evalRes.result.value, null, 2));

    await new Promise(r => setTimeout(r, 1000));
    const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true });
    fs.writeFileSync('authority_light_hi.png', Buffer.from(shot.data, 'base64'));
    console.log('Saved authority_light_hi.png');

    ws.close();
  } catch (err) {
    console.error('Error during test:', err);
  } finally {
    chromeProc.kill();
  }
}

main();
