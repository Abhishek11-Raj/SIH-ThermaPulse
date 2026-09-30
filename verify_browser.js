const { spawn } = require('child_process');

async function main() {
  const chromePath = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
  const port = 9225;
  const chromeProc = spawn(chromePath, [
    '--headless=new',
    `--remote-debugging-port=${port}`,
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

    ws.addEventListener('message', (event) => {
      const data = JSON.parse(event.data);
      if (data.method === 'Runtime.consoleAPICalled') {
        console.log('[BROWSER CONSOLE]', data.params.type, data.params.args.map(a => a.value || a.description).join(' '));
      } else if (data.method === 'Runtime.exceptionThrown') {
        console.error('[BROWSER EXCEPTION]', data.params.exceptionDetails.text, data.params.exceptionDetails.exception?.description);
      }
    });

    await send('Runtime.enable');
    await send('Page.enable');

    console.log('Navigating to http://127.0.0.1:8000/dashboard/ ...');
    await send('Page.navigate', { url: 'http://127.0.0.1:8000/dashboard/' });
    await new Promise(r => setTimeout(r, 2000));

    // Test 1: Check initial state
    let res = await send('Runtime.evaluate', {
      expression: `({
        htmlClass: document.documentElement.className,
        bodyBg: getComputedStyle(document.body).backgroundColor,
        heroHeadline: document.getElementById('hero-headline')?.innerText,
        feelsLike: document.getElementById('hero-temp-feels')?.innerText,
        lang: window.state?.language,
        theme: window.state?.theme
      })`,
      returnByValue: true
    });
    console.log('Initial State:', res.result.value);

    // Test 2: Trigger toggleTheme() to switch to Light Mode
    console.log('\n--- Testing toggleTheme() (to Light Mode) ---');
    res = await send('Runtime.evaluate', {
      expression: `
        try {
          toggleTheme();
          const card = document.querySelector('.k-card');
          const header = document.querySelector('.k-header');
          const body = document.body;
          ({
            success: true,
            htmlClass: document.documentElement.className,
            bodyBg: getComputedStyle(body).backgroundColor,
            cardBg: card ? getComputedStyle(card).backgroundColor : null,
            headerBg: header ? getComputedStyle(header).backgroundColor : null,
            textColor: getComputedStyle(body).color,
            themeState: window.state?.theme,
            themeIcon: document.getElementById('theme-icon')?.innerText
          });
        } catch(e) {
          ({ success: false, error: e.message, stack: e.stack });
        }
      `,
      returnByValue: true
    });
    console.log('After toggleTheme():', res.result.value);

    // Test 3: Trigger switchLanguage('hi')
    console.log('\n--- Testing switchLanguage("hi") ---');
    res = await send('Runtime.evaluate', {
      expression: `
        try {
          switchLanguage('hi');
          ({
            success: true,
            lang: window.state?.language,
            headline: document.getElementById('hero-headline')?.innerText,
            subhead: document.getElementById('hero-subhead')?.innerText,
            threatLabel: document.getElementById('lbl-instant-threat')?.innerText,
            feelsLikeLabel: document.getElementById('lbl-feels-like')?.innerText,
            trajectoryTitle: document.getElementById('hdr-trajectory-title')?.innerText,
            mapTitle: document.getElementById('hdr-map-title')?.innerText,
            reliefTitle: document.getElementById('hdr-relief-title')?.innerText,
            guidanceTitle: document.getElementById('hdr-guidance-title')?.innerText,
            hotspotTitle: document.getElementById('hotspot-title')?.innerText,
            firstGuidanceTileTitle: document.querySelector('#guidance-grid h4')?.innerText,
            btnEnClass: document.getElementById('lang-btn-en')?.className,
            btnHiClass: document.getElementById('lang-btn-hi')?.className
          });
        } catch(e) {
          ({ success: false, error: e.message, stack: e.stack });
        }
      `,
      returnByValue: true
    });
    console.log('After switchLanguage("hi"):', JSON.stringify(res.result.value, null, 2));

    // Capture screenshot of Light Mode + Hindi
    const screenshot = await send('Page.captureScreenshot', { format: 'png' });
    const fs = require('fs');
    fs.writeFileSync('screenshot_light_hi.png', Buffer.from(screenshot.data, 'base64'));
    console.log('Screenshot saved to screenshot_light_hi.png');

    // Test 4: Switch back to dark and en
    console.log('\n--- Testing toggle back to Dark Mode & EN ---');
    res = await send('Runtime.evaluate', {
      expression: `
        try {
          toggleTheme();
          switchLanguage('en');
          ({
            success: true,
            htmlClass: document.documentElement.className,
            bodyBg: getComputedStyle(document.body).backgroundColor,
            lang: window.state?.language,
            theme: window.state?.theme,
            headline: document.getElementById('hero-headline')?.innerText
          });
        } catch(e) {
          ({ success: false, error: e.message });
        }
      `,
      returnByValue: true
    });
    console.log('After reset to Dark & EN:', res.result.value);

    const screenshotDark = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync('screenshot_dark_en.png', Buffer.from(screenshotDark.data, 'base64'));
    console.log('Screenshot saved to screenshot_dark_en.png');

    ws.close();
  } catch (err) {
    console.error('Error during test:', err);
  } finally {
    chromeProc.kill();
  }
}

main();
